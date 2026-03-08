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

sent_signals = []

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        # 마크다운 지원을 위해 parse_mode 추가
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_symbols():
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
    """1시간봉 데이터 수집 및 지표 계산 (ATR 추가)"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        if not ohlcv or len(ohlcv) < 50: return pd.DataFrame()
        
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 지표 계산 (RSI 14, ADX 14)
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        
        df['adx'] = adx_df.iloc[:, 0]
        df['plus_di'] = adx_df.iloc[:, 1]
        
        # [추가] ATR 계산 (손절/익절 가이드라인용)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
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
            
        last = df.iloc[-2] 
        prev = df.iloc[-3]
        
        candle_time = last['time'] 
        
        rsi = last['rsi']
        plus_di = last['plus_di']
        adx = last['adx']
        atr = last['atr']
        v_now = last['volume']
        v_prev = prev['volume']
        curr_price = last['close']

        # 🎯 기존 최적화 타점 조건 유지
        if (not pd.isna(rsi) and rsi < 30 and 
            plus_di > 36 and 
            adx >= 25 and 
            v_now > v_prev):
            
            signal_id = f"{symbol}_{candle_time}"
            if signal_id not in sent_signals:
                found_count += 1
                sent_signals.append(signal_id)
                
                # [추가] 손절(SL) 및 익절(TP) 계산 (ATR의 2배 적용)
                tp_price = curr_price + (atr * 2)
                sl_price = curr_price - (atr * 2)
                
                clean_name = symbol.split(':')[0]
                # 트레이딩뷰 및 비트겟 링크 추가
                tv_url = f"https://www.tradingview.com/chart/?symbol=BITGET:{clean_name}.P"

                msg = (f"🚨 *[1H SIGNAL FOUND]*\n\n"
                       f"**Symbol:** {clean_name}\n"
                       f"**Price:** {curr_price}\n"
                       f"---指标---\n"
                       f"RSI: {round(rsi, 2)}\n"
                       f"ADX: {round(adx, 2)} (+DI: {round(plus_di, 2)})\n"
                       f"Vol: {round(v_now/v_prev, 1)}x Up ✅\n"
                       f"---Guide---\n"
                       f"🟢 **TP (Target):** {round(tp_price, 4)}\n"
                       f"🔴 **SL (Stop):** {round(sl_price, 4)}\n\n"
                       f"🔗 [TradingView]({tv_url})")
                
                send_telegram(msg)
                print(f"Signal Sent: {symbol}")

        time.sleep(0.12)

    print(f"===== SCAN END (Total Found: {found_count}) =====")

if __name__ == "__main__":
    while True: # 무한 반복 추가 (필요 없으면 제거)
        run_scan()
        print("Waiting for next scan... (60 min)")
        time.sleep(3600) # 1시간마다 반복
