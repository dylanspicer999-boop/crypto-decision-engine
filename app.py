import streamlit as st
import requests
import pandas as pd
import time

# --- UI Setup ---
st.set_page_config(page_title="Apex Crypto Terminal", page_icon="🏛️", layout="wide")
st.title("🏛️ Apex Crypto Terminal")
st.markdown("Live Institutional Confluence Matrix & Sentinel Risk Manager")

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

# --- Initialize Memory (Session State) ---
if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = []

# --- Build the Tabs ---
tab1, tab2 = st.tabs(["📊 Radar Scanner", "🛡️ Sentinel Tracker"])

# ==========================================
# TAB 1: THE RADAR SCANNER
# ==========================================
with tab1:
    st.subheader("Intraday Confluence Matrix (1H Timeframe)")
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
                    
                    # Quantitative Indicators
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
                    
                    curr_p = df['price'].iloc[-1]
                    curr_sma = df['SMA_50'].iloc[-1]
                    curr_vol = df['volume'].iloc[-1]
                    curr_vol_sma = df['Vol_SMA_20'].iloc[-1]
                    curr_rsi = df['RSI_14'].iloc[-1]
                    curr_macd = df['MACD'].iloc[-1]
                    curr_sig = df['MACD_Signal'].iloc[-1]
                    
                    # --- CALIBRATED CONFLUENCE MATRIX ---
                    score = 0
                    
                    trend_ok = curr_p > curr_sma
                    if trend_ok: score += 25
                    
                    if curr_rsi <= 32: score += 25
                    elif curr_rsi <= 42: score += 15
                    elif curr_rsi >= 70: score -= 40
                    
                    macd_ok = curr_macd > curr_sig
                    if macd_ok: score += 25
                    
                    vol_ok = curr_vol > (curr_vol_sma * 1.2)
                    if vol_ok: score += 25
                    
                    final_score = max(0, min(100, score))
                    
                    if curr_rsi >= 75:
                        verdict = "🔴 PASS (Overbought Exhaustion)"
                    elif final_score >= 70 and curr_rsi <= 45:
                        verdict = "🟢 GRADE-A BUY"
                    elif final_score >= 50:
                        verdict = "🟡 WATCHLIST (Forming Setup)"
                    else:
                        verdict = "🔴 PASS (Weak Edge)"
                    
                    price_fmt = f"${curr_p:.8f}" if curr_p < 0.01 else f"${curr_p:,.2f}"
                    vol_ratio = f"{curr_vol / curr_vol_sma:.1f}x" if curr_vol_sma > 0 else "1.0x"
                    
                    results.append({
                        "Asset": coin_name,
                        "Price": price_fmt,
                        "1H RSI": round(curr_rsi, 1),
                        "Trend": "Bullish" if trend_ok else "Bearish",
                        "MACD": "Bullish" if macd_ok else "Bearish",
                        "Vol Spike": vol_ratio,
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
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

# ==========================================
# TAB 2: THE SENTINEL TRACKER
# ==========================================
with tab2:
    st.subheader("Dynamic Trailing Stop Manager")
    
    # 1. Add Position Interface
    with st.expander("➕ Log New Trade"):
        col1, col2, col3 = st.columns(3)
        with col1:
            trade_coin = st.selectbox("Asset", list(watchlist.values()))
        with col2:
            trade_entry = st.number_input("Entry Price ($)", min_value=0.0, format="%.6f")
        with col3:
            trade_trail = st.number_input("Trailing Stop (%)", min_value=1.0, value=4.0, step=0.5)
        
        if st.button("Log Position"):
            # Find ID by Name
            trade_id = list(watchlist.keys())[list(watchlist.values()).index(trade_coin)]
            st.session_state['portfolio'].append({
                "coin_id": trade_id,
                "coin_name": trade_coin,
                "entry": trade_entry,
                "high_water": trade_entry, # Starts at entry
                "trail_pct": trade_trail / 100
            })
            st.success(f"{trade_coin} logged in Sentinel!")
            time.sleep(1)
            st.rerun()

    # 2. Monitor Active Positions
    st.markdown("### Active Positions")
    if not st.session_state['portfolio']:
        st.info("No active trades tracked. Log a position above to monitor it.")
    else:
        if st.button("🛡️ Refresh Sentinel", type="primary"):
            sentinel_results = []
            
            # Use CoinGecko's simple price endpoint for fast bulk checking
            ids = ",".join([p['coin_id'] for p in st.session_state['portfolio']])
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
            
            try:
                res = requests.get(url, headers=headers).json()
                
                for i, pos in enumerate(st.session_state['portfolio']):
                    curr_price = res.get(pos['coin_id'], {}).get('usd', pos['entry'])
                    
                    # Update High Water Mark
                    if curr_price > pos['high_water']:
                        st.session_state['portfolio'][i]['high_water'] = curr_price
                        
                    high = st.session_state['portfolio'][i]['high_water']
                    stop_price = high * (1 - pos['trail_pct'])
                    
                    # P&L Calculation
                    pnl_pct = ((curr_price - pos['entry']) / pos['entry']) * 100
                    pnl_str = f"+{pnl_pct:.2f}%" if pnl_pct >= 0 else f"{pnl_pct:.2f}%"
                    
                    # Stop Out Logic
                    if curr_price <= stop_price:
                        action = "🔴 STOPPED OUT (Close Trade)"
                    else:
                        action = "🟢 HOLD"
                        
                    sentinel_results.append({
                        "Asset": pos['coin_name'],
                        "Entry": f"${pos['entry']:.4f}",
                        "Current Price": f"${curr_price:.4f}",
                        "High Water Mark": f"${high:.4f}",
                        "Stop Loss": f"${stop_price:.4f}",
                        "P&L": pnl_str,
                        "Action": action
                    })
                    
                st.dataframe(pd.DataFrame(sentinel_results), use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.error("API error while fetching Sentinel prices. Try again.")

        if st.button("Clear All Positions"):
            st.session_state['portfolio'] = []
            st.rerun()
