import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
from concurrent.futures import ThreadPoolExecutor

# 페이지 설정
st.set_page_config(page_title="VIP SCANNER", layout="centered")

# 스타일 설정 (아이폰 모바일 환경 최적화)
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    h1 { font-size: 1.2rem !important; text-align: center; margin-bottom: 5px; }
    [data-testid="stMetricValue"] { font-size: 0.9rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.7rem !important; }
    .stButton>button { 
        height: 3em; font-size: 0.85rem; border-radius: 8px;
        background-color: #00f0ff; color: black; font-weight: bold;
    }
    .guide-text { font-size: 0.7rem; color: #d1d4dc; padding: 8px; background: #1e2129; border-radius: 5px; margin-bottom: 10px; }
    /* 테이블 텍스트 크기 최소화 (아이폰용) */
    .stDataFrame { font-size: 0.7rem !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 사이드바 설정 ---
st.sidebar.header("⚙️ 필터 설정")
rsi_1h_limit = st.sidebar.number_input("1H RSI 미만", 1, 100, 30)
rsi_4h_limit = st.sidebar.number_input("4H RSI 이하", 1, 100, 30)
adx_limit = st.sidebar.number_input("Min ADX", 1, 100, 25)
di_limit = st.sidebar.number_input("Min +DI", 1, 100, 36)

# --- 메인 화면 ---
st.title("🛡️ BITGET VIP MOBILE")

# 상단 수치 요약
m1, m2, m3, m4 = st.columns(4)
m1.metric("1H", f"<{rsi_1h_limit}")
m2.metric("4H", f"≤{rsi_4h_limit}")
m3.metric("ADX", f"≥{adx_limit}")
m4.metric("+DI", f">{di_limit}")

st.markdown("""
<div class="guide-text">
    <b>💡 신호:</b> 🔮다이버 | ✅진입 | ⚠️ 4H+1H 동시 과매도 종목만 노출
</div>
""", unsafe_allow_html=True)

run_button = st.button('🚀 실시간 통합 스캔 시작')

# --- 분석 로직 ---
exchange = ccxt.bitget({'options': {'defaultType': 'swap'}, 'enableRateLimit': True})

def analyze_symbol(symbol):
    try:
        # 1. 1시간 봉 데이터
        ohlcv_1h = exchange.fetch_ohlcv(symbol, '1h', limit=60)
        df_1h = pd.DataFrame(ohlcv_1h, columns=['time','open','high','low','close','volume'])
        df_1h['rsi'] = ta.rsi(df_1h['close'], length=14)
        adx_df = ta.adx(df_1h['high'], df_1h['low'], df_1h['close'], length=14)
        last_1h = df_1h.iloc[-1]
        
        # 기본 필터 조건 (1H RSI, ADX, +DI)
        if (not pd.isna(last_1h['rsi']) and last_1h['rsi'] < rsi_1h_limit and 
            adx_df.iloc[-1, 0] >= adx_limit and adx_df.iloc[-1, 1] > di_limit):
            
            # 2. 4시간 봉 데이터
            ohlcv_4h = exchange.fetch_ohlcv(symbol, '4h', limit=30)
            df_4h = pd.DataFrame(ohlcv_4h, columns=['time','open','high','low','close','volume'])
            rsi_4h = ta.rsi(df_4h['close'], length=14).iloc[-1]
            
            # 4시간 봉 과매도 조건 체크
            if not pd.isna(rsi_4h) and rsi_4h <= rsi_4h_limit:
                
                # 3. 다이버전스 & 5분봉 체크
                diver = ""
                lookback = df_1h.iloc[-15:-2]
                if last_1h['low'] <= lookback['low'].min() * 1.01 and last_1h['rsi'] > lookback['rsi'].min() + 2:
                    diver = "🔮"

                ohlcv_5m = exchange.fetch_ohlcv(symbol, '5m', limit=15)
                df_5m = pd.DataFrame(ohlcv_5m, columns=['time','open','high','low','close','volume'])
                ma10 = df_5m['close'].rolling(window=10).mean().iloc[-1]
                entry = "✅" if df_5m['close'].iloc[-1] > ma10 else "⏳"

                # 결과 데이터 구성 (요청하신 수치들 포함)
                return {
                    "코인": symbol.split(':')[0].replace('/USDT', ''),
                    "1H": round(last_1h['rsi'], 1),
                    "4H": round(rsi_4h, 1),
                    "ADX": round(adx_df.iloc[-1, 0], 1),
                    "+DI": round(adx_df.iloc[-1, 1], 1),
                    "신호": f"{diver}{entry}"
                }
    except: return None
    return None

if run_button:
    try:
        markets = exchange.load_markets()
        symbols = [s for s, m in markets.items() if m.get('linear') and m.get('quote') == 'USDT' and m.get('active')]
        with st.spinner('조회중...'):
            with ThreadPoolExecutor(max_workers=30) as executor:
                results = [r for r in list(executor.map(analyze_symbol, symbols)) if r is not None]
        
        if results:
            df = pd.DataFrame(results)
            
            # VIP 섹션 (다이버 + 진입)
            vip = df[df['신호'].str.contains("🔮") & df['신호'].str.contains("✅")]
            if not vip.empty:
                st.info("🏆 VIP GOLDEN")
                st.dataframe(vip, hide_index=True, use_container_width=True)
            
            st.write("📋 분석 결과 (1H RSI순)")
            # 1H RSI 낮은 순으로 정렬하여 수치 확인 용이하게 구성
            st.dataframe(df.sort_values("1H"), hide_index=True, use_container_width=True)
        else:
            st.info("조건 일치 코인 없음")
    except Exception as e:
        st.error(f"오류: {e}")
