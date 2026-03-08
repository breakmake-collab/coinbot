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
    
    # 🎯 핵심: '시(Hour)'까지만 기록 (예: "2024-05-20 01")
    # 이렇게 하면 1시 0분, 10분, 20분은 모두 같은 값으로 취급되어 중복이 차단되고
    # 2시가 되면 값이 바뀌므로 다시 정상 스캔됩니다.
    now_hour_str = now_utc.strftime('%Y-%m-%d %H')
    file_path = "last_run.txt"
    
    print(f"===== 스캔 시도: {now_utc.strftime('%H:%M:%S')} (UTC) =====")

    # 1. 중복 체크 (같은 '시'에 이미 실행된 적 있는지 확인)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            if f.read().strip() == now_hour_str:
                print(f"✅ {now_hour_str}시에 이미 스캔을 완료했습니다. 중복 실행 방지.")
                return

    # 2. 30분 초과 체크 (기존 유지)
    if delay_min >= 30:
        print(f"⏳ 30분 초과로 스캔 건너뜀: {delay_min}분")
        return

    # 3. [핵심] 스캔 시작 직후 파일에 '현재 시(Hour)' 기록
    # 뒤이어 실행될 봇(10분, 20분)이 이 기록을 보고 멈추게 됩니다.
    with open(file_path, "w") as f:
        f.write(now_hour_str)

    # --- 실제 코인 스캔 로직 ---
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
                       f"📊 **지표 정보**\n"
                       f"• RSI: {round(rsi, 2)}\n"
                       f"• ADX: {round(adx, 2)}\n"
                       f"• +DI: {round(plus_di, 2)}\n"
                       f"━━━━━━━━━━━━━━\n"
                       f"🛡 **매매 가이드**\n"
                       f"🟢 **익절:** {round(tp_price, 4)}\n"
                       f"🔴 **손절:** {round(sl_price, 4)}")
                
                send_telegram(msg)
    
    print(f"===== {now_hour_str}시 스캔 종료 (발견: {found_count}) =====")

if __name__ == "__main__":
    run_scan()
