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
    'enableRateLimit': True, # API 속도 제한 자동 준수
})

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# 중복 알림 방지용 딕셔너리 (메모리 최적화: {ID: 시간})
sent_signals = {}

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"Telegram Error: {e}")

def get_symbols():
    """활성 종목만 필터링 (최적화)"""
    try:
        markets = exchange.load_markets()
        return [
            symbol for symbol, m in markets.items() 
            if m.get('linear') and m.get('quote') == 'USDT' and m.get('active')
        ]
    except Exception as e:
        print(f"Error loading symbols: {e}")
        return []

def get_df(symbol):
    """지표 계산 최적화"""
    try:
        # 데이터 호출 최소화 (limit=100 유지)
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        if not ohlcv or len(ohlcv) < 50: return None
        
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # pandas_ta를 이용한 지표 일괄 계산
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_df.iloc[:, 0]
        df['plus_di'] = adx_df.iloc[:, 1]
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        return df
    except:
        return None

def run_scan():
    now_utc = datetime.now(timezone.utc)
    print(f"===== SCAN START: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    symbols = get_symbols()
    if not symbols: return
    
    found_count = 0
    
    # 메모리 정리: 24시간이 지난 신호 기록 삭제 (최적화)
    current_time = time.time() * 1000
    expired_ids = [sid for sid, timestamp in sent_signals.items() if current_time - timestamp > 86400000]
    for eid in expired_ids:
        del sent_signals[eid]

    for symbol in symbols:
        try:
            df = get_df(symbol)
            if df is None or len(df) < 2: continue
                
            last = df.iloc[-2]  # 확정봉
            prev = df.iloc[-3]  # 이전봉
            
            # 수치 할당
            rsi, plus_di, adx, atr = last['rsi'], last['plus_di'], last['adx'], last['atr']
            v_now, v_prev = last['volume'], prev['volume']
            curr_price = last['close']
            candle_time = last['time']

            # 🎯 타점 조건 (기존 유지)
            if (not pd.isna(rsi) and rsi < 30 and 
                plus_di > 36 and 
                adx >= 25 and 
                v_now > v_prev):
                
                signal_id = f"{symbol}_{candle_time}"
                if signal_id not in sent_signals:
                    sent_signals[signal_id] = candle_time
                    found_count += 1
                    
                    tp_price = curr_price + (atr * 2)
                    sl_price = curr_price - (atr * 2)
                    clean_name = symbol.split(':')[0].split('/')[0]

                    msg = (f"🚨 *[1H SIGNAL FOUND]*\n\n"
                           f"**Symbol:** {clean_name}\n"
                           f"**Price:** {curr_price}\n"
                           f"---指标---\n"
                           f"RSI: {round(rsi, 2)}\n"
                           f"ADX: {round(adx, 2)} (+DI: {round(plus_di, 2)})\n"
                           f"Vol: {round(v_now/v_prev, 1)}x Up ✅\n"
                           f"---Guide---\n"
                           f"🟢 **TP (Target):** {round(tp_price, 4)}\n"
                           f"🔴 **SL (Stop):** {round(sl_price, 4)}")
                    
                    send_telegram(msg)
                    print(f"Signal: {symbol}")

        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
            continue

        # API 부하 분산 (Bitget은 초당 10~20회 권장)
        time.sleep(0.1)

    print(f"===== SCAN END (Found: {found_count}) =====")

if __name__ == "__main__":
    while True:
        run_scan()
        # 1시간 간격으로 정각 즈음에 실행되도록 대기
        time.sleep(3600)
