import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 바이낸스 연결 (GitHub 지역 제한 우회 설정)
# =====================================================

# GitHub Actions 환경인지 확인 (환경변수 'GITHUB_ACTIONS'는 깃허브에서 자동 제공함)
is_github_action = os.getenv('GITHUB_ACTIONS') == 'true'

if is_github_action:
    # GitHub 환경일 때만 우회 주소 사용
    exchange = ccxt.binance({
        "options": {"defaultType": "future"},
        "enableRateLimit": True,
        "urls": {
            "api": {
                "public": "https://fapi.binance.com/fapi/v1",  # 경로를 정확히 v1까지 지정
                "private": "https://fapi.binance.com/fapi/v1",
            }
        }
    })
    print("🌐 Running on GitHub Actions: Using fapi endpoint")
else:
    # 로컬 환경에서는 원래대로 접속
    exchange = ccxt.binance({
        "options": {"defaultType": "future"},
        "enableRateLimit": True
    })
    print("🏠 Running on Local: Using default endpoint")

# =====================================================
# 이하 로직은 사용자님의 성공한 로컬 코드와 동일하게 유지
# =====================================================

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
    except Exception as e:
        print("⚠️ Telegram 에러:", e)

def get_symbols():
    try:
        markets = exchange.load_markets()
        return [s for s in markets if markets[s]["contract"] and markets[s]["quote"] == "USDT" and markets[s]["active"]]
    except Exception as e:
        print("❌ 마켓 로드 에러:", e)
        return []

def get_df(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=120)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_data.iloc[:, 0]
        df['plus_di'] = adx_data.iloc[:, 1]
        return df
    except:
        return pd.DataFrame()

def check_signal(symbol):
    global sent_alerts, signal_found
    df = get_df(symbol)
    if len(df) < 50: return

    last = df.iloc[-2]
    prev = df.iloc[-3]
    rsi, plus_di, adx = last['rsi'], last['plus_di'], last['adx']
    v_now, v_prev = last['volume'], prev['volume']

    if pd.isna(rsi) or pd.isna(plus_di) or pd.isna(adx): return

    if rsi < 30 and plus_di > 36 and adx > 20 and v_now > v_prev:
        now = time.time()
        if symbol in sent_alerts and now - sent_alerts[symbol] < 3600: return
        sent_alerts[symbol] = now
        msg = f"🚀 SIGNAL FOUND\n\n코인 : {symbol}\n가격 : {last['close']}\n\nRSI : {round(rsi, 2)}\n+DI : {round(plus_di, 2)}\nADX : {round(adx, 2)}\nVolume 증가"
        send_telegram(msg)
        signal_found = True

def run_scan():
    global signal_found
    signal_found = False
    print(f"===== SCAN START (UTC: {datetime.now(timezone.utc)}) =====")
    symbols = get_symbols()
    print("SCAN COINS:", len(symbols))

    for i, symbol in enumerate(symbols):
        try:
            check_signal(symbol)
            if i % 15 == 0: time.sleep(0.1)
        except: continue

    if not signal_found:
        send_telegram("🔍 현재 조건에 맞는 코인이 없습니다.")
    print("===== SCAN END =====")

if __name__ == "__main__":
    run_scan()
