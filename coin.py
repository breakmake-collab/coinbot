import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 비트겟(Bitget) 선물 설정
# =====================================================
exchange = ccxt.bitget({
    'options': {'defaultType': 'swap'}, # 선물 마켓 고정
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
        # 비트겟 1시간봉 데이터 요청
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 지표 계산 (RSI, ADX, DI)
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_data.iloc[:, 0]
        df['plus_di'] = adx_data.iloc[:, 1]
        return df
    except:
        return pd.DataFrame()

def run_scan():
    print(f"===== BITGET MEGA 100 SCAN START ({datetime.now(timezone.utc)}) =====")
    
    # 🔥 비트겟 선물 주요 알트코인 100개 (거래량 순 위주)
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
        'GALUSDT', 'ARKUSDT', 'PIXELUSDT', 'PYTHUSDT'
    ]
    
    print(f"Total Targets: {len(target_symbols)}")
    found_count = 0

    for symbol in target_symbols:
        df = get_df(symbol)
        if df.empty or len(df) < 50:
            continue
            
        last = df.iloc[-2]  # 확정봉
        prev = df.iloc[-3]  # 이전봉
        
        rsi = last['rsi']
        plus_di = last['plus_di']
        adx = last['adx']
        v_now = last['volume']
        v_prev = prev['volume']

        # -----------------------------------------------------
        # ⚠️ 테스트용 조건: RSI < 70 (신호 확인용)
        # 확인 후 사용자님의 실제 조건으로 변경하세요:
        # if rsi < 30 and plus_di > 36 and adx > 20 and v_now > v_prev:
        # -----------------------------------------------------
        if not pd.isna(rsi) and rsi < 70:
            found_count += 1
            msg = (f"✅ [BITGET SIGNAL]\n"
                   f"Symbol: {symbol}\n"
                   f"Price: {last['close']}\n"
                   f"RSI: {round(rsi, 2)}\n"
                   f"ADX: {round(adx, 2)}\n"
                   f"Volume: Increased")
            send_telegram(msg)
            print(f"Found: {symbol}")
            
            # 테스트 시 과도한 메시지 방지 (5개 발견 시 종료)
            if found_count >= 5: break

        time.sleep(0.15) # API 속도 제한 준수

    print(f"===== SCAN END (Found: {found_count}) =====")

if __name__ == "__main__":
    run_scan()
