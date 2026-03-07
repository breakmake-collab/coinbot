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
    'options': {'defaultType': 'swap'}, # 선물(Swap) 마켓
    'enableRateLimit': True,
})

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# 중복 알림 방지를 위한 메모리 (프로그램 실행 회차 내 중복 방지)
sent_signals = []

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

def get_symbols():
    """비트겟에서 활성화된 모든 USDT 선물 종목 리스트 획득"""
    try:
        markets = exchange.load_markets()
        return [
            m['symbol'] for m in markets.values() 
            if m['linear'] and m['quote'] == 'USDT' and m['active']
        ]
    except Exception as e:
        print(f"Error loading symbols: {e}")
        return []

def get_df(symbol):
    """1시간봉 데이터 수집 및 지표 계산"""
    try:
        # 1시간봉('1h') 데이터 100개 호출
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        if not ohlcv or len(ohlcv) < 50: return pd.DataFrame()
        
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 지표 계산 (RSI 14, ADX 14)
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        
        # ADX 및 +DI 컬럼 추출 (pandas-ta 표준 컬럼명 대응)
        df['adx'] = adx_df.iloc[:, 0]
        df['plus_di'] = adx_df.iloc[:, 1]
        return df
    except:
        return pd.DataFrame()

def run_scan():
    print(f"===== BITGET 1H FULL SCAN START ({datetime.now(timezone.utc)}) =====")
    
    symbols = get_symbols()
    print(f"Total Symbols: {len(symbols)}")
    
    found_count = 0
    for i, symbol in enumerate(symbols):
        df = get_df(symbol)
        if df.empty or len(df) < 30: continue
            
        # [중요] 실시간 봉(-1)이 아닌, 직전 마감된 확정봉(-2) 확인
        last = df.iloc[-2] 
        prev = df.iloc[-3]
        
        candle_time = last['time'] # 봉의 고유 시간 (중복 방지 키)
        
        rsi = last['rsi']
        plus_di = last['plus_di']
        adx = last['adx']
        v_now = last['volume']
        v_prev = prev['volume']

        # -----------------------------------------------------
        # 🎯 최적화 타점 조건
        # 1. RSI < 30 (과매도)
        # 2. +DI > 36 (강한 상승 에너지)
        # 3. ADX >= 25 (추세 강도 최적화)
        # 4. 거래량 증가 (실질적 수급 확인)
        # -----------------------------------------------------
        if (not pd.isna(rsi) and rsi < 30 and 
            plus_di > 36 and 
            adx >= 25 and 
            v_now > v_prev):
            
            # 동일 종목, 동일 시간에 중복 발송 방지
            signal_id = f"{symbol}_{candle_time}"
            if signal_id not in sent_signals:
                found_count += 1
                sent_signals.append(signal_id)
                
                clean_name = symbol.split(':')[0]
                msg = (f"🚨 [1H SIGNAL FOUND]\n"
                       f"Symbol: {clean_name}\n"
                       f"Price: {last['close']}\n\n"
                       f"RSI: {round(rsi, 2)}\n"
                       f"ADX: {round(adx, 2)}\n"
                       f"+DI: {round(plus_di, 2)}\n"
                       f"Vol: {round(v_now/v_prev, 1)}x Up ✅")
                send_telegram(msg)
                print(f"Signal Sent: {symbol}")

        # API 요청 속도 조절 (초당 약 8개 스캔)
        time.sleep(0.12)

    print(f"===== SCAN END (Total Found: {found_count}) =====")

if __name__ == "__main__":
    run_scan()
