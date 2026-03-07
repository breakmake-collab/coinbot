import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 바이낸스 우회 연결 설정 (핵심)
# =====================================================
def get_exchange():
    # 바이낸스에서 공식적으로 제공하는 대체 API 도메인 리스트
    endpoints = [
        "https://fapi.binance.com/fapi",
        "https://fapi1.binance.com/fapi",
        "https://fapi2.binance.com/fapi",
        "https://fapi3.binance.com/fapi"
    ]
    
    for url in endpoints:
        try:
            ex = ccxt.binance({
                "options": {"defaultType": "future"},
                "enableRateLimit": True,
                "urls": {"api": {"public": url}}
            })
            # 연결 테스트: 간단한 서버 시간 요청
            ex.fetch_time() 
            print(f"✅ 연결 성공: {url}")
            return ex
        except Exception as e:
            print(f"❌ 연결 실패 ({url}): {e}")
            continue
    return None

exchange = get_exchange()

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
    if not exchange: return []
    try:
        # fetch_markets 대신 더 가벼운 fetch_tickers로 시도
        tickers = exchange.fetch_tickers()
        return [s for s in tickers if s.endswith('USDT')]
    except Exception as e:
        print(f"❌ 종목 로드 실패: {e}")
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

    # --- 기존 사용자 조건으로 복구 ---
    if rsi < 30 and plus_di > 36 and adx > 20 and v_now > v_prev:
        msg = f"🚀 SIGNAL FOUND\n\n코인 : {symbol}\n가격 : {last['close']}\n\nRSI : {round(rsi, 2)}\n+DI : {round(plus_di, 2)}\nADX : {round(adx, 2)}\nVolume 증가"
        send_telegram(msg)
        signal_found = True

def run_scan():
    global signal_found
    if not exchange:
        send_telegram("❌ 모든 바이낸스 API 서버에 접속할 수 없습니다. (GitHub IP 전면 차단)")
        return

    print(f"===== SCAN START ({datetime.now(timezone.utc)}) =====")
    symbols = get_symbols()
    print(f"SCAN COINS: {len(symbols)}")

    for i, symbol in enumerate(symbols):
        try:
            check_signal(symbol)
            if i % 10 == 0: time.sleep(0.1)
        except: continue

    if not signal_found:
        send_telegram("🔍 조건에 맞는 코인이 없습니다.")
    print("===== SCAN END =====")

if __name__ == "__main__":
    run_scan()
