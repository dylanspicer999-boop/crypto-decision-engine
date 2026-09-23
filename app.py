import streamlit as st
import requests
import pandas as pd
import time

# --- UI Setup ---
st.set_page_config(page_title="Apex Crypto Terminal", page_icon="🏛️", layout="wide")
st.title("🏛️ Apex Crypto Terminal")
st.markdown("Live Institutional Confluence Matrix | Dual-Engine Divergence Filter")

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
                
                if len(df) < 50:
                    continue
                
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
                
                # --- FIX 1: CLOSED CANDLE LOCK (iloc[-2]) ---
                # We stop evaluating the live bouncing candle and only look at history
                closed_p = df['price'].iloc[-2]
                closed_sma = df['SMA_50'].iloc[-2]
                closed_vol = df['volume'].iloc[-2]
                closed_vol_sma = df['Vol_SMA_20'].iloc[-2]
                closed_rsi = df['RSI_14'].iloc[-2]
                closed_macd = df['MACD'].iloc[-2]
                closed_sig = df['MACD_Signal'].iloc[-2]
                
                # --- FIX 2: BULLISH DIVERGENCE DETECTION ---
                # Find the lowest price over the previous 30 hours
                past_30 = df.iloc[-32:-2]
                lowest_idx = past_30['price'].idxmin()
                past_low_p = past_30.loc[lowest_idx, 'price']
                past_low_rsi = past_30.loc[lowest_idx, 'RSI_14']
                
                # Divergence Logic: Lower price, but higher RSI
                is_divergence = (closed_p < past_low_p) and (closed_rsi > past_low_rsi) and (closed_rsi < 45)
                
                # --- CALIBRATED CONFLUENCE MATRIX ---
                score = 0
                
                # 1. Macro Trend (+25 pts)
                trend_ok = closed_p > closed_sma
                if trend_ok: score += 25
                
                # 2. Reversal / Pullback
                if is_divergence:
                    score += 40  # Massive bonus for catching sellers exhausting
                elif closed_rsi <= 32:
                    score += 25
                elif closed_rsi <= 42:
                    score += 15
                elif closed_rsi >= 70:
                    score -= 40  # Overbought penalty
                
                # 3. MACD Momentum (+25 pts)
                macd_ok = closed_macd > closed_sig
                if macd_ok: score += 25
                
                # 4. Volume Confirmation (+25 pts)
                vol_ok = closed_vol > (closed_vol_sma * 1.2)
                if vol_ok: score += 25
                
                final_score = max(0, min(100, score))
                
                # Verdict Generator
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
