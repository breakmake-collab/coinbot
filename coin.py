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

# 중복 알림 방지용 (24시간 관리)
sent_signals = {}

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except: pass

def get_symbols():
    try:
        markets = exchange.load_markets()
        return [
            symbol for symbol, m in markets.items() 
            if m.get('linear') and m.get('quote') == 'USDT' and m.get('active')
        ]
    except: return []

def get_df(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        if not ohlcv or len(ohlcv) < 50: return None
        
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 지표 계산 (RSI, ADX, ATR)
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_df.iloc[:, 0]
        df['plus_di'] = adx_df.iloc[:, 1]
        
        # [왼쪽 3번 추가] ATR 계산 (변동성 기반 손절/익절용)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        return df
    except: return None

def run_scan():
    print(f"===== 스캔 시작: {datetime.now(timezone.utc).strftime('%H:%M:%S')} (UTC) =====")
    
    symbols = get_symbols()
    found_count = 0
    
    # 메모리 정리 (24시간 지난 신호 삭제)
    current_time = time.time() * 1000
    expired_ids = [sid for sid, timestamp in sent_signals.items() if current_time - timestamp > 86400000]
    for eid in expired_ids: del sent_signals[eid]

    for symbol in symbols:
        df = get_df(symbol)
        if df is None or len(df) < 5: continue
            
        last = df.iloc[-2]   # 직전 확정봉
        prev = df.iloc[-3]   # 그 이전봉
        
        rsi, plus_di, adx, atr = last['rsi'], last['plus_di'], last['adx'], last['atr']
        v_now, v_prev = last['volume'], prev['volume']
        curr_price = last['close']
        prev_price = prev['close']
        candle_time = last['time']

        # [오른쪽 3번 추가] 가격 변화율 계산 (비율)
        price_change_pct = ((curr_price - prev_price) / prev_price) * 100

        # 🎯 전략 조건 검사 (기존 유지)
        if (not pd.isna(rsi) and rsi < 30 and 
            plus_di > 36 and 
            adx >= 25 and 
            v_now > v_prev):
            
            signal_id = f"{symbol}_{candle_time}"
            if signal_id not in sent_signals:
                sent_signals[signal_id] = candle_time
                found_count += 1
                
                # [왼쪽 3번 추가] 손절(SL) 및 익절(TP) 계산 (ATR 2배 적용)
                tp_price = curr_price + (atr * 2)
                sl_price = curr_price - (atr * 2)
                
                clean_name = symbol.split(':')[0].split('/')[0]

                # 메시지 구성 (한국어 + 비율 + 가이드라인)
                msg = (f"🚨 *[1H 포착: {clean_name}]*\n\n"
                       f"💵 **현재가:** {curr_price} ({round(price_change_pct, 2)}%)\n"
                       f"━━━━━━━━━━━━━━\n"
                       f"📊 **지표 현황**\n"
                       f"• RSI: {round(rsi, 2)}\n"
                       f"• ADX: {round(adx, 2)} (+DI: {round(plus_di, 2)})\n"
                       f"• 거래량: {round(v_now/v_prev, 1)}배 증가 ✅\n"
                       f"━━━━━━━━━━━━━━\n"
                       f"🛡 **매매 가이드 (ATR)**\n"
                       f"🟢 **익절가:** {round(tp_price, 4)}\n"
                       f"🔴 **손절가:** {round(sl_price, 4)}")
                
                send_telegram(msg)
                print(f"신호 발송: {clean_name}")

        time.sleep(0.1)

    print(f"===== 스캔 종료 (발견: {found_count}) =====")

if __name__ == "__main__":
    while True:
        run_scan()
        # 다음 스캔까지 대기 (1시간)
        time.sleep(3600)
