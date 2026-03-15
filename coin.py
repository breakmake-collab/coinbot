import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
from concurrent.futures import ThreadPoolExecutor

# 페이지 설정
st.set_page_config(page_title="BITGET VIP GOLDEN SCANNER", layout="wide")

# 스타일 설정
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2129; padding: 15px; border-radius: 10px; border: 1px solid #3e424b; }
    .vip-box { 
        background-color: #1a1a1a; 
        border: 2px solid #00f0ff; 
        padding: 25px; 
        border-radius: 15px; 
        margin-bottom: 25px;
        box-shadow: 0px 4px 15px rgba(0, 240, 255, 0.2);
    }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #00f0ff; color: black; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 사이드바 필터 설정 (수치 고정) ---
st.sidebar.header("⚙️ STRATEGY SETTINGS")

with st.sidebar.expander("📉 RSI THRESHOLD", expanded=True):
    rsi_1h_threshold = st.sidebar.number_input("1H RSI 이하", 1, 100, 30)
    rsi_4h_threshold = st.sidebar.number_input("4H RSI 이하", 1, 100, 30)

with st.sidebar.expander("⚡ MOMENTUM & TREND", expanded=True):
    adx_threshold = st.sidebar.number_input("Min ADX (추세강도)", 1, 100, 25)
    plus_di_threshold = st.sidebar.number_input("Min +DI (에너지)", 1, 100, 36)

# --- 메인 헤더 ---
st.title("🛡️ BITGET VIP 골든 스캐너")
st.caption("비트겟 전용: RSI < 30, ADX ≥ 25, +DI > 36 + 다이버전스 + 5분봉 돌파")

m1, m2, m3, m4 = st.columns(4)
m1.metric("1H RSI Limit", f"< {rsi_1h_threshold}")
m2.metric("4H RSI Limit", f"≤ {rsi_4h_threshold}")
m3.metric("Min ADX", f"≥ {adx_threshold}")
m4.metric("Min +DI", f"> {plus_di_threshold}")

st.divider()

run_button = st.button('🚀 비트겟 마켓 전수 조사 시작')

# --- [비트겟 연결 설정] ---
exchange = ccxt.bitget({'options': {'defaultType': 'swap'}, 'enableRateLimit': True})

def analyze_symbol(symbol):
    try:
        # 비트겟 데이터 수집
        ohlcv_1h = exchange.fetch_ohlcv(symbol, '1h', limit=80)
        if len(ohlcv_1h) < 40: return None
        
        df = pd.DataFrame(ohlcv_1h, columns=['time','open','high','low','close','volume'])
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_df.iloc[:, 0]
        df['plus_di'] = adx_df.iloc[:, 1]
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['vol_avg'] = df['volume'].rolling(window=20).mean()
        
        last_1h = df.iloc[-1]
        
        # [VIP 필터 조건 체크]
        if (not pd.isna(last_1h['rsi']) and last_1h['rsi'] < rsi_1h_threshold and 
            last_1h['adx'] >= adx_threshold and last_1h['plus_di'] > plus_di_threshold):
            
            # 4시간 봉 확인
            ohlcv_4h = exchange.fetch_ohlcv(symbol, '4h', limit=30)
            df_4h = pd.DataFrame(ohlcv_4h, columns=['time','open','high','low','close','volume'])
            rsi_4h = ta.rsi(df_4h['close'], length=14).iloc[-1]
            
            if not pd.isna(rsi_4h) and rsi_4h <= rsi_4h_threshold:
                
                # 다이버전스 체크
                diver_signal = ""
                lookback_df = df.iloc[-20:-3] 
                if not lookback_df.empty:
                    prev_min_low = lookback_df['low'].min()
                    prev_min_rsi = lookback_df['rsi'].min()
                    # 가격은 낮거나 비슷한데 RSI는 높은지
                    if last_1h['low'] <= prev_min_low * 1.01 and last_1h['rsi'] > prev_min_rsi + 2:
                        diver_signal = "🔮다이버"

                # 5분 봉 진입 신호
                ohlcv_5m = exchange.fetch_ohlcv(symbol, '5m', limit=20)
                df_5m = pd.DataFrame(ohlcv_5m, columns=['time','open','high','low','close','volume'])
                ma10_5m = df_5m['close'].rolling(window=10).mean().iloc[-1]
                current_price = df_5m['close'].iloc[-1]
                
                entry_signal = "⏳ 대기"
                if current_price > ma10_5m:
                    entry_signal = "✅ 진입가능"

                r1 = last_1h['rsi']
                vol_ratio = last_1h['volume'] / last_1h['vol_avg']
                
                # 신뢰도 별점
                rating = "⭐⭐⭐" 
                if r1 < 20 and rsi_4h < 25: rating = "⭐⭐⭐⭐⭐" 
                elif r1 < 22 or rsi_4h < 28: rating = "⭐⭐⭐⭐" 
                
                clean_name = symbol.split(':')[0].replace('/', '').split(':')[0]
                
                return {
                    "신뢰도": rating,
                    "코인명": clean_name,
                    "현재가": current_price,
                    "1H RSI": round(r1, 1),
                    "4H RSI": round(rsi_4h, 1),
                    "다이버전스": diver_signal,
                    "5분봉신호": entry_signal,
                    "ADX": round(last_1h['adx'], 1),
                    "+DI": round(last_1h['plus_di'], 1),
                    "거래량비율": f"{vol_ratio:.2f}x",
                    "익절가(TP)": f"{current_price + (last_1h['atr'] * 2):.4f}",
                    "손절가(SL)": f"{current_price - (last_1h['atr'] * 2):.4f}"
                }
    except:
        return None
    return None

if run_button:
    try:
        markets = exchange.load_markets()
        # 비트겟 선물 심볼 필터링
        symbols = [s for s, m in markets.items() if m.get('linear') and m.get('quote') == 'USDT' and m.get('active')]
        
        with st.spinner('🎯 비트겟 마켓 전수 조사 중...'):
            with ThreadPoolExecutor(max_workers=30) as executor:
                futures = list(executor.map(analyze_symbol, symbols))
                results = [r for r in futures if r is not None]
        
        if results:
            final_df = pd.DataFrame(results)
            
            # --- VIP 골든 타점 섹션 ---
            vip_targets = final_df[
                (final_df['다이버전스'] == "🔮다이버") & 
                (final_df['5분봉신호'] == "✅ 진입가능")
            ]
            
            if not vip_targets.empty:
                st.markdown('<div class="vip-box"><h2>🏆 VIP 골든 타점 (전 조건 일치)</h2>', unsafe_allow_html=True)
                st.dataframe(vip_targets, hide_index=True, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("💡 모든 조건을 만족하는 골든 타점이 없습니다. 하단 리스트를 확인하세요.")
            
            # 전체 리스트
            st.subheader("📋 실시간 전체 분석 리스트")
            final_df = final_df.sort_values(by=["신뢰도", "1H RSI"], ascending=[False, True])

            def style_df(row):
                if "⭐⭐⭐⭐⭐" in row['신뢰도']:
                    return ['background-color: #701b1b; color: white'] * len(row)
                elif "⭐⭐⭐⭐" in row['신뢰도']:
                    return ['background-color: #4a1d1d; color: white'] * len(row)
                elif row['5분봉신호'] == "✅ 진입가능":
                    return ['background-color: #002b1b; color: #ccffcc'] * len(row)
                return [''] * len(row)

            st.dataframe(final_df.style.apply(style_df, axis=1), hide_index=True, use_container_width=True)
        else:
            st.info("💡 조건에 맞는 종목이 없습니다.")
            
    except Exception as e:
        st.error(f"⚠️ 오류 발생: {e}")

st.divider()
st.caption("Bitget Futures Scanner | 한국 IP에서 안정적으로 작동합니다.")
