import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
from concurrent.futures import ThreadPoolExecutor

# 페이지 설정
st.set_page_config(page_title="비트겟 스캐너 (바이낸스 차트 연동)", layout="wide")

# --- 메인 헤더 영역 ---
st.title("🛡️ 코인 폭락 타점 & 신뢰도 스캐너")
st.markdown("🔍 필터: `1H RSI < 25` & `ADX >= 30` + `4H RSI 중첩 분석` (차트: 바이낸스 연동)")

# 버튼을 상단에 배치
run_button = st.button('🚀 실시간 전수 조사 및 신뢰도 분석 시작', use_container_width=True)

st.divider()

# 비트겟 연결 (데이터 소스)
exchange = ccxt.bitget({'options': {'defaultType': 'swap'}, 'enableRateLimit': True})

def analyze_symbol(symbol):
    try:
        # 1시간 봉 데이터 수집
        ohlcv_1h = exchange.fetch_ohlcv(symbol, '1h', limit=50)
        if len(ohlcv_1h) < 30: return None
        
        df = pd.DataFrame(ohlcv_1h, columns=['time','open','high','low','close','volume'])
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_df.iloc[:, 0]
        df['plus_di'] = adx_df.iloc[:, 1]
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['vol_avg'] = df['volume'].rolling(window=20).mean()
        
        last_1h = df.iloc[-1]
        
        # 필터 조건
        if (not pd.isna(last_1h['rsi']) and last_1h['rsi'] < 25 and 
            last_1h['plus_di'] >= 40 and last_1h['adx'] >= 30):
            
            # 4시간 봉 RSI
            ohlcv_4h = exchange.fetch_ohlcv(symbol, '4h', limit=30)
            df_4h = pd.DataFrame(ohlcv_4h, columns=['time','open','high','low','close','volume'])
            rsi_4h = ta.rsi(df_4h['close'], length=14).iloc[-1]
            
            # 신뢰도 계산
            r1 = last_1h['rsi']
            r4 = rsi_4h if not pd.isna(rsi_4h) else 50
            vol_ratio = last_1h['volume'] / last_1h['vol_avg']
            
            rating = "⭐⭐⭐" 
            if r1 < 20 and r4 < 25: rating = "⭐⭐⭐⭐⭐" 
            elif r4 < 30: rating = "⭐⭐⭐⭐" 
            if vol_ratio >= 2.0: rating += " (🔥)"

            # 코인명 정리 (예: BTCUSDT)
            clean_name = symbol.split(':')[0].replace('/', '')
            
            # [수정] 바이낸스 선물 차트 링크로 변경
            binance_url = f"https://www.tradingview.com/chart/?symbol=BINANCE:{clean_name}.P"
            
            tp = last_1h['close'] + (last_1h['atr'] * 2)
            sl = last_1h['close'] - (last_1h['atr'] * 2)
            
            return {
                "신뢰도": rating,
                "코인명": clean_name,
                "현재가": last_1h['close'],
                "1H RSI": round(r1, 2),
                "4H RSI": round(r4, 2),
                "ADX": round(last_1h['adx'], 2),
                "거래량비율": f"{vol_ratio:.2f}x",
                "바이낸스차트": binance_url, # 컬럼명 변경
                "익절가(TP)": f"{tp:.4f}",
                "손절가(SL)": f"{sl:.4f}"
            }
    except:
        return None

# 실행 로직
if run_button:
    try:
        markets = exchange.load_markets()
        symbols = [s for s, m in markets.items() if m.get('linear') and m.get('quote') == 'USDT' and m.get('active')]
        
        with st.spinner('바이낸스 차트 동기화 및 전수 조사 중...'):
            with ThreadPoolExecutor(max_workers=25) as executor:
                futures = list(executor.map(analyze_symbol, symbols))
                results = [r for r in futures if r is not None]
        
        if results:
            final_df = pd.DataFrame(results)
            final_df = final_df.sort_values(by="신뢰도", ascending=False)
            
            st.success(f"✅ {len(results)}개의 타점 포착!")

            def highlight_high_rating(row):
                if "⭐⭐⭐⭐⭐" in row['신뢰도']:
                    return ['background-color: #701b1b; color: white'] * len(row)
                elif "⭐⭐⭐⭐" in row['신뢰도']:
                    return ['background-color: #4a1d1d; color: white'] * len(row)
                return [''] * len(row)

            st.dataframe(
                final_df.style.apply(highlight_high_rating, axis=1),
                column_config={
                    "바이낸스차트": st.column_config.LinkColumn("바이낸스 차트", display_text="열기")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("현재 조건에 부합하는 코인이 없습니다.")
            
    except Exception as e:
        st.error(f"오류 발생: {e}")

st.divider()
st.caption("참고: 가격 데이터는 비트겟 기준이며, 차트는 바이낸스 선물(Perpetual) 기준으로 연결됩니다.")
