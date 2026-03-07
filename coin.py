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
# 로컬에서도 작동하고 GitHub 서버(미국 등)에서도 451 에러 없이 작동하게 합니다.
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

# =====================================================
# 2. 텔레그램 및 알림 설정
# =====================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

sent_alerts = {}
sent_messages = set()
signal_found = False

def send_telegram(msg):
    global sent_messages
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    if msg in sent_messages:
        return
    sent_messages.add(msg)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code != 200:
            print("⚠️ Telegram 전송 실패:", response.text)
    except Exception as e:
        print("⚠️ Telegram 요청 에러:", e)

# =====================================================
# 3. 데이터 처리 및 지표 계산
# =====================================================
def get_symbols():
    try:
        markets = exchange.load_markets()
        symbols = []
        for s in markets:
            market = markets[s]
            if market["contract"] and market["quote"] == "USDT" and market["active"]:
                symbols.append(s)
        return symbols
    except Exception as e:
        print("❌ 마켓 로드 에러:", e)
        return []

def get_df(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=120)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 보조지표 계산 (pandas_ta)
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        
        # 로컬에서 성공했던 인덱스 접근 방식 유지
        df['adx'] = adx_data.iloc[:, 0]      # ADX_14
        df['plus_di'] = adx_data.iloc[:, 1]  # DMP_14
        
        return df
    except Exception as e:
        # 특정 코인 에러 시 무시하고 다음 코인으로 진행
        return pd.DataFrame()

# =====================================================
# 4. 신호 체크 및 실행
# =====================================================
def check_signal(symbol):
    global sent_alerts, signal_found
    df = get_df(symbol)

    if len(df) < 50:
        return

    last = df.iloc[-2]  # 확정된 직전 봉
    prev = df.iloc[-3]

    rsi = last['rsi']
    plus_di = last['plus_di']
    adx = last['adx']
    volume_now = last['volume']
    volume_prev = prev['volume']

    if pd.isna(rsi) or pd.isna(plus_di) or pd.isna(adx):
        return

    # 전략 조건: RSI < 30, +DI > 36, ADX > 20, 거래량 증가
    if rsi < 30 and plus_di > 36 and adx > 20 and volume_now > volume_prev:
        now = time.time()
        # 1시간 내 중복 알림 방지
        if symbol in sent_alerts and now - sent_alerts[symbol] < 3600:
            return
        sent_alerts[symbol] = now

        msg = f"""🚀 SIGNAL FOUND

코인 : {symbol}
가격 : {last['close']}

RSI : {round(rsi, 2)}
+DI : {round(plus_di, 2)}
ADX : {round(adx, 2)}
Volume 증가 (전봉 대비)
"""
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
            # API 과부하 방지 (GitHub IP 차단 예방)
            if i % 10 == 0:
                time.sleep(0.1)
        except Exception as e:
            print(f"ERROR: {symbol} {e}")

    if not signal_found:
        send_telegram("🔍 현재 조건에 맞는 코인이 없습니다.")
    
    print("===== SCAN END =====")

if __name__ == "__main__":
    run_scan()
