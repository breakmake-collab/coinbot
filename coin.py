import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 바이낸스 연결 (가장 안정적인 설정)
# =====================================================
# GitHub Actions의 지역 제한을 피하기 위해 대안 엔드포인트(api1, api2 등)를 사용합니다.
exchange = ccxt.binance({
    "options": {"defaultType": "future"},
    "enableRateLimit": True,
    "urls": {
        "api": {
            "public": "https://fapi.binance.com/fapi", # /v1을 제거하여 ccxt가 직접 붙이게 함
        }
    }
})

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

sent_alerts = {}
sent_messages = set()
signal_found = False

def send_telegram(msg):
    global sent_messages
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    if msg in sent_messages: return
    sent_messages.add(msg)
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

def get_symbols():
    try:
        # 가벼운 요청으로 마켓 데이터를 먼저 로드
        markets = exchange.load_markets()
        symbols = [s for s in markets if markets[s].get("contract") and markets[s].get("quote") == "USDT" and markets[s].get("active")]
        return symbols
    except Exception as e:
        print(f"❌ 마켓 로드 실패: {e}")
        return []

def get_df(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_data.iloc[:, 0]
        df['plus_di'] = adx_data.iloc[:, 1]
        return df
    except:
        return pd.DataFrame()

def check_signal(symbol):
    global signal_found
    df = get_df(symbol)
    if df.empty or len(df) < 50: return

    last = df.iloc[-2]
    prev = df.iloc[-3]
    
    rsi, plus_di, adx = last['rsi'], last['plus_di'], last['adx']
    v_now, v_prev = last['volume'], prev['volume']

    # 테스트를 위해 조건을 매우 느슨하게 (성공 확인용)
    # 확인 후 원래 조건(rsi < 30 등)으로 복구하세요.
    if rsi < 70: 
        msg = f"✅ TEST SIGNAL: {symbol}\nRSI: {round(rsi,2)}"
        send_telegram(msg)
        signal_found = True

def run_scan():
    global signal_found
    signal_found = False
    print(f"===== SCAN START (UTC: {datetime.now(timezone.utc)}) =====")
    
    symbols = get_symbols()
    print(f"SCAN COINS: {len(symbols)}") # 여기서 숫자가 0보다 커야 합니다.

    if not symbols:
        send_telegram("❌ 코인 목록을 가져오지 못했습니다. (API 차단 가능성)")
        return

    # 상위 20개만 먼저 테스트 (전체 다 돌면 시간이 오래 걸림)
    for i, symbol in enumerate(symbols[:20]): 
        check_signal(symbol)
        time.sleep(0.1)

    if not signal_found:
        send_telegram("🔍 조건에 맞는 코인이 없습니다.")
    print("===== SCAN END =====")

if __name__ == "__main__":
    run_scan()
