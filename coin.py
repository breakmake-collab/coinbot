import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 바이비트(Bybit) 설정 (선물 전용으로 강제 고정)
# =====================================================
exchange = ccxt.bybit({
    'options': {
        'defaultType': 'linear',  # 선물 마켓 고정
        'adjustForTimeDifference': True,
    },
    'enableRateLimit': True,
})

# ⚠️ 핵심: 현물(Spot) 데이터를 아예 요청하지 않도록 차단
exchange.options['fetchMarkets'] = ['linear'] 

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

signal_found = False

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

def get_symbols():
    try:
        # fetch_markets() 대신 선물 전용 메서드로 시도
        markets = exchange.fetch_derivatives_markets()
        # USDT 결제 선물만 필터링
        return [m['symbol'] for m in markets if m['linear'] and m['quote'] == 'USDT' and m['active']]
    except Exception as e:
        print(f"Market Load Error: {e}")
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

    if pd.isna(rsi) or pd.isna(plus_di) or pd.isna(adx): return

    if rsi < 30 and plus_di > 36 and adx > 20 and v_now > v_prev:
        msg = f"🚀 [BYBIT SIGNAL]\n코인: {symbol}\n가격: {last['close']}\nRSI: {round(rsi, 2)}\n+DI: {round(plus_di, 2)}\nADX: {round(adx, 2)}"
        send_telegram(msg)
        signal_found = True

def run_scan():
    global signal_found
    print(f"===== SCAN START ({datetime.now(timezone.utc)}) =====")
    symbols = get_symbols()
    print(f"SCAN COINS: {len(symbols)}")

    for i, symbol in enumerate(symbols):
        try:
            check_signal(symbol)
            if i % 10 == 0: time.sleep(0.1)
        except: continue

    if not signal_found:
        send_telegram("🔍 조건 일치 없음")
    print("===== SCAN END =====")

if __name__ == "__main__":
    run_scan()
