import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
from concurrent.futures import ThreadPoolExecutor

# 페이지 설정
st.set_page_config(page_title="VIP SCANNER", layout="centered")

# 아이폰 17 가로 폭에 최적화된 CSS
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    h1 { font-size: 1.1rem !important; text-align: center; margin-bottom: 15px; color: #00f0ff; }
    
    /* 한 줄 지표 레이아웃 */
    .status-container {
        display: flex;
        justify-content: space-between;
        background: #1e2129;
        padding: 10px 5px;
        border-radius: 10px;
        margin-bottom: 15px;
        border: 1px solid #3e424b;
    }
    .status-item {
        text-align: center;
        flex: 1;
        border-right: 1px solid #3e424b;
    }
    .status-item:last-child { border-right: none; }
    .status-label { font-size: 0.65rem; color: #848e9c; display: block; }
    .status-value { font-size: 0.85rem; font-weight: bold; color: #ffffff; }

    /* 지표 설명 가이드 스타일 */
    .info-guide {
        background-color: #16191f;
        padding: 12px;
        border-radius: 8px;
        border-left: 3px solid #00f0ff;
        margin-bottom: 15px;
    }
    .info-title { font-size: 0.75rem; font-weight: bold; color: #00f0ff; margin-bottom: 6px; display: block; }
    .info-item { font-size: 0.68rem; color: #d1d4dc; line-height: 1.5; display: block; margin-bottom: 2px; }

    .stButton>button { 
        height: 3.2em; font-size: 0.85rem; border-radius: 8px;
        background-color: #00f0ff; color: black; font-weight: bold; margin-top: 5px;
    }
    .guide-text { font-size: 0.7rem; color: #d1d4dc; padding: 8px; background: #1e2129; border-radius: 5px; margin-bottom: 10px; }
    .stDataFrame { font-size: 0.7rem !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 사이드바 설정 (4H RSI 기본값을 35로 변경) ---
st.sidebar.header("⚙️ CONFIG")
rsi_1h_limit = st.sidebar.number_input("1H RSI 미만", 1, 100, 30)
rsi_4h_limit = st.sidebar.number_input("4H RSI 이하", 1, 100, 35) # 기준 35로 수정
adx_limit = st.sidebar.number_input("Min ADX", 1, 100, 25)
di_limit = st.sidebar.number_input("Min +DI", 1, 100, 36)

# --- 메인 화면 ---
st.title("🛡️ 바이낸스 롱 포지션 전용")

# 1. 아이폰 한 줄 배치 커스텀 HTML
st.markdown(f"""
<div class="status-container">
    <div class="status-item">
        <span class="status-label">1H RSI</span>
        <span class="status-value">< {rsi_1h_limit}</span>
    </div>
    <div class="status-item">
        <span class="status-label">4H RSI</span>
        <span class="status-value">≤ {rsi_4h_limit}</span>
    </div>
    <div class="status-item">
        <span class="status-label">ADX</span>
        <span class="status-value">≥ {adx_limit}</span>
    </div>
    <div class="status-item">
        <span class="status-label">+DI</span>
        <span class="status-value">> {di_limit}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# 2. 지표 간략 설명 가이드
st.markdown("""
<div class="info-guide">
    <span class="info-title">📊 지표 이해하기</span>
    <span class="info-item">• <b>RSI:</b> 30미만은 과하게 팔린 '과매도' 상태로 반등 확률이 높습니다.</span>
    <span class="info-item">• <b>ADX:</b> 추세의 세기입니다. 25이상이면 하락 압력이 매우 강함을 뜻합니다.</span>
    <span class="info-item">• <b>+DI:</b> 매수 에너지입니다. 36초과 시 하락 중에도 튀어오를 힘이 큽니다.</span>
    <span class="info-item">• <b>🔮다이버:</b> 가격은 낮아지나 지표는 올라가는 '추세 반전' 신호입니다.</span>
    <span class="info-item">• <b>✅진입:</b> 5분봉이 이평선 위로 고개를 든 최종 매수 타이밍입니다.</span>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="guide-text">
    <b>💡 신호:</b> 🔮다이버 | ✅진입 가능 | ⏳ 대기
</div>
""", unsafe_allow_html=True)

run_button = st.button('🚀 비트겟 전 종목 전수 조사 시작')

# --- 분석 로직 ---
exchange = ccxt.bitget({'options': {'defaultType': 'swap'}, 'enableRateLimit': True})

def analyze_symbol(symbol):
    try:
        ohlcv_1h = exchange.fetch_ohlcv(symbol, '1h', limit=60)
        df_1h = pd.DataFrame(ohlcv_1h, columns=['time','open','high','low','close','volume'])
        df_1h['rsi'] = ta.rsi(df_1h['close'], length=14)
        adx_df = ta.adx(df_1h['high'], df_1h['low'], df_1h['close'], length=14)
        last_1h = df_1h.iloc[-1]
        
        if (not pd.isna(last_1h['rsi']) and last_1h['rsi'] < rsi_1h_limit and 
            adx_df.iloc[-1, 0] >= adx_limit and adx_df.iloc[-1, 1] > di_limit):
            
            ohlcv_4h = exchange.fetch_ohlcv(symbol, '4h', limit=30)
            df_4h = pd.DataFrame(ohlcv_4h, columns=['time','open','high','low','close','volume'])
            rsi_4h = ta.rsi(df_4h['close'], length=14).iloc[-1]
            
            # 4시간 봉 35이하 필터 적용 부분
            if not pd.isna(rsi_4h) and rsi_4h <= rsi_4h_limit:
                diver = ""
                lookback = df_1h.iloc[-15:-2]
                if last_1h['low'] <= lookback['low'].min() * 1.01 and last_1h['rsi'] > lookback['rsi'].min() + 2:
                    diver = "🔮"

                ohlcv_5m = exchange.fetch_ohlcv(symbol, '5m', limit=15)
                df_5m = pd.DataFrame(ohlcv_5m, columns=['time','open','high','low','close','volume'])
                ma10 = df_5m['close'].rolling(window=10).mean().iloc[-1]
                entry = "✅" if df_5m['close'].iloc[-1] > ma10 else "⏳"

                return {
                    "코인": symbol.split(':')[0].replace('/USDT', ''),
                    "1H": round(last_1h['rsi'], 1),
                    "4H": round(rsi_4h, 1),
                    "ADX": round(adx_df.iloc[-1, 0], 1),
                    "+DI": round(adx_df.iloc[-1, 1], 1),
                    "신호": f"{diver}{entry}",
                    "is_vip": True if (diver == "🔮" and entry == "✅") else False
                }
    except: return None
    return None

if run_button:
    try:
        markets = exchange.load_markets()
        symbols = [s for s, m in markets.items() if m.get('linear') and m.get('quote') == 'USDT' and m.get('active')]
        with st.spinner('전 종목 스캔 중...'):
            with ThreadPoolExecutor(max_workers=30) as executor:
                results = [r for r in list(executor.map(analyze_symbol, symbols)) if r is not None]
        
        if results:
            df = pd.DataFrame(results)
            vip = df[df['is_vip'] == True].drop(columns=['is_vip'])
            others = df[df['is_vip'] == False].drop(columns=['is_vip'])

            if not vip.empty:
                st.success("🏆 VIP GOLDEN (지금 바로 확인)")
                st.dataframe(vip, hide_index=True, use_container_width=True)
            else:
                st.warning("⚠️ 현재 조건에 일치하는 VIP 종목이 없습니다.")
            
            if not others.empty:
                st.write("📋 신호 대기 종목")
                st.dataframe(others.sort_values("1H"), hide_index=True, use_container_width=True)
            else:
                st.info("💡 신호 대기 중인 다른 후보군도 없습니다.")
        else:
            st.info("조건 일치 코인 없음")
    except Exception as e:
        st.error(f"오류: {e}")
