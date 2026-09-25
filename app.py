import streamlit as st
import requests
import pandas as pd
import time
import plotly.graph_objects as go
import numpy as np

# --- UI Configuration ---
st.set_page_config(page_title="Apex Crypto Terminal", page_icon="🏛️", layout="wide")
st.title("🏛️ Apex Quantitative Decision Engine")
st.markdown("Institutional Relative Strength, Volume Absorption, & Derivatives Alpha Matrix")

# --- Secrets & API Keys ---
try:
    CG_API_KEY = st.secrets["CG_API_KEY"]
except Exception:
    CG_API_KEY = ""

headers = {"x-cg-demo-api-key": CG_API_KEY}

watchlist = {
    'bitcoin': 'Bitcoin', 'ethereum': 'Ethereum', 'solana': 'Solana',
    'cardano': 'Cardano', 'avalanche-2': 'Avalanche', 'litecoin': 'Litecoin',
    'bitcoin-cash': 'Bitcoin Cash', 'ethereum-classic': 'Ethereum Classic',
    'tezos': 'Tezos', 'dogecoin': 'Dogecoin', 'shiba-inu': 'Shiba Inu',
    'pepe': 'Pepe', 'chainlink': 'Chainlink', 'uniswap': 'Uniswap',
    'aave': 'Aave', 'compound-governance-token': 'Compound',
    'ripple': 'XRP', 'stellar': 'Stellar'
}

ticker_map = {
    'bitcoin': 'BTC', 'ethereum': 'ETH', 'solana': 'SOL',
    'cardano': 'ADA', 'avalanche-2': 'AVAX', 'litecoin': 'LTC',
    'bitcoin-cash': 'BCH', 'ethereum-classic': 'ETC',
    'tezos': 'XTZ', 'dogecoin': 'DOGE', 'shiba-inu': 'SHIB',
    'pepe': 'PEPE', 'chainlink': 'LINK', 'uniswap': 'UNI',
    'aave': 'AAVE', 'compound-governance-token': 'COMP',
    'ripple': 'XRP', 'stellar': 'XLM'
}

# --- Webhook Alert Function ---
def send_discord_alert(webhook_url, message):
    if webhook_url:
        try:
            payload = {"content": message}
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception:
            pass

# --- Sidebar: Automation Settings ---
with st.sidebar:
    st.header("🔔 Automation & Alerts")
    discord_webhook = st.text_input("Discord Webhook URL", type="password")
    enable_alerts = st.checkbox("Enable Sniper Alerts")
    st.markdown("---")
    st.markdown("### ⚙️ Alpha Engine Parameters")
    min_z_score = st.slider("Strict Dip Threshold (Z-Score)", min_value=-3.0, max_value=-0.5, value=-1.2, step=0.1)
    vol_climax_mult = st.slider("Min Volume Absorption Multiple", min_value=1.0, max_value=3.0, value=1.5, step=0.1)

# --- Data Fetching Helpers ---
@st.cache_data(ttl=43200, show_spinner=False)
def fetch_macro_trend(coin_id):
    try:
        url_daily = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=100&interval=daily"
        res_daily = requests.get(url_daily, headers=headers, timeout=10)
        if res_daily.status_code == 200:
            data = res_daily.json()
            prices = [item[1] for item in data['prices']]
            df = pd.DataFrame({'price': prices})
            if len(df) >= 50:
                df['SMA_50'] = df['price'].rolling(window=50).mean()
                return bool(df['price'].iloc[-2] > df['SMA_50'].iloc[-2])
    except Exception:
        pass
    return False

@st.cache_data(ttl=60, show_spinner=False)
def fetch_hyperliquid_derivatives():
    derivatives = {}
    try:
        url = "https://api.hyperliquid.xyz/info"
        headers_hl = {"Content-Type": "application/json"}
        payload = {"type": "metaAndAssetCtxs"}
        res = requests.post(url, headers=headers_hl, json=payload, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            universe = data[0].get("universe", [])
            asset_ctxs = data[1]
            for i, asset in enumerate(universe):
                coin_symbol = asset.get("name")
                funding = float(asset_ctxs[i].get("funding", 0.0))
                oi_coins = float(asset_ctxs[i].get("openInterest", 0.0))
                mark_px = float(asset_ctxs[i].get("markPx", 0.0))
                derivatives[coin_symbol] = {
                    "funding": funding,
                    "oi_notional": oi_coins * mark_px
                }
    except Exception:
        pass
    return derivatives

@st.cache_data(ttl=30, show_spinner=False)
def fetch_clearinghouse_state(wallet_address):
    try:
        url = "https://api.hyperliquid.xyz/info"
        headers_hl = {"Content-Type": "application/json"}
        payload = {"type": "clearinghouseState", "user": wallet_address}
        res = requests.post(url, headers=headers_hl, json=payload, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=20, show_spinner=False)
def fetch_single_spot_price(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            return float(res.json()[coin_id]['usd'])
    except Exception:
        pass
    return 0.0

@st.cache_data(ttl=300, show_spinner=False)
def fetch_btc_performance():
    try:
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=2"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            prices = [x[1] for x in res.json()['prices']]
            if len(prices) >= 24:
                return (prices[-1] - prices[-24]) / prices[-24]
    except Exception:
        pass
    return 0.0

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_backtest_data(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=90"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            timestamps = [pd.to_datetime(item[0], unit='ms') for item in data['prices']]
            prices = [item[1] for item in data['prices']]
            return pd.DataFrame({'timestamp': timestamps, 'price': prices}).set_index('timestamp')
    except Exception:
        pass
    return None

# --- State Management ---
if 'positions' not in st.session_state:
    st.session_state.positions = []
if 'scan_data' not in st.session_state:
    st.session_state.scan_data = []

tab1, tab2, tab3, tab4 = st.tabs(["🎯 Decision Matrix", "🛡️ Sentinel Tracker", "🧪 Quantitative Optimizer", "🐋 Smart Money Tracker"])

# ==========================================
# TAB 1: DECISION MATRIX
# ==========================================
with tab1:
    col_scan, _ = st.columns([1, 4])
    with col_scan:
        scan_clicked = st.button("🔄 Execute Quantitative Evaluation", type="primary", use_container_width=True)

    if scan_clicked:
        progress_bar = st.progress(0)
        status_text = st.empty()
        fresh_results = []
        
        status_text.text("Benchmarking Bitcoin Macro Baseline & Derivatives...")
        btc_24h_return = fetch_btc_performance()
        derivatives_data = fetch_hyperliquid_derivatives()
        total_coins = len(watchlist)
        
        for idx, (coin_id, coin_name) in enumerate(watchlist.items()):
            status_text.text(f"Evaluating Microstructure for {coin_name}...")
            try:
                macro_trend_bullish = fetch_macro_trend(coin_id)
                url_hourly = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=10"
                res_hourly = requests.get(url_hourly, headers=headers, timeout=10)
                
                ticker = ticker_map.get(coin_id)
                ticker_data = derivatives_data.get(ticker, {"funding": 0.0, "oi_notional": 0.0})
                funding_rate = ticker_data["funding"]
                oi = ticker_data["oi_notional"]
                
                if res_hourly.status_code == 200:
                    data_hourly = res_hourly.json()
                    prices_h = [item[1] for item in data_hourly['prices']]
                    volumes_h = [item[1] for item in data_hourly['total_volumes']]
                    df_h = pd.DataFrame({'price': prices_h, 'volume': volumes_h})
                    
                    if len(df_h) >= 50:
                        df_h['SMA_20'] = df_h['price'].rolling(window=20).mean()
                        df_h['STD_20'] = df_h['price'].rolling(window=20).std()
                        df_h['Z_Score'] = (df_h['price'] - df_h['SMA_20']) / df_h['STD_20']
                        
                        asset_24h_return = (df_h['price'].iloc[-1] - df_h['price'].iloc[-25]) / df_h['price'].iloc[-25] if len(df_h) >= 25 else 0.0
                        rs_vs_btc = asset_24h_return - btc_24h_return
                        
                        df_h['Vol_SMA_20'] = df_h['volume'].rolling(window=20).mean()
                        closed_vol = df_h['volume'].iloc[-2]
                        closed_vol_sma = df_h['Vol_SMA_20'].iloc[-2]
                        volume_absorbed = closed_vol >= (closed_vol_sma * vol_climax_mult)
                        
                        delta = df_h['price'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        df_h['RSI_14'] = 100 - (100 / (1 + rs))
                        
                        ema_12 = df_h['price'].ewm(span=12, adjust=False).mean()
                        ema_26 = df_h['price'].ewm(span=26, adjust=False).mean()
                        df_h['MACD'] = ema_12 - ema_26
                        df_h['MACD_Signal'] = df_h['MACD'].ewm(span=9, adjust=False).mean()
                        df_h['MACD_Hist'] = df_h['MACD'] - df_h['MACD_Signal']
                        
                        closed_p = df_h['price'].iloc[-2]
                        closed_z = df_h['Z_Score'].iloc[-2]
                        closed_rsi = df_h['RSI_14'].iloc[-2]
                        curr_hist = df_h['MACD_Hist'].iloc[-2]
                        prev_hist = df_h['MACD_Hist'].iloc[-3]
                        momentum_decelerating = curr_hist > prev_hist
                        
                        past_30 = df_h.iloc[-32:-2]
                        lowest_idx = past_30['price'].idxmin()
                        past_low_p = past_30.loc[lowest_idx, 'price']
                        past_low_rsi = past_30.loc[lowest_idx, 'RSI_14']
                        is_divergence = (closed_p < past_low_p) and (closed_rsi > past_low_rsi) and (closed_z < 0)
                        
                        score = 0
                        if macro_trend_bullish: score += 20
                        if closed_z <= min_z_score: score += 25
                        if is_divergence: score += 25
                        if volume_absorbed: score += 15
                        if momentum_decelerating: score += 10
                        if funding_rate <= 0.0: score += 10
                        if rs_vs_btc > 0.01: score += 10
                        
                        final_score = min(100, score)
                        
                        if not macro_trend_bullish:
                            verdict = "🔴 PASS (Macro Downtrend Veto)"
                        elif funding_rate >= 0.00045:
                            verdict = "🔴 PASS (Liquidation Risk / Crowded Long)"
                        elif closed_z >= 1.5:
                            verdict = "🔴 PASS (Statistical Exhaustion)"
                        elif closed_z > -0.5:
                            verdict = "🔴 PASS (No Statistical Dip)"
                        elif closed_z <= min_z_score and not volume_absorbed:
                            verdict = "⚠️ PASS (Falling Knife / Volume Deficit)"
                        elif final_score >= 80 and closed_z <= min_z_score and (volume_absorbed or is_divergence):
                            if funding_rate <= 0.0:
                                verdict = "🟢 SNIPER ENTRY (Short Squeeze Ignition)"
                            else:
                                verdict = "🟢 SNIPER ENTRY (High-Volume Absorption)"
                            
                            if enable_alerts and discord_webhook:
                                send_discord_alert(
                                    discord_webhook,
                                    f"🎯 **HIGH-PROBABILITY QUANT SIGNAL** 🎯\n"
                                    f"**Asset:** {coin_name}\n"
                                    f"**Price:** ${closed_p:,.4f}\n"
                                    f"**Z-Score:** {closed_z:.2f}\n"
                                    f"**Relative vs BTC:** {rs_vs_btc*100:+.2f}%\n"
                                    f"**Verdict:** {verdict}"
                                )
                        elif final_score >= 65 and closed_z <= -1.0:
                            verdict = "🟡 WATCHLIST (Absorption In Progress)"
                        else:
                            verdict = "🔴 PASS (Insufficient Edge)"
                        
                        price_fmt = f"${closed_p:.8f}" if closed_p < 0.01 else f"${closed_p:,.2f}"
                        funding_fmt = f"{funding_rate * 100:.4f}%"
                        oi_fmt = f"${oi/1e6:.1f}M" if oi < 1e9 else f"${oi/1e9:.2f}B"
                        
                        fresh_results.append({
                            "Asset": coin_name,
                            "Price": price_fmt,
                            "Z-Score": round(closed_z, 2),
                            "Vol Absorption": "✅ YES" if volume_absorbed else "❌ Low",
                            "Alpha vs BTC": f"{rs_vs_btc*100:+.2f}%",
                            "Funding Rate": funding_fmt,
                            "Open Interest": oi_fmt,
                            "Divergence": "🔥 YES" if is_divergence else "No",
                            "Score": f"{final_score}/100",
                            "Verdict": verdict,
                            "_raw_score": final_score,
                            "_raw_z": closed_z,
                            "_raw_oi": oi
                        })
            except Exception:
                pass
                
            progress_bar.progress((idx + 1) / total_coins)
            time.sleep(1.4)
            
        status_text.empty()
        progress_bar.empty()
        st.session_state.scan_data = fresh_results

    if st.session_state.scan_data:
        st.markdown("### 🔍 Execution Filters")
        f1, f2 = st.columns(2)
        with f1:
            view_filter = st.selectbox(
                "Filter Signal Quality",
                ["Confirmed Buys Only (Grade-A & Sniper)", "Active Setups Only (Buys & Watchlist)", "All Tracked Assets"]
            )
        with f2:
            sort_by = st.selectbox(
                "Rank Priority",
                ["Score (Highest First)", "Z-Score (Deepest Oversold)", "Open Interest (Derivatives Liquidity)"]
            )
            
        df_display = pd.DataFrame(st.session_state.scan_data)
        
        if view_filter == "Confirmed Buys Only (Grade-A & Sniper)":
            df_display = df_display[df_display['Verdict'].str.contains("🟢")]
        elif view_filter == "Active Setups Only (Buys & Watchlist)":
            df_display = df_display[df_display['Verdict'].str.contains("🟢|🟡")]
            
        if sort_by == "Score (Highest First)":
            df_display = df_display.sort_values(by="_raw_score", ascending=False)
        elif sort_by == "Z-Score (Deepest Oversold)":
            df_display = df_display.sort_values(by="_raw_z", ascending=True)
        elif sort_by == "Open Interest (Derivatives Liquidity)":
            df_display = df_display.sort_values(by="_raw_oi", ascending=False)
            
        cols = ["Asset", "Price", "Z-Score", "Vol Absorption", "Alpha vs BTC", "Funding Rate", "Open Interest", "Divergence", "Score", "Verdict"]
        st.dataframe(df_display[cols], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📊 Price Distribution & Volatility Channel")
    selected_coin_name = st.selectbox("Select Asset to Verify Volatility Envelopes", list(watchlist.values()), key="vis_asset")
    
    if st.button("Generate Inspection Chart"):
        selected_id = [k for k, v in watchlist.items() if v == selected_coin_name][0]
        url = f"https://api.coingecko.com/api/v3/coins/{selected_id}/market_chart?vs_currency=usd&days=10"
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            timestamps = [pd.to_datetime(item[0], unit='ms') for item in data['prices']]
            prices = [item[1] for item in data['prices']]
            
            df_chart = pd.DataFrame({'timestamp': timestamps, 'price': prices}).set_index('timestamp')
            df_chart['SMA_20'] = df_chart['price'].rolling(20).mean()
            df_chart['Upper_Band'] = df_chart['SMA_20'] + (df_chart['price'].rolling(20).std() * 2)
            df_chart['Lower_Band'] = df_chart['SMA_20'] - (df_chart['price'].rolling(20).std() * 2)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['price'], mode='lines', name='Price', line=dict(color='#00FFA3', width=2)))
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA_20'], mode='lines', name='20-SMA', line=dict(color='#FFA500', width=1, dash='dash')))
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Upper_Band'], mode='lines', name='+2σ Exhaustion', line=dict(color='#FF4B4B', width=1)))
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Lower_Band'], mode='lines', name='-2σ Statistical Dip', line=dict(color='#00BFFF', width=1)))
            
            fig.update_layout(title=f"{selected_coin_name} Microstructure Envelopes", template="plotly_dark", height=420, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

# ==========================================
# TAB 2: SENTINEL TRACKER
# ==========================================
with tab2:
    st.subheader("Dynamic Trailing Stop, Risk Heat, & Asymmetric R:R Brackets")
    
    with st.expander("➕ Log New Trade & Calculate Position Size", expanded=True):
        st.markdown("**1. Portfolio Risk Budget**")
        c1, c2 = st.columns(2)
        with c1:
            port_size = st.number_input("Total Capital Pool ($)", min_value=50.0, value=5000.0, step=250.0, key="port_size")
        with c2:
            max_risk = st.number_input("Risk Limit per Trade (%)", min_value=0.1, max_value=10.0, value=2.0, step=0.1)
        
        total_allocated = sum([pos.get("Size", 0) for pos in st.session_state.positions])
        heat_pct = (total_allocated / port_size) * 100 if port_size > 0 else 0
        
        st.markdown(f"**Portfolio Heat: {heat_pct:.1f}%** Allocated (${total_allocated:,.2f} / ${port_size:,.2f})")
        st.progress(min(heat_pct / 100.0, 1.0))
        if heat_pct >= 100:
            st.error("⚠️ Overleveraged: Portfolio heat limit reached. Close positions before opening new ones.")
            
        st.markdown("**2. Trade Execution Parameters**")
        col1, col2, col3 = st.columns(3)
        with col1:
            trade_asset = st.selectbox("Execution Asset", list(watchlist.values()), key="trade_asset")
            selected_coin_id = [k for k, v in watchlist.items() if v == trade_asset][0]
            live_price_estimate = fetch_single_spot_price(selected_coin_id)
        with col2:
            default_entry = live_price_estimate if live_price_estimate > 0 else 1.0
            trade_entry = st.number_input("Entry Price ($)", min_value=0.00000001, format="%.6f", value=default_entry)
        with col3:
            trade_stop_pct = st.number_input("Trailing Stop (%)", min_value=0.1, max_value=50.0, value=4.0, step=0.5)
            
        risk_dollar_budget = port_size * (max_risk / 100.0)
        stop_fraction = trade_stop_pct / 100.0
        suggested_position = risk_dollar_budget / stop_fraction
        
        risk_per_coin = trade_entry * stop_fraction
        target_1 = trade_entry + (1.5 * risk_per_coin)
        target_2 = trade_entry + (3.0 * risk_per_coin)
        
        st.info(
            f"**Execution Plan:** Max Dollar Risk: **${risk_dollar_budget:,.2f}** | "
            f"Required Position Size: **${suggested_position:,.2f}**\n\n"
            f"🎯 Target 1 (+1.5R): ${target_1:,.4f} | 🎯 Target 2 (+3.0R): ${target_2:,.4f}"
        )
            
        if st.button("Log Position into Sentinel"):
            if heat_pct + ((suggested_position/port_size)*100) > 100:
                st.error("Execution Rejected: Trade size violates portfolio heat limits.")
            else:
                st.session_state.positions.append({
                    "Asset": trade_asset,
                    "Entry": trade_entry,
                    "High Water Mark": trade_entry,
                    "Stop Pct": stop_fraction,
                    "Size": suggested_position,
                    "TP1": target_1,
                    "TP2": target_2
                })
                st.success(f"Position active: {trade_asset} logged at ${trade_entry:,.4f}")
                time.sleep(1)
                st.rerun()

    st.subheader("Active Position Tracking")
    if st.button("🛡️ Refresh Sentinel & Check Brackets", type="primary"):
        if not st.session_state.positions:
            st.info("No active positions currently logged.")
        else:
            updated_positions = []
            for pos in st.session_state.positions:
                coin_id = [k for k, v in watchlist.items() if v == pos["Asset"]][0]
                try:
                    curr_price = fetch_single_spot_price(coin_id)
                    if curr_price > 0:
                        if curr_price > pos["High Water Mark"]:
                            pos["High Water Mark"] = curr_price
                            
                        stop_loss = pos["High Water Mark"] * (1 - pos["Stop Pct"])
                        pnl_pct = ((curr_price - pos["Entry"]) / pos["Entry"]) * 100
                        position_size = pos.get("Size", 0)
                        pnl_dollars = position_size * (pnl_pct / 100.0)
                        
                        if curr_price <= stop_loss:
                            action = "🔴 STOPPED OUT"
                        elif curr_price >= pos.get("TP2", 0.0):
                            action = "🎯 TP2 REACHED"
                        elif curr_price >= pos.get("TP1", 0.0):
                            action = "🎯 TP1 REACHED"
                        else:
                            action = "🟢 HOLD"
                        
                        updated_positions.append({
                            "Asset": pos["Asset"],
                            "Size": f"${position_size:,.2f}",
                            "Entry": f"${pos['Entry']:,.4f}",
                            "Current": f"${curr_price:,.4f}",
                            "Stop Loss": f"${stop_loss:,.4f}",
                            "P&L": f"{pnl_pct:+.2f}% (${pnl_dollars:+.2f})",
                            "Action": action
                        })
                except Exception:
                    pass
                time.sleep(1.0)
                
            if updated_positions:
                st.dataframe(pd.DataFrame(updated_positions), use_container_width=True, hide_index=True)

    if st.button("Clear All Positions"):
        st.session_state.positions = []
        st.rerun()

# ==========================================
# TAB 3: QUANTITATIVE OPTIMIZER
# ==========================================
with tab3:
    st.subheader("🧪 Edge Validation & Horizon Backtesting")
    st.markdown("Test the forward expectancy of oversold entries across 2,000+ historical candles.")
    
    col_bt1, col_bt2, col_bt3 = st.columns(3)
    with col_bt1:
        bt_asset_name = st.selectbox("Asset Under Test", list(watchlist.values()), key="bt_asset")
    with col_bt2:
        bt_z_thresh = st.slider("Entry Z-Score Threshold", min_value=-3.0, max_value=-0.5, value=-1.2, step=0.1)
    with col_bt3:
        hold_hours = st.select_slider("Holding Window (Hours)", options=[4, 8, 12, 24, 48, 72], value=24)
    
    if st.button("Run Simulation", type="primary"):
        bt_coin_id = [k for k, v in watchlist.items() if v == bt_asset_name][0]
        with st.spinner(f"Pulling 90-day candle data for {bt_asset_name}..."):
            df_bt = fetch_backtest_data(bt_coin_id)
            
        if df_bt is not None and len(df_bt) > 50:
            df_bt['SMA_20'] = df_bt['price'].rolling(window=20).mean()
            df_bt['STD_20'] = df_bt['price'].rolling(window=20).std()
            df_bt['Z_Score'] = (df_bt['price'] - df_bt['SMA_20']) / df_bt['STD_20']
            
            df_bt['Forward_Return'] = df_bt['price'].shift(-hold_hours) / df_bt['price'] - 1
            buy_signals = df_bt[df_bt['Z_Score'] <= bt_z_thresh].dropna(subset=['Forward_Return'])
            
            total_signals = len(buy_signals)
            if total_signals > 0:
                winning_trades = buy_signals[buy_signals['Forward_Return'] > 0]
                win_rate = (len(winning_trades) / total_signals) * 100
                avg_pnl = buy_signals['Forward_Return'].mean() * 100
                max_win = buy_signals['Forward_Return'].max() * 100
                max_loss = buy_signals['Forward_Return'].min() * 100
                
                col_b1, col_b2, col_b3 = st.columns(3)
                col_b1.metric("Signals Fired", total_signals)
                col_b2.metric(f"{hold_hours}h Win Rate", f"{win_rate:.1f}%")
                col_b3.metric("Expectancy / Trade", f"{avg_pnl:+.2f}%")
                
                st.markdown(f"**Max Favorable Excursion:** +{max_win:.2f}% | **Max Adverse Excursion:** {max_loss:.2f}%")
                
                fig_bt = go.Figure()
                fig_bt.add_trace(go.Scatter(x=df_bt.index, y=df_bt['price'], mode='lines', name='Price', line=dict(color='#333333')))
                fig_bt.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['price'], mode='markers', name=f'Z-Score {bt_z_thresh} Trigger', marker=dict(color='#00FFA3', size=8, symbol='triangle-up')))
                fig_bt.update_layout(title="Historical Signal Density", template="plotly_dark", height=400)
                st.plotly_chart(fig_bt, use_container_width=True)
            else:
                st.warning(f"No triggers observed for {bt_asset_name} under a {bt_z_thresh} Z-Score requirement.")
        else:
            st.error("Historical dataset unavailable. Check connection limits.")

# ==========================================
# TAB 4: SMART MONEY TRACKER (WHALES)
# ==========================================
with tab4:
    st.subheader("🐋 Smart Money / Whale Surveillance")
    st.markdown("Track live perpetual futures exposure, leverage, and PnL for top Hyperliquid addresses.")
    
    # Pre-loaded leaderboard whale addresses
    known_whales = {
        "Select a Curated Target...": None,
        "Alpha Whale (Leaderboard Rank 1)": "0x85ecf584f25db6f146718b86d493e33c5af72052",
        "Apex Predator (High Win-Rate)": "0xd820894cbda3406368d4a974b77f804fc9c71671",
        "Deep Pocket (Max Open Interest)": "0x1f562bf57a06f3dc8693c66f50b86a87799ce77e",
        "Custom Wallet Address...": "custom"
    }
    
    col_w1, col_w2 = st.columns([3, 1])
    with col_w1:
        target_selection = st.selectbox("Select Top Target or Enter Custom", list(known_whales.keys()))
        if known_whales.get(target_selection) == "custom":
            target_wallet = st.text_input("Enter Hyperliquid Wallet Address (0x...)", value="", placeholder="0x...")
        else:
            target_wallet = known_whales.get(target_selection)
            
    with col_w2:
        st.markdown("<br>", unsafe_allow_html=True) 
        scan_whale = st.button("📡 Scan Wallet", type="primary", use_container_width=True)
        
    if scan_whale:
        if not target_wallet:
            st.warning("Please select a target or enter a custom wallet address.")
        elif not target_wallet.startswith("0x") or len(target_wallet) != 42:
            st.error("Invalid wallet address format. Must be an EVM-compatible 0x address.")
        else:
            with st.spinner(f"Intercepting clearinghouse state for {target_wallet[:6]}...{target_wallet[-4:]}"):
                state_data = fetch_clearinghouse_state(target_wallet)
                
            if state_data and "marginSummary" in state_data:
                margin = state_data["marginSummary"]
                account_val = float(margin.get("accountValue", 0))
                total_ntl = float(margin.get("totalNtlPos", 0))
                margin_used = float(margin.get("totalMarginUsed", 0))
                
                est_leverage = total_ntl / account_val if account_val > 0 else 0
                
                st.markdown("### 📊 Account Overview")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Account Equity", f"${account_val:,.2f}")
                c2.metric("Total Open Interest", f"${total_ntl:,.2f}")
                c3.metric("Margin Used", f"${margin_used:,.2f}")
                c4.metric("Est. Account Leverage", f"{est_leverage:.2f}x")
                
                positions = state_data.get("assetPositions", [])
                if positions:
                    st.markdown("### 🟢 Active Perpetual Positions")
                    pos_list = []
                    for p in positions:
                        pos = p["position"]
                        coin = pos["coin"]
                        size = float(pos["szi"])
                        entry = float(pos["entryPx"])
                        pos_val = float(pos["positionValue"])
                        pnl = float(pos["unrealizedPnl"])
                        lev = pos["leverage"]["value"]
                        
                        side = "LONG" if size > 0 else "SHORT"
                        
                        pos_list.append({
                            "Asset": coin,
                            "Side": side,
                            "Size": f"{abs(size):,.4f}",
                            "Entry Price": f"${entry:,.4f}",
                            "Position Value": f"${pos_val:,.2f}",
                            "Leverage": f"{lev}x",
                            "Unrealized PnL": f"${pnl:,.2f}"
                        })
                        
                    df_pos = pd.DataFrame(pos_list)
                    st.dataframe(df_pos, use_container_width=True, hide_index=True)
                else:
                    st.info("No active perpetual positions found for this wallet. They are currently flat.")
            else:
                st.error("Could not retrieve wallet data. Ensure the address is correct and active on Hyperliquid.")
