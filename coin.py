import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 바이비트(Bybit) 연결 설정
# =====================================================
# 바이비트는 GitHub Actions 서버 IP를 차단하지 않아 별도의 우회 주소가 필요 없습니다.
exchange = ccxt.bybit({
    'options': {'defaultType': 'linear'}, # USDT 무기한 선물(Linear Swap)
    'enableRateLimit': True,
})

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

sent_alerts = {}
sent_messages = set()
signal_found = False

def send_telegram(msg):
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
    """바이비트 USDT 선물 종목 리스트 가져오기"""
    try:
        markets = exchange.load_markets()
        # 바이비트 선물 종목 중 USDT로 결제되는 활성화된 종목만 필터링
        symbols = [
            s for s in markets 
            if s.endswith(':USDT') and markets[s].get('active')
        ]
        return symbols
    except Exception as e:
        print(f"❌ 종목 로드 실패: {e}")
        return []

def get_df(symbol):
    """캔들 데이터 수집 및 지표 계산"""
    try:
        # 바이비트 1시간봉 100개 데이터
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        if not ohlcv:
            return pd.DataFrame()
            
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # RSI (14)
        df['rsi'] = ta.rsi(df['close'], length=14)

        # ADX / +DI (14)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        # Bybit 데이터에 맞춘 인덱스 접근 (0: ADX, 1: +DI)
        df['adx'] = adx_df.iloc[:, 0]    
        df['plus_di'] = adx_df.iloc[:, 1] 
        
        return df
    except Exception:
        return pd.DataFrame()

def check_signal(symbol):
    """사용자 오리지널 조건 체크"""
    global sent_alerts, signal_found
    df = get_df(symbol)

    if df.empty or len(df) < 50:
        return

    # 확정된 직전 봉 (-2)
    last = df.iloc[-2]
    prev = df.iloc[-3]

    rsi = last['rsi']
    plus_di = last['plus_di']
    adx = last['adx']
    v_now = last['volume']
    v_prev = prev['volume']

    if pd.isna(rsi) or pd.isna(plus_di) or pd.isna(adx):
        return

    # 조건: RSI < 30, +DI > 36, ADX > 20, 거래량 증가
    if rsi < 30 and plus_di > 36 and adx > 20 and v_now > v_prev:
        now = time.time()
        # 동일 종목 1시간 내 중복 알림 방지
        if symbol in sent_alerts and now - sent_alerts[symbol] < 3600:
            return
        sent_alerts[symbol] = now

        # 바이비트 종목명에서 ':USDT' 부분 제거하고 가독성 높이기
        clean_symbol = symbol.replace(':USDT', '')
        
        msg = (
            f"🚀 [BYBIT SIGNAL]\n\n"
            f"코인 : {clean_symbol}\n"
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
    print(f"===== BYBIT SCAN START (UTC): {start_time} =====")
    
    symbols = get_symbols()
    print(f"대상 종목 수: {len(symbols)}")

    for i, symbol in enumerate(symbols):
        try:
            check_signal(symbol)
            # API 과부하 방지
            if i % 20 == 0:
                time.sleep(0.1)
        except Exception as e:
            print(f"ERROR ({symbol}): {e}")
            
    if not signal_found:
        send_telegram("🔍 현재 바이비트 조건 일치 종목 없음")
        print("결과: 일치 종목 없음")

    print("===== SCAN END =====")

if __name__ == "__main__":
    run_scan()
