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

exchange = ccxt.binance({
    "options": {"defaultType": "future"},
    "enableRateLimit": True
})

sent_messages = set()
signal_found = False

def send_telegram(msg):
    """중복 메시지 방지 및 텔레그램 전송"""
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
            print("⚠️ 전송 실패:", response.text)
    except Exception as e:
        print("⚠️ 에러:", e)

def get_symbols():
    """선물 USDT 종목 리스트"""
    markets = exchange.load_markets()
    return [s for s in markets if markets[s]["contract"] and markets[s]["quote"] == "USDT" and markets[s]["active"]]

def get_df(symbol):
    """pandas_ta를 이용한 지표 계산"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=120)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # RSI 계산
        df['rsi'] = ta.rsi(df['close'], length=14)

        # ADX / +DI 계산 (pandas_ta 방식)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_df.iloc[:, 0]    # ADX_14
        df['plus_di'] = adx_df.iloc[:, 1] # DMP_14 (+DI)
        
        return df
    except:
        return pd.DataFrame()

def check_signal(symbol):
    """신호 체크 로직"""
    global signal_found
    df = get_df(symbol)

    if len(df) < 50: return

    last = df.iloc[-2]  # 직전 확정 봉
    prev = df.iloc[-3]  # 그 전 봉

    rsi, plus_di, adx = last['rsi'], last['plus_di'], last['adx']
    v_now, v_prev = last['volume'], prev['volume']

    if pd.isna(rsi) or pd.isna(plus_di) or pd.isna(adx): return

    # 사용자 지정 조건
    if rsi < 30 and plus_di > 36 and adx > 20 and v_now > v_prev:
        msg = f"🚀 SIGNAL: {symbol}\n가격: {last['close']}\nRSI: {round(rsi,2)}\n+DI: {round(plus_di,2)}\nADX: {round(adx,2)}\n거래량 증가"
        send_telegram(msg)
        signal_found = True

def run_scan():
    global signal_found
    signal_found = False
    print(f"SCAN START: {datetime.now()}")
    
    symbols = get_symbols()
    for symbol in symbols:
        try:
            check_signal(symbol)
            time.sleep(0.05) # 바이낸스 속도 제한 준수
        except:
            continue
            
    if not signal_found:
        send_telegram("🔍 현재 조건에 맞는 코인이 없습니다.")
    print("SCAN END")

if __name__ == "__main__":
    run_scan()
