# =====================================================
# 필요한 라이브러리
# pip install ccxt pandas pandas_ta requests
# =====================================================

import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

print("===== CRYPTO SIGNAL BOT START =====")

# =====================================================
# 바이낸스 연결 (선물)
# =====================================================

exchange = ccxt.binance({
    "options": {"defaultType": "future"},
    "enableRateLimit": True
})

# =====================================================
# 텔레그램 정보 (환경변수)
# =====================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

sent_alerts = {}
sent_messages = set()
signal_found = False

# =====================================================
# 텔레그램 메시지 보내기
# =====================================================

def send_telegram(msg):

    global sent_messages

    if msg in sent_messages:
        return

    sent_messages.add(msg)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": msg
    }

    requests.post(url, data=data)

# =====================================================
# 선물 전체 코인 불러오기
# =====================================================

def get_symbols():

    markets = exchange.load_markets()

    symbols = []

    for s in markets:

        market = markets[s]

        if market["contract"] and market["quote"] == "USDT" and market["active"]:
            symbols.append(s)

    return symbols

# =====================================================
# 캔들 데이터 + 지표 계산
# =====================================================

def get_df(symbol):

    ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=120)

    df = pd.DataFrame(
        ohlcv,
        columns=['time','open','high','low','close','volume']
    )

    df['rsi'] = ta.rsi(df['close'], length=14)

    adx = ta.adx(df['high'], df['low'], df['close'], length=14)

    df['adx'] = adx.iloc[:,0]      # ADX 값
    df['plus_di'] = adx.iloc[:,1]  # +DI 값

    return df

# =====================================================
# 신호 체크
# =====================================================

def check_signal(symbol):

    global sent_alerts, signal_found

    df = get_df(symbol)

    if len(df) < 50:
        return

    last = df.iloc[-2]
    prev = df.iloc[-3]

    rsi = last['rsi']
    plus_di = last['plus_di']
    adx = last['adx']

    volume_now = last['volume']
    volume_prev = prev['volume']

    if pd.isna(rsi) or pd.isna(plus_di) or pd.isna(adx):
        return

    # =============================
    # 조건
    # =============================

    if rsi < 30 and plus_di > 36 and adx > 20 and volume_now > volume_prev:

        now = time.time()

        if symbol in sent_alerts and now - sent_alerts[symbol] < 3600:
            return

        sent_alerts[symbol] = now

        price = last['close']

        msg = f"""🚀 SIGNAL

코인 : {symbol}
가격 : {price}

RSI : {round(rsi,2)}
+DI : {round(plus_di,2)}
ADX : {round(adx,2)}
Volume 증가
"""

        send_telegram(msg)

        signal_found = True

# =====================================================
# 코인 목록 한번만 불러오기
# =====================================================

symbols = get_symbols()

print("SCAN COINS:", len(symbols))

# =====================================================
# 스캔 실행
# =====================================================

def run_scan():

    global signal_found

    signal_found = False

    print("SCAN START")

    for symbol in symbols:

        try:
            check_signal(symbol)

        except Exception as e:
            print("ERROR:", symbol)

    if not signal_found:
        send_telegram("조건에 맞는 코인 없음")

    print("SCAN END")

# =====================================================
# 처음 실행 시 1번 스캔 (확인용)
# =====================================================

run_scan()
