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
    'options': {'defaultType': 'swap'}, # 선물 마켓(Swap) 고정
    'enableRateLimit': True,
})

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        # 타점이 여러 개일 수 있으므로 타임아웃을 넉넉히 잡고 전송
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

def get_df(symbol):
    try:
        # 비트겟 1시간봉 데이터 100개 요청
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        if not ohlcv: return pd.DataFrame()
        
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 지표 계산 (RSI, ADX, DI)
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        
        # pandas-ta의 ADX 출력 컬럼명에 맞춰 매핑
        df['adx'] = adx_data.iloc[:, 0]     # ADX_14
        df['plus_di'] = adx_data.iloc[:, 1]  # DMP_14
        return df
    except:
        return pd.DataFrame()

def run_scan():
    # 로그 인코딩 문제 방지를 위해 영어 로그 유지
    print(f"===== BITGET FULL SCAN START ({datetime.now(timezone.utc)}) =====")
    
    # 알트코인 100개 리스트
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
    
    print(f"Scanning {len(target_symbols)} symbols...")
    found_count = 0

    for symbol in target_symbols:
        df = get_df(symbol)
        if df.empty or len(df) < 50:
            continue
            
        last = df.iloc[-2]  # 직전 확정봉
        prev = df.iloc[-3]  # 그 전봉
        
        rsi = last['rsi']
        plus_di = last['plus_di']
        adx = last['adx']
        v_now = last['volume']
        v_prev = prev['volume']

        # -----------------------------------------------------
        # 🔥 실전 조건: RSI < 30 AND +DI > 36 AND ADX >= 20 AND 거래량 증가
        # -----------------------------------------------------
        if (not pd.isna(rsi) and rsi < 30 and 
            plus_di > 36 and 
            adx >= 20 and 
            v_now > v_prev):
            
            found_count += 1
            msg = (f"🚨 [REAL SIGNAL FOUND]\n"
                   f"Symbol: {symbol}\n"
                   f"Price: {last['close']}\n\n"
                   f"RSI: {round(rsi, 2)}\n"
                   f"ADX: {round(adx, 2)}\n"
                   f"+DI: {round(plus_di, 2)}\n"
                   f"Vol: Up ({round(v_now/v_prev, 1)}x) ✅")
            send_telegram(msg)
            print(f"Signal: {symbol}")

        # 100개 스캔 시 API 차단 방지를 위해 약한 딜레이 유지
        time.sleep(0.1)

    print(f"===== SCAN END (Total Found: {found_count}) =====")

if __name__ == "__main__":
    run_scan()
