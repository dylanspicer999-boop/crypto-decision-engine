import streamlit as st
import requests
import pandas as pd
import time

# --- UI Setup ---
st.set_page_config(page_title="Apex Crypto Terminal", page_icon="🏛️", layout="wide")
st.title("🏛️ Apex Crypto Terminal")
st.markdown("Live Institutional Confluence Matrix & Risk Manager")

# --- Secure API Keys ---
try:
    CG_API_KEY = st.secrets["CG_API_KEY"]
except:
    st.warning("⚠️ API Key not found in secrets. Using public limits.")
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

# --- State Management for Sentinel ---
if 'positions' not in st.session_state:
    st.session_state.positions = []

tab1, tab2 = st.tabs(["📊 Radar Scanner", "🛡️ Sentinel Tracker"])

# ==========================================
# TAB 1: RADAR SCANNER (DIVERGENCE ENGINE)
# ==========================================
with tab1:
    if st.button("🔄 Run Live Market Scan", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        total_coins = len(watchlist)
        
        for idx, (coin_id, coin_name) in enumerate(watchlist.items()):
            status_text.text(f"Analyzing {coin_name}...")
            try:
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=10"
                res = requests.get(url, headers=headers, timeout=10)
                
                if res.status_code == 200:
                    data = res.json()
                    prices = [item[1] for item in data['prices']]
                    volumes = [item[1] for item in data['total_volumes']]
                    
                    df = pd.DataFrame({'price': prices, 'volume': volumes})
                    
                    if len(df) < 50:
                        continue
                    
                    # Indicators
                    df['SMA_50'] = df['price'].rolling(window=50).mean()
                    df['Vol_SMA_20'] = df['volume'].rolling(window=20).mean()
                    
                    delta = df['price'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    df['RSI_14'] = 100 - (100 / (1 + rs))
                    
                    ema_12 = df['price'].ewm(span=12, adjust=False).mean()
                    ema_26 = df['price'].ewm(span=26, adjust=False).mean()
                    df['MACD'] = ema_12 - ema_26
                    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                    
                    # Closed Candle Lock
                    closed_p = df['price'].iloc[-2]
                    closed_sma = df['SMA_50'].iloc[-2]
                    closed_vol = df['volume'].iloc[-2]
                    closed_vol_sma = df['Vol_SMA_20'].iloc[-2]
                    closed_rsi = df['RSI_14'].iloc[-2]
                    closed_macd = df['MACD'].iloc[-2]
                    closed_sig = df['MACD_Signal'].iloc[-2]
                    
                    # Divergence Logic
                    past_30 = df.iloc[-32:-2]
                    lowest_idx = past_30['price'].idxmin()
                    past_low_p = past_30.loc[lowest_idx, 'price']
                    past_low_rsi = past_30.loc[lowest_idx, 'RSI_14']
                    
                    is_divergence = (closed_p < past_low_p) and (closed_rsi > past_low_rsi) and (closed_rsi < 45)
                    
                    # Scoring
                    score = 0
                    if closed_p > closed_sma: score += 25
                    
                    if is_divergence: score += 40
                    elif closed_rsi <= 32: score += 25
                    elif closed_rsi <= 42: score += 15
                    elif closed_rsi >= 70: score -= 40
                    
                    if closed_macd > closed_sig: score += 25
                    if closed_vol > (closed_vol_sma * 1.2): score += 25
                    
                    final_score = max(0, min(100, score))
                    
                    # Verdicts
                    if closed_rsi >= 75:
                        verdict = "🔴 PASS (Overbought Exhaustion)"
                    elif final_score >= 80 and is_divergence:
                        verdict = "🟢 SNIPER ENTRY (Divergence Confirmed)"
                    elif final_score >= 70:
                        verdict = "🟢 GRADE-A BUY (Confirmed Pullback)"
                    elif final_score >= 50:
                        verdict = "🟡 WATCHLIST (Forming Setup)"
                    else:
                        verdict = "🔴 PASS (Weak Edge)"
                    
                    price_fmt = f"${closed_p:.8f}" if closed_p < 0.01 else f"${closed_p:,.2f}"
                    
                    results.append({
                        "Asset": coin_name,
                        "Price (Closed)": price_fmt,
                        "1H RSI": round(closed_rsi, 1),
                        "Divergence": "🔥 YES" if is_divergence else "No",
                        "Score": f"{final_score}/100",
                        "Verdict": verdict
                    })
                    
            except Exception:
                pass
                
            progress_bar.progress((idx + 1) / total_coins)
            time.sleep(1.5)
            
        status_text.empty()
        progress_bar.empty()
        
        if results:
            results_df = pd.DataFrame(results)
            st.dataframe(results_df, use_container_width=True, hide_index=True)

# ==========================================
# TAB 2: SENTINEL TRACKER
# ==========================================
with tab2:
    st.subheader("Dynamic Trailing Stop Manager")
    
    with st.expander("➕ Log New Trade"):
        col1, col2, col3 = st.columns(3)
        with col1:
            trade_asset = st.selectbox("Asset", list(watchlist.values()))
        with col2:
            trade_entry = st.number_input("Entry Price ($)", min_value=0.000001, format="%.6f")
        with col3:
            trade_stop_pct = st.number_input("Trailing Stop (%)", min_value=0.1, max_value=50.0, value=4.0, step=0.5)
            
        if st.button("Log Position"):
            st.session_state.positions.append({
                "Asset": trade_asset,
                "Entry": trade_entry,
                "High Water Mark": trade_entry,
                "Stop Pct": trade_stop_pct / 100.0
            })
            st.success(f"Logged {trade_asset} at ${trade_entry}")

    st.subheader("Active Positions")
    if st.button("🛡️ Refresh Sentinel", type="primary"):
        if not st.session_state.positions:
            st.info("No active positions logged.")
        else:
            updated_positions = []
            for pos in st.session_state.positions:
                # Reverse lookup coin_id from coin_name
                coin_id = [k for k, v in watchlist.items() if v == pos["Asset"]][0]
                
                try:
                    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
                    res = requests.get(url, headers=headers, timeout=10)
                    if res.status_code == 200:
                        curr_price = res.json()[coin_id]['usd']
                        
                        # Update High Water Mark
                        if curr_price > pos["High Water Mark"]:
                            pos["High Water Mark"] = curr_price
                            
                        # Calculate Stop
                        stop_loss = pos["High Water Mark"] * (1 - pos["Stop Pct"])
                        pnl_pct = ((curr_price - pos["Entry"]) / pos["Entry"]) * 100
                        
                        action = "🟢 HOLD" if curr_price > stop_loss else "🔴 SELL (Stop Triggered)"
                        
                        updated_positions.append({
                            "Asset": pos["Asset"],
                            "Entry": f"${pos['Entry']:.4f}",
                            "Current Price": f"${curr_price:.4f}",
                            "High Water Mark": f"${pos['High Water Mark']:.4f}",
                            "Stop Loss": f"${stop_loss:.4f}",
                            "P&L": f"{pnl_pct:+.2f}%",
                            "Action": action
                        })
                except Exception:
                    pass
                time.sleep(1.5)
                
            if updated_positions:
                st.dataframe(pd.DataFrame(updated_positions), use_container_width=True, hide_index=True)

    if st.button("Clear All Positions"):
        st.session_state.positions = []
        st.rerun()
