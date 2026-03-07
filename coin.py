import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 바이비트(Bybit) 설정
# =====================================================
exchange = ccxt.bybit({
    'options': {
        'defaultType': 'linear',
        'adjustForTimeDifference': True,
    },
    'enableRateLimit': True,
})

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
        # 선물 마켓 정보 로드
        markets = exchange.load_markets()
        # USDT로 거래되는 선물 종목만 리스트업
        symbols = [s for s in markets if s.endswith(':USDT') and markets[s].get('linear')]
        return symbols
    except Exception as e:
        print(f"Market Load Error: {e}")
        return []

def get_df(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 지표 계산
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
    rsi = last['rsi']

    if pd.isna(rsi): return

    # =====================================================
    # ⚠️ 테스트를 위한 아주 느슨한 조건 (RSI 70 미만이면 다 잡힘)
    # =====================================================
    if rsi < 70: 
        clean_symbol = symbol.replace(':USDT', '')
        msg = f"✅ [TEST SIGNAL]\n코인: {clean_symbol}\nRSI: {round(rsi, 2)}\n(현재 테스트 모드입니다)"
        send_telegram(msg)
        signal_found = True
        return True # 신호 찾으면 True 반환
    return False

def run_scan():
    global signal_found
    signal_found = False
    print(f"===== SCAN START ({datetime.now(timezone.utc)}) =====")
    
    symbols = get_symbols()
    print(f"SCAN COINS: {len(symbols)}")

    # 너무 많이 전송되면 텔레그램 차단될 수 있으니 선착순 5개만 찾고 종료
    found_count = 0
    for i, symbol in enumerate(symbols):
        try:
            if check_signal(symbol):
                found_count += 1
            
            # 5개 찾으면 테스트 종료
            if found_count >= 5:
                break
                
            if i % 10 == 0: time.sleep(0.1)
        except: continue

    if not signal_found:
        send_telegram("🔍 테스트 조건(RSI 70)에도 맞는 코인이 없습니다.")
    
    print(f"===== SCAN END (Found: {found_count}) =====")

if __name__ == "__main__":
    run_scan()
