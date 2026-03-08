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
    now_utc = datetime.now(timezone.utc)
    delay_min = now_utc.minute
    # 🎯 현재 '날짜와 시간(시)'을 문자열로 만듭니다 (예: 2024-05-20 13)
    now_hour_str = now_utc.strftime('%Y-%m-%d %H')
    file_path = "last_run.txt"
    
    print(f"===== 스캔 시도: {now_utc.strftime('%H:%M:%S')} (UTC) =====")

    # 🎯 [핵심 추가] 1. 파일 읽어서 이번 시간대에 이미 실행했는지 확인
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            if f.read().strip() == now_hour_str:
                print(f"✅ {now_hour_str}시에 이미 성공적으로 실행되었습니다. 중복 실행을 방지하고 종료합니다.")
                return

    # 🎯 2. 30분 초과 체크 (기존 유지)
    if delay_min >= 30:
        skip_msg = f"⏳ **스캔 건너뜀:** 현재 {delay_min}분입니다. (30분 초과)\n이미 타점이 지났을 확률이 높아 다음 정각 봉을 기다립니다."
        send_telegram(skip_msg)
        print(f"건너뜀 알림 발송: {delay_min}분")
        return

    # --- 여기서부터 실제 코인 스캔 로직 (건드리지 않음) ---
    symbols = get_symbols()
    found_count = 0
    
    current_time_ms = time.time() * 1000
    expired_ids = [sid for sid, timestamp in sent_signals.items() if current_time_ms - timestamp > 86400000]
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

        price_change_pct = ((curr_price - prev_price) / prev_price) * 100

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
                print(f"강력 신호 발송: {clean_name}")

        time.sleep(0.1)

    # 🎯 [핵심 추가] 3. 모든 스캔이 무사히 끝나면 파일에 현재 시간 기록
    with open(file_path, "w") as f:
        f.write(now_hour_str)
    
    print(f"===== 스캔 종료 (발견: {found_count}) 및 {now_hour_str}시 기록 완료 =====")

if __name__ == "__main__":
    run_scan()
