import ccxt
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 설정 및 환경 변수 로드
# =====================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# 바이낸스 선물 연결
exchange = ccxt.binance({
    "options": {"defaultType": "future"},
    "enableRateLimit": True
})

# 실행 시 중복 방지를 위한 변수 (단일 실행 세션 내에서 사용)
sent_alerts = {}
signal_found = False

def send_telegram(msg):
    """텔레그램 메시지 전송 함수"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"⚠️ 설정 오류: {msg}")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Telegram 전송 실패: {response.text}")
    except Exception as e:
        print(f"⚠️ Telegram 요청 에러: {e}")

def get_symbols():
    """USDT 선물 마켓의 활성화된 심볼 목록 가져오기"""
    try:
        markets = exchange.load_markets()
        return [
            s for s, m in markets.items() 
            if m.get("contract") and m.get("quote") == "USDT" and m.get("active")
        ]
    except Exception as e:
        print(f"❌ 마켓 정보 로드 실패: {e}")
        return []

def get_df(symbol):
    """캔들 데이터 수집 및 지표 계산"""
    try:
        # 1시간 봉 120개 수집
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=120)
        if not ohlcv:
            return None

        df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # RSI 계산 (14)
        df['rsi'] = RSIIndicator(df['close'], window=14).rsi()

        # ADX 및 +DI 계산 (14)
        adx_indicator = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
        df['adx'] = adx_indicator.adx()
        df['plus_di'] = adx_indicator.adx_pos()

        return df
    except Exception:
        return None

def check_signal(symbol):
    """신호 조건 체크 및 알림"""
    global signal_found
    
    df = get_df(symbol)
    if df is None or len(df) < 50:
        return

    # 마지막 확정 봉 (현재 진행 중인 봉 제외)
    last = df.iloc[-2]
    prev = df.iloc[-3]

    rsi = last['rsi']
    plus_di = last['plus_di']
    adx = last['adx']
    volume_now = last['volume']
    volume_prev = prev['volume']

    # 데이터 결측치 확인
    if pd.isna(rsi) or pd.isna(plus_di) or pd.isna(adx):
        return

    # --- 전략 조건 설정 ---
    # 1. RSI 30 미만 (과매도 영역 근처)
    # 2. +DI 36 초과 (상승 강도 강함)
    # 3. ADX 20 초과 (추세 형성 중)
    # 4. 전 봉 대비 거래량 증가
    if rsi < 30 and plus_di > 36 and adx > 20 and volume_now > volume_prev:
        price = last['close']
        msg = (
            f"🚀 [SIGNAL FOUND]\n\n"
            f"코인 : {symbol}\n"
            f"가격 : {price}\n"
            f"RSI : {round(rsi, 2)}\n"
            f"+DI : {round(plus_di, 2)}\n"
            f"ADX : {round(adx, 2)}\n"
            f"결과 : 거래량 동반 반등 가능성"
        )
        send_telegram(msg)
        signal_found = True

def run_scan():
    """메인 스캔 프로세스"""
    global signal_found
    
    print(f"===== 스캔 시작: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} (UTC) =====")
    
    symbols = get_symbols()
    print(f"대상 코인 수: {len(symbols)}")

    for i, symbol in enumerate(symbols):
        try:
            check_signal(symbol)
            # 바이낸스 API 부하 방지 (0.1초 대기)
            if i % 10 == 0:
                time.sleep(0.1)
        except Exception as e:
            print(f"에러 ({symbol}): {e}")

    if not signal_found:
        send_telegram("🔍 현재 조건에 일치하는 코인이 없습니다.")
        print("결과: 조건 일치 코인 없음")

    print("===== 스캔 종료 =====")

if __name__ == "__main__":
    run_scan()
