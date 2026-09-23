import streamlit as st
import requests
import pandas as pd
import time

# --- UI Setup ---
st.set_page_config(page_title="Apex Crypto Terminal", page_icon="🏛️", layout="wide")
st.title("🏛️ Apex Crypto Terminal")
st.markdown("Live Institutional Confluence Matrix | Hourly Intraday Filter")

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
                
                # Latest Readings
                curr_p = df['price'].iloc[-1]
                curr_sma = df['SMA_50'].iloc[-1]
                curr_vol = df['volume'].iloc[-1]
                curr_vol_sma = df['Vol_SMA_20'].iloc[-1]
                curr_rsi = df['RSI_14'].iloc[-1]
                curr_macd = df['MACD'].iloc[-1]
                curr_sig = df['MACD_Signal'].iloc[-1]
                
                # --- CALIBRATED CONFLUENCE MATRIX ---
                score = 0
                
                # 1. Macro Trend (+25 pts)
                trend_ok = curr_p > curr_sma
                if trend_ok: score += 25
                
                # 2. Intraday Pullback (+25 pts) or Penalty
                if curr_rsi <= 32:
                    score += 25
                elif curr_rsi <= 42:
                    score += 15
                elif curr_rsi >= 70:
                    score -= 40  # Overbought penalty
                
                # 3. MACD Momentum (+25 pts)
                macd_ok = curr_macd > curr_sig
                if macd_ok: score += 25
                
                # 4. Volume Confirmation (+25 pts)
                vol_ok = curr_vol > (curr_vol_sma * 1.2)
                if vol_ok: score += 25
                
                # Prevent negative display scores
                final_score = max(0, min(100, score))
                
                # Absolute Circuit Breakers
                if curr_rsi >= 75:
                    verdict = "🔴 PASS (Overbought Exhaustion)"
                elif final_score >= 70 and curr_rsi <= 45:
                    verdict = "🟢 GRADE-A BUY (Confirmed Pullback)"
                elif final_score >= 50:
                    verdict = "🟡 WATCHLIST (Forming Setup)"
                else:
                    verdict = "🔴 PASS (Weak Edge / No Setup)"
                
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
        results_df = pd.DataFrame(results)
        st.dataframe(results_df, use_container_width=True, hide_index=True)
