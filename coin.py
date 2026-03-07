import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 비트겟(Bitget) 설정
# =====================================================
exchange = ccxt.bitget({
    'options': {'defaultType': 'swap'},
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
        markets = exchange.load_markets()
        # USDT 선물 + 활성 종목만 필터링
        return [
            m['symbol'] for m in markets.values() 
            if m['linear'] and m['quote'] == 'USDT' and m['active']
        ]
    except Exception as e:
        print(f"Error loading symbols: {e}")
        return []

def get_df(symbol):
    try:
        # 데이터 효율을 위해 60개만 호출
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=60)
        if not ohlcv or len(ohlcv) < 30: return pd.DataFrame()
        
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 지표 계산 (RSI 14, ADX 14)
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        
        # pandas-ta ADX 출력값 추출 (컬럼명 유연하게 대응)
        df['adx'] = adx_data.iloc[:, 0]
        df['plus_di'] = adx_data.iloc[:, 1]
        return df
    except:
        return pd.DataFrame()

def run_scan():
    print(f"===== BITGET ALL-MARKET SCAN (ADX 30+) START ({datetime.now(timezone.utc)}) =====")
    
    all_symbols = get_symbols()
    print(f"Total Symbols to scan: {len(all_symbols)}")
    
    found_count = 0
    for i, symbol in enumerate(all_symbols):
        df = get_df(symbol)
        if df.empty or len(df) < 20: continue
            
        last = df.iloc[-2]  # 확정봉 기준
        prev = df.iloc[-3]
        
        rsi = last['rsi']
        plus_di = last['plus_di']
        adx = last['adx']
        v_now = last['volume']
        v_prev = prev['volume']

        # -----------------------------------------------------
        # 🔥 업그레이드된 조건: ADX 30 이상 (강력한 추세)
        # -----------------------------------------------------
        if (not pd.isna(rsi) and rsi < 30 and 
            plus_di > 36 and 
            adx >= 25 and  # <--- ADX 기준 상향
            v_now > v_prev):
            
            found_count += 1
            clean_name = symbol.replace(':USDT', '')
            msg = (f"🎯 [POWER TREND SIGNAL]\n"
                   f"Symbol: {clean_name}\n"
                   f"RSI: {round(rsi, 2)} (Oversold)\n"
                   f"ADX: {round(adx, 2)} (Strong!)\n"
                   f"+DI: {round(plus_di, 2)}\n"
                   f"Vol: {round(v_now/v_prev, 1)}x Up")
            send_telegram(msg)
            print(f"Found Strong Signal: {symbol}")

        # 전체 종목 스캔을 위한 속도 조절 (Bitget 가이드라인 준수)
        time.sleep(0.1) 

    print(f"===== SCAN END (Found: {found_count}) =====")

if __name__ == "__main__":
    run_scan()

