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

# 중복 알림 방지용 (매 실행 시 초기화되므로 보조 수단)
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
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_df.iloc[:, 0]
        df['plus_di'] = adx_df.iloc[:, 1]
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df
    except: return None

def run_scan():
    now_utc = datetime.now(timezone.utc)
    delay_min = now_utc.minute
    
    # 🎯 핵심: '날짜와 시간(Hour)'까지만 기록 (예: "2026-03-08 13")
    # 이렇게 하면 1시 내의 모든 실행(0분, 10분, 20분)은 같은 시간으로 인식됩니다.
    now_hour_str = now_utc.strftime('%Y-%m-%d %H')
    file_path = "last_run.txt"
    
    print(f"===== 스캔 시도: {now_utc.strftime('%H:%M:%S')} (UTC) =====")

    # 1. 중복 체크 (파일 읽기)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            if f.read().strip() == now_hour_str:
                print(f"✅ {now_hour_str}시에 이미 작업이 완료되었습니다. 중복 실행을 종료합니다.")
                return

    # 2. 30분 초과 체크 (기존 기능 유지)
    if delay_min >= 30:
        skip_msg = f"⏳ **스캔 건너뜀:** 현재 {delay_min}분입니다. (30분 초과)\n이미 타점이 지났을 확률이 높아 다음 정각 봉을 기다립니다."
        send_telegram(skip_msg)
        return

    # 3. [즉시 기록] 스캔 시작하자마자 파일을 업데이트해서 10분 뒤 봇이 내 존재를 알게 함
    with open(file_path, "w") as f:
        f.write(now_hour_str)

    # --- 선물 전체 코인 스캔 로직 (건드리지 않음) ---
    symbols = get_symbols()
    found_count = 0
    current_time_ms = time.time() * 1000

    for symbol in symbols:
        df = get_df(symbol)
        if df is None or len(df) < 5: continue
            
        last = df.iloc[-2]
        prev = df.iloc[-3]
        
        rsi, plus_di, adx, atr = last['rsi'], last['plus_di'], last['adx'], last['atr']
        v_now, v_prev = last['volume'], prev['volume']
        curr_price = last['close']
        prev_price = prev['close']
        candle_time = last['time']
        price_change_pct = ((curr_price - prev_price) / prev_price) * 100

        # 사용자님의 빡센 조건 그대로 유지
        if (not pd.isna(rsi) and rsi < 25 and 
            plus_di >= 40 and 
            adx >= 30 and 
            v_now > v_prev):
            
            signal_id = f"{symbol}_{candle_time}"
            if signal_id not in sent_signals:
                sent_signals[signal_id] = current_time_ms
                found_count += 1
                
                tp_price = curr_price + (atr * 2)
                sl_price = curr_price - (atr * 2)
                clean_name = symbol.split(':')[0].split('/')[0]

                msg = (f"🔥 *[코인이름: {clean_name}]*\n"
                       f"⏱ **지연 시간:** 정각 대비 {delay_min}분 경과\n\n"
                       f"💵 **현재가:** {curr_price} ({round(price_change_pct, 2)}%)\n"
                       f"━━━━━━━━━━━━━━\n"
                       f"📊 **필터링된 지표**\n"
                       f"• RSI: {round(rsi, 2)} (매우 낮음 ⚠️)\n"
                       f"• ADX: {round(adx, 2)} (강한 추세)\n"
                       f"• +DI: {round(plus_di, 2)} (에너지 폭발)\n"
                       f"• 거래량: {round(v_now/v_prev, 1)}배 증가 ✅\n"
                       f"━━━━━━━━━━━━━━\n"
                       f"🛡 **매매 가이드 (ATR)**\n"
                       f"🟢 **익절가:** {round(tp_price, 4)}\n"
                       f"🔴 **손절가:** {round(sl_price, 4)}")
                
                send_telegram(msg)
        time.sleep(0.1)

    print(f"===== {now_hour_str}시 스캔 종료 (발견: {found_count}) =====")

if __name__ == "__main__":
    run_scan() # while True 없이 1회 실행 후 종료
