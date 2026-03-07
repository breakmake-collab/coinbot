import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 바이비트(Bybit) 설정 - 가장 심플한 접속 방식
# =====================================================
exchange = ccxt.bybit({
    'options': {'defaultType': 'linear'},
    'enableRateLimit': True,
})

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

def get_symbols():
    try:
        # load_markets()가 차단될 경우를 대비해 fetch_tickers() 사용
        tickers = exchange.fetch_tickers()
        # USDT로 끝나는 선물 종목들만 골라내기
        symbols = [s for s in tickers.keys() if s.endswith(':USDT')]
        if not symbols:
            # 주소 형식이 다를 경우를 대비한 2차 필터
            symbols = [s for s in tickers.keys() if s.endswith('USDT')]
        return symbols
    except Exception as e:
        print(f"❌ 종목 리스트 로드 실패: {e}")
        return []

def get_df(symbol):
    try:
        # 1시간봉 100개
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        df['rsi'] = ta.rsi(df['close'], length=14)
        return df
    except:
        return pd.DataFrame()

def run_scan():
    print(f"===== SCAN START (UTC: {datetime.now(timezone.utc)}) =====")
    
    symbols = get_symbols()
    print(f"SCAN COINS: {len(symbols)}") # 👈 이 숫자가 중요합니다!

    if not symbols:
        send_telegram("❌ 종목을 하나도 가져오지 못했습니다. (IP 차단 확률 100%)")
        return

    found_count = 0
    # 상위 30개만 테스트
    for symbol in symbols[:30]:
        df = get_df(symbol)
        if df.empty or len(df) < 50: continue
        
        rsi = df.iloc[-2]['rsi']
        
        # 테스트를 위해 아주 느슨한 조건 (RSI 80 이하)
        if not pd.isna(rsi) and rsi < 80:
            found_count += 1
            print(f"신호 발견: {symbol} (RSI: {rsi})")
            if found_count <= 3: # 텔레그램 도배 방지 (3개만 전송)
                send_telegram(f"✅ 테스트 성공!\n코인: {symbol}\nRSI: {round(rsi, 2)}")

    if found_count == 0:
        send_telegram("🔍 모든 종목을 훑었으나 조건에 맞는 게 없습니다.")
    
    print(f"===== SCAN END (Found: {found_count}) =====")

if __name__ == "__main__":
    run_scan()
