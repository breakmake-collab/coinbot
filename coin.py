import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 설정 및 환경 변수
# =====================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# 바이낸스 연결 - 지역 제한(451 에러) 우회를 위한 fapi 설정
exchange = ccxt.binance({
    "options": {"defaultType": "future"},
    "enableRateLimit": True,
    "urls": {
        "api": {
            "public": "https://fapi.binance.com/fapi",
            "private": "https://fapi.binance.com/fapi",
        }
    }
})

sent_messages = set()
signal_found = False

def send_telegram(msg):
    """텔레그램 메시지 전송 (중복 방지 포함)"""
    global sent_messages
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"⚠️ 설정 미비: {msg}")
        return
    
    if msg in sent_messages:
        return
    sent_messages.add(msg)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Telegram 전송 실패: {response.text}")
    except Exception as e:
        print(f"⚠️ Telegram 에러: {e}")

def get_symbols():
    """선물 USDT 종목 리스트 가져오기"""
    try:
        markets = exchange.load_markets()
        return [
            s for s in markets 
            if markets[s].get("contract") and markets[s].get("quote") == "USDT" and markets[s].get("active")
        ]
    except Exception as e:
        print(f"❌ 마켓 정보 로드 실패: {e}")
        return []

def get_df(symbol):
    """캔들 데이터 수집 및 지표 계산 (pandas_ta 사용)"""
    try:
        # 선물 전용 데이터 1시간봉 120개
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=120)
        if not ohlcv:
            return pd.DataFrame()
            
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # RSI 계산 (14)
        df['rsi'] = ta.rsi(df['close'], length=14)

        # ADX / +DI 계산 (14)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        # pandas_ta의 ADX 결과 컬럼명은 ADX_14, DMP_14, DMN_14 등입니다.
        df['adx'] = adx_df.iloc[:, 0]    # ADX 값
        df['plus_di'] = adx_df.iloc[:, 1]  # +DI 값
        
        return df
    except Exception:
        return pd.DataFrame()

def check_signal(symbol):
    """사용자 조건 체크"""
    global signal_found
    df = get_df(symbol)

    if df.empty or len(df) < 50:
        return

    # 마지막 확정 봉 (-2)
    last = df.iloc[-2]
    prev = df.iloc[-3]

    rsi = last['rsi']
    plus_di = last['plus_di']
    adx = last['adx']
    v_now = last['volume']
    v_prev = prev['volume']

    # 데이터 결측치 예외 처리
    if pd.isna(rsi) or pd.isna(plus_di) or pd.isna(adx):
        return

    # 조건: RSI < 30, +DI > 36, ADX > 20, 거래량 증가
    if rsi < 30 and plus_di > 36 and adx > 20 and v_now > v_prev:
        msg = (
            f"🚀 [SIGNAL FOUND]\n\n"
            f"코인 : {symbol}\n"
            f"가격 : {last['close']}\n\n"
            f"RSI : {round(rsi, 2)}\n"
            f"+DI : {round(plus_di, 2)}\n"
            f"ADX : {round(adx, 2)}\n"
            f"거래량 : 전봉 대비 증가"
        )
        send_telegram(msg)
        signal_found = True

def run_scan():
    """메인 스캔 프로세스"""
    global signal_found
    signal_found = False
    
    start_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    print(f"===== 스캔 시작 (UTC): {start_time} =====")
    
    symbols = get_symbols()
    print(f"대상 종목 수: {len(symbols)}")

    for i, symbol in enumerate(symbols):
        try:
            check_signal(symbol)
            # API 부하 방지
            if i % 20 == 0:
                time.sleep(0.1)
        except Exception as e:
            print(f"ERROR ({symbol}): {e}")
            
    if not signal_found:
        send_telegram("🔍 현재 조건에 맞는 코인이 없습니다.")
        print("결과: 일치 종목 없음")

    print("===== 스캔 종료 =====")

if __name__ == "__main__":
    run_scan()
