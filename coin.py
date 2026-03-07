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
    'options': {'defaultType': 'swap'}, # 선물 마켓 (Swap)
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

def get_df(symbol):
    try:
        # 비트겟 선물 데이터 1시간봉 100개
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 지표 계산
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_data.iloc[:, 0]
        df['plus_di'] = adx_data.iloc[:, 1]
        return df
    except Exception:
        return pd.DataFrame()

def run_scan():
    # 로그 인코딩 에러 방지를 위해 영어 사용
    print(f"===== BITGET SCAN START ({datetime.now(timezone.utc)}) =====")
    
    # 비트겟 선물 주요 종목 리스트 (약 100개)
    # 비트겟 포맷: '코인명USDT' 또는 '코인명/USDT:USDT'
    target_symbols = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOTUSDT',
        'LINKUSDT', 'MATICUSDT', 'NEARUSDT', 'LTCUSDT', 'BCHUSDT', 'SHIBUSDT', 'TRXUSDT', 'UNIUSDT',
        'SUIUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT', 'SEIUSDT', 'TIAUSDT', 'STXUSDT', 'INJUSDT',
        'IMXUSDT', 'KASUSDT', 'FETUSDT', 'RNDRUSDT', 'TAOUSDT', 'HBARUSDT', 'ATOMUSDT', 'PEPEUSDT',
        'WIFUSDT', 'BONKUSDT', 'FLOKIUSDT', 'JUPUSDT', 'ORDIUSDT', 'LUNCUSDT', 'MEMEUSDT', 'BEAMUSDT',
        'PYTHUSDT', 'GALAUSDT', 'FILUSDT', 'ETCUSDT', 'DYDXUSDT', 'CRVUSDT', 'AAVEUSDT', 'LDOUSDT',
        'PENDLEUSDT', 'ENAUSDT', 'WUSDT', 'ARUSDT', 'STRKUSDT', 'ANKRUSDT', 'GRTUSDT', 'AGIXUSDT',
        'OCEANUSDT', 'SANDUSDT', 'MANAUSDT', 'ALGOUSDT', 'EGLDUSDT', 'CHZUSDT', 'AXSUSDT', 'FLOWUSDT',
        'ICPUSDT', 'QNTUSDT', 'FTMUSDT', 'THETAUSDT', 'MKRUSDT', 'SNXUSDT', 'NEOUSDT', 'IOTAUSDT',
        'KAVAUSDT', 'ZILUSDT', 'ENJUSDT', 'COMPUSDT', '1INCHUSDT', 'RUNESDT', 'WOOUSDT', 'DYMUSDT',
        'METISUSDT', 'BOMEUSDT', 'SLERFUSDT', 'MEWUSDT', 'ALTUSDT', 'MANTAUSDT', 'JTOSDT', 'BLURUSDT',
        'MINAUSDT', 'RONUSDT', 'AXLUSDT', 'IDUSDT', 'EDUUSDT', 'MAVUSDT', 'CYBERUSDT', 'ARKMUSDT',
        'GALUSDT', 'ARKUSDT', 'PIXELUSDT', 'STRKUSDT'
    ]
    
    print(f"Scanning {len(target_symbols)} symbols on Bitget...")
    found_count = 0

    for symbol in target_symbols:
        df = get_df(symbol)
        if df.empty or len(df) < 50:
            continue
            
        last = df.iloc[-2]
        prev = df.iloc[-3]
        
        rsi = last['rsi']
        plus_di = last['plus_di']
        adx = last['adx']
        v_now = last['volume']
        v_prev = prev['volume']

        # 테스트를 위해 느슨한 조건 (RSI 70 미만)
        # 성공 확인 후 rsi < 30 and plus_di > 36 and adx > 20 and v_now > v_prev 로 변경하세요.
        if not pd.isna(rsi) and rsi < 70:
            found_count += 1
            msg = f"BITGET SIGNAL: {symbol}\nRSI: {round(rsi, 2)}\nADX: {round(adx, 2)}"
            send_telegram(msg)
            print(f"Found: {symbol}")
            
            # 테스트용: 3개만 찾으면 조기 종료
            if found_count >= 3: break

        time.sleep(0.1) # 속도 제한

    if found_count == 0:
        print("No signals found.")
    
    print(f"===== SCAN END (Found: {found_count}) =====")

if __name__ == "__main__":
    run_scan()
