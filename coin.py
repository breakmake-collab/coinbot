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
    'enableRateLimit': True, # CCXT 자체 속도 제한 권장 준수
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
    """비트겟에서 활성화된 모든 USDT 선물 종목을 가져옴"""
    try:
        markets = exchange.load_markets()
        # USDT 결제 + 활성화된 선물 종목만 필터링
        return [
            m['symbol'] for m in markets.values() 
            if m['linear'] and m['quote'] == 'USDT' and m['active']
        ]
    except Exception as e:
        print(f"Error loading symbols: {e}")
        return []

def get_df(symbol):
    try:
        # 데이터 로딩 (비트겟 API 부하를 줄이기 위해 limit 최소화)
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=50)
        if not ohlcv or len(ohlcv) < 30: return pd.DataFrame()
        
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 지표 계산
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_data.iloc[:, 0]
        df['plus_di'] = adx_data.iloc[:, 1]
        return df
    except:
        return pd.DataFrame()

def run_scan():
    print(f"===== BITGET ALL-SYMBOLS SCAN START ({datetime.now(timezone.utc)}) =====")
    
    # 전체 종목 리스트 가져오기
    all_symbols = get_symbols()
    print(f"Total Symbols Found: {len(all_symbols)}")
    
    found_count = 0
    for i, symbol in enumerate(all_symbols):
        df = get_df(symbol)
        if df.empty or len(df) < 20:
            continue
            
        last = df.iloc[-1]   # 현재 진행 중인 봉 (또는 -2 확정봉)
        prev = df.iloc[-2]
        
        rsi, plus_di, adx = last['rsi'], last['plus_di'], last['adx']
        v_now, v_prev = last['volume'], prev['volume']

        # 사용자님 조건 적용
        if (not pd.isna(rsi) and rsi < 30 and 
            plus_di > 36 and 
            adx >= 20 and 
            v_now > v_prev):
            
            found_count += 1
            clean_name = symbol.replace(':USDT', '')
            msg = (f"🚨 [ALL-MARKET SIGNAL]\n"
                   f"Symbol: {clean_name}\n"
                   f"Price: {last['close']}\n\n"
                   f"RSI: {round(rsi, 2)}\n"
                   f"ADX: {round(adx, 2)}\n"
                   f"+DI: {round(plus_di, 2)}\n"
                   f"Vol: {round(v_now/v_prev, 1)}x Up ✅")
            send_telegram(msg)
            print(f"Signal: {symbol}")

        # 종목이 수백 개이므로 요청 간격 조절 (비트겟 IP 차단 방지)
        # 약 0.1초마다 하나씩 처리
        if i % 10 == 0:
            time.sleep(1) 
        else:
            time.sleep(0.05)

    print(f"===== SCAN END (Total Found: {found_count}) =====")

if __name__ == "__main__":
    run_scan()
