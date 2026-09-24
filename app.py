import streamlit as st
import requests
import pandas as pd
import time
import plotly.graph_objects as go
import numpy as np

# --- UI Configuration ---
st.set_page_config(page_title="Apex Crypto Terminal", page_icon="🏛️", layout="wide")
st.title("🏛️ Apex Crypto Terminal")
st.markdown("Institutional Dual-Timeframe, Volatility, & Derivatives Decision Engine")

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
    st.header("🔔 Automation & Webhooks")
    discord_webhook = st.text_input("Discord Webhook URL", type="password")
    enable_alerts = st.checkbox("Enable Sniper Alerts")
    st.markdown("---")
    st.info("If enabled, the scanner will silently ping your Discord server the moment a Grade-A Sniper Entry triggers.")

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

tab1, tab2, tab3 = st.tabs(["📊 Radar Scanner", "🛡️ Sentinel Tracker", "🧪 Backtest Lab"])

# ==========================================
# TAB 1: RADAR SCANNER
# ==========================================
with tab1:
    col_scan, _ = st.columns([1, 4])
    with col_scan:
        scan_clicked = st.button("🔄 Run Live Market Scan", type="primary", use_container_width=True)

    if scan_clicked:
        progress_bar = st.progress(0)
        status_text = st.empty()
        fresh_results = []
        
        status_text.text("Acquiring Global Derivatives Data...")
        derivatives_data = fetch_hyperliquid_derivatives()
        total_coins = len(watchlist)
        
        for idx, (coin_id, coin_name) in enumerate(watchlist.items()):
            status_text.text(f"Analyzing {coin_name}...")
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
                        
                        delta = df_h['price'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        df_h['RSI_14'] = 100 - (100 / (1 + rs))
                        
                        df_h['Vol_SMA_20'] = df_h['volume'].rolling(window=20).mean()
                        ema_12 = df_h['price'].ewm(span=12, adjust=False).mean()
                        ema_26 = df_h['price'].ewm(span=26, adjust=False).mean()
                        df_h['MACD'] = ema_12 - ema_26
                        df_h['MACD_Signal'] = df_h['MACD'].ewm(span=9, adjust=False).mean()
                        
                        closed_p = df_h['price'].iloc[-2]
                        closed_z = df_h['Z_Score'].iloc[-2]
                        closed_vol = df_h['volume'].iloc[-2]
                        closed_vol_sma = df_h['Vol_SMA_20'].iloc[-2]
                        closed_rsi = df_h['RSI_14'].iloc[-2]
                        closed_macd = df_h['MACD'].iloc[-2]
                        closed_sig = df_h['MACD_Signal'].iloc[-2]
                        
                        past_30 = df_h.iloc[-32:-2]
                        lowest_idx = past_30['price'].idxmin()
                        past_low_p = past_30.loc[lowest_idx, 'price']
                        past_low_rsi = past_30.loc[lowest_idx, 'RSI_14']
                        
                        is_divergence = (closed_p < past_low_p) and (closed_rsi > past_low_rsi) and (closed_z < 0)
                        
                        score = 0
                        if macro_trend_bullish: score += 25
                        if is_divergence: score += 40
                        elif closed_z <= -2.0: score += 25
                        elif closed_z <= -1.0: score += 15
                        elif closed_z >= 1.5: score -= 40
                        
                        if closed_macd > closed_sig: score += 25
                        if closed_vol > (closed_vol_sma * 1.2): score += 25
                        
                        final_score = max(0, min(100, score))
                        
                        # --- Veto Hierarchy & Webhook Triggers ---
                        if not macro_trend_bullish:
                            verdict = "🔴 PASS (Macro Downtrend Veto)"
                        elif funding_rate >= 0.00045:
                            verdict = "🔴 PASS (Liquidation Risk / Crowded Long)"
                        elif closed_z >= 1.5:
                            verdict = "🔴 PASS (Statistical Exhaustion)"
                        elif closed_z > 0:
                            verdict = "🔴 PASS (No Dip Detected)"
                        elif final_score >= 80 and is_divergence and closed_z <= -1.0:
                            if oi > 50_000_000:
                                verdict = "🟢 SNIPER ENTRY (High-Conviction Squeeze)"
                            else:
                                verdict = "🟢 SNIPER ENTRY (Divergence Confirmed)"
                            
                            # DISCORD WEBHOOK FIRE
                            if enable_alerts and discord_webhook:
                                send_discord_alert(discord_webhook, f"🚨 **{verdict}** 🚨\n**Asset:** {coin_name}\n**Price:** ${closed_p:,.4f}\n**Z-Score:** {closed_z:.2f}\n**Open Interest:** ${oi:,.0f}")

                        elif final_score >= 70 and closed_z <= -1.0:
                            verdict = "🟢 GRADE-A BUY (Confirmed Z-Dip)"
                        elif closed_z > -1.0:
                            verdict = "🟡 WATCHLIST (Mild Pullback)"
                        elif final_score >= 50:
                            verdict = "🟡 WATCHLIST (Forming Setup)"
                        else:
                            verdict = "🔴 PASS (Weak Edge)"
                        
                        price_fmt = f"${closed_p:.8f}" if closed_p < 0.01 else f"${closed_p:,.2f}"
                        funding_fmt = f"{funding_rate * 100:.4f}%"
                        
                        if oi >= 1e9:
                            oi_fmt = f"${oi/1e9:.2f}B"
                        elif oi >= 1e6:
                            oi_fmt = f"${oi/1e6:.2f}M"
                        else:
                            oi_fmt = f"${oi:,.0f}"
                            
                        fresh_results.append({
                            "Asset": coin_name,
                            "Price": price_fmt,
                            "Z-Score": round(closed_z, 2),
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

    # --- Sorter & Filter Control Panel ---
    if st.session_state.scan_data:
        st.markdown("### ⚙️ Scan Controls")
        f1, f2 = st.columns([1, 1])
        with f1:
            view_filter = st.selectbox(
                "Filter Signals",
                ["All Assets", "Active Setups Only (Buys & Watchlist)", "Confirmed Buys Only (Grade-A & Sniper)"]
            )
        with f2:
            sort_by = st.selectbox(
                "Sort Table By",
                ["Score (Highest First)", "Z-Score (Most Oversold)", "Open Interest (Largest First)"]
            )
            
        df_display = pd.DataFrame(st.session_state.scan_data)
        
        if view_filter == "Active Setups Only (Buys & Watchlist)":
            df_display = df_display[df_display['Verdict'].str.contains("🟢|🟡")]
        elif view_filter == "Confirmed Buys Only (Grade-A & Sniper)":
            df_display = df_display[df_display['Verdict'].str.contains("🟢")]
            
        if sort_by == "Score (Highest First)":
            df_display = df_display.sort_values(by="_raw_score", ascending=False)
        elif sort_by == "Z-Score (Most Oversold)":
            df_display = df_display.sort_values(by="_raw_z", ascending=True)
        elif sort_by == "Open Interest (Largest First)":
            df_display = df_display.sort_values(by="_raw_oi", ascending=False)
            
        visible_columns = ["Asset", "Price", "Z-Score", "Funding Rate", "Open Interest", "Divergence", "Score", "Verdict"]
        st.dataframe(df_display[visible_columns], use_container_width=True, hide_index=True)

    # --- Interactive Chart Inspection ---
    st.markdown("---")
    st.subheader("🔍 Deep Dive Asset Visualizer")
    selected_coin_name = st.selectbox("Select Asset to Inspect Bands & Momentum", list(watchlist.values()), key="vis_asset")
    
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
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA_20'], mode='lines', name='20-SMA (Mean)', line=dict(color='#FFA500', width=1, dash='dash')))
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Upper_Band'], mode='lines', name='+2σ (Exhaustion)', line=dict(color='#FF4B4B', width=1)))
            fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['Lower_Band'], mode='lines', name='-2σ (Oversold Dip)', line=dict(color='#00BFFF', width=1)))
            
            fig.update_layout(title=f"{selected_coin_name} Volatility Bands (10-Day Hourly)", template="plotly_dark", height=450, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

# ==========================================
# TAB 2: SENTINEL TRACKER & HEAT MANAGER
# ==========================================
with tab2:
    st.subheader("Risk Sentinel & Portfolio Heat Manager")
    
    with st.expander("➕ Log New Trade & Calculate Position Size", expanded=True):
        st.markdown("**1. Portfolio Risk Limits**")
        c1, c2 = st.columns(2)
        with c1:
            port_size = st.number_input("Total Portfolio Size ($)", min_value=50.0, value=5000.0, step=250.0, key="port_size")
        with c2:
            max_risk = st.number_input("Risk Limit per Trade (%)", min_value=0.1, max_value=10.0, value=2.0, step=0.1)
        
        # PORTFOLIO HEAT CALCULATION
        total_allocated = sum([pos.get("Size", 0) for pos in st.session_state.positions])
        heat_pct = (total_allocated / port_size) * 100 if port_size > 0 else 0
        
        st.markdown(f"**Portfolio Heat: {heat_pct:.1f}%** Allocated (\\${total_allocated:,.2f} / \\${port_size:,.2f})")
        st.progress(min(heat_pct / 100.0, 1.0))
        if heat_pct >= 100:
            st.error("⚠️ **OVERLEVERAGED:** Active positions exceed total portfolio balance. Close trades before adding new ones.")
            
        st.markdown("**2. Trade Configuration**")
        col1, col2, col3 = st.columns(3)
        with col1:
            trade_asset = st.selectbox("Select Asset to Trade", list(watchlist.values()), key="trade_asset")
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
            f"**Execution Blueprint:** Max dollar loss: **\\${risk_dollar_budget:,.2f}** | "
            f"Allocated position size: **\\${suggested_position:,.2f}**\n\n"
            f"🎯 **Target 1 (+1.5R):** \\${target_1:,.4f} | 🎯 **Target 2 (+3.0R):** \\${target_2:,.4f}"
        )
            
        if st.button("Commit Trade to Sentinel"):
            if heat_pct + ((suggested_position/port_size)*100) > 100:
                st.error("Trade rejected: This position would push your portfolio heat over 100%.")
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
                st.success(f"Position active: {trade_asset} logged at \\${trade_entry:,.4f}")
                time.sleep(1)
                st.rerun()

    st.subheader("Active Positions")
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
# TAB 3: DYNAMIC BACKTEST OPTIMIZER
# ==========================================
with tab3:
    st.subheader("🧪 Dynamic Strategy Optimizer (90-Day Hourly Data)")
    st.markdown("Fine-tune your quantitative thresholds to find the highest historical win rate for any asset.")
    
    col_bt1, col_bt2, col_bt3 = st.columns(3)
    with col_bt1:
        bt_asset_name = st.selectbox("Select Asset to Backtest", list(watchlist.values()), key="bt_asset")
    with col_bt2:
        z_threshold = st.slider("Z-Score Entry Threshold", min_value=-3.0, max_value=-0.5, value=-1.0, step=0.1, help="How deep must the dip be to trigger a buy?")
    with col_bt3:
        hold_hours = st.select_slider("Holding Timeframe (Hours)", options=[4, 8, 12, 24, 48, 72], value=24, help="How long do we hold the asset after buying the dip?")
    
    if st.button("Run Vectorized Backtest", type="primary"):
        bt_coin_id = [k for k, v in watchlist.items() if v == bt_asset_name][0]
        with st.spinner(f"Pulling 90 days of historical hourly data for {bt_asset_name}..."):
            df_bt = fetch_backtest_data(bt_coin_id)
            
        if df_bt is not None and len(df_bt) > 50:
            df_bt['SMA_20'] = df_bt['price'].rolling(window=20).mean()
            df_bt['STD_20'] = df_bt['price'].rolling(window=20).std()
            df_bt['Z_Score'] = (df_bt['price'] - df_bt['SMA_20']) / df_bt['STD_20']
            
            # Dynamic forward return calculation based on slider
            df_bt['Forward_Return'] = df_bt['price'].shift(-hold_hours) / df_bt['price'] - 1
            
            # Filter entries based on dynamic slider
            buy_signals = df_bt[df_bt['Z_Score'] <= z_threshold].dropna(subset=['Forward_Return'])
            
            total_signals = len(buy_signals)
            if total_signals > 0:
                winning_trades = buy_signals[buy_signals['Forward_Return'] > 0]
                win_rate = (len(winning_trades) / total_signals) * 100
                avg_pnl = buy_signals['Forward_Return'].mean() * 100
                max_win = buy_signals['Forward_Return'].max() * 100
                max_loss = buy_signals['Forward_Return'].min() * 100
                
                st.success(f"Backtest complete. Processed {len(df_bt):,} hourly candles.")
                
                col_b1, col_b2, col_b3 = st.columns(3)
                col_b1.metric("Total Entry Signals Fired", total_signals)
                col_b2.metric(f"{hold_hours}-Hour Forward Win Rate", f"{win_rate:.1f}%")
                col_b3.metric("Average Profit per Trade", f"{avg_pnl:+.2f}%")
                
                st.markdown(f"**Best Performing Trade:** +{max_win:.2f}% | **Worst Performing Trade:** {max_loss:.2f}%")
                
                fig_bt = go.Figure()
                fig_bt.add_trace(go.Scatter(x=df_bt.index, y=df_bt['price'], mode='lines', name='Price', line=dict(color='#333333')))
                fig_bt.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['price'], mode='markers', name=f'Z-Score {z_threshold} Triggers', marker=dict(color='#00FFA3', size=8, symbol='triangle-up')))
                fig_bt.update_layout(title="Historical Trade Executions", template="plotly_dark", height=400)
                st.plotly_chart(fig_bt, use_container_width=True)
            else:
                st.warning(f"No signals triggered in the last 90 days for {bt_asset_name} at a strict Z-Score of {z_threshold}.")
        else:
            st.error("Failed to retrieve sufficient historical data. API may be rate limited.")
