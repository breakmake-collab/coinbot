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
    'options': {'defaultType': 'swap'},
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
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        if not ohlcv: return pd.DataFrame()
        
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_data.iloc[:, 0]
        df['plus_di'] = adx_data.iloc[:, 1]
        return df
    except:
        return pd.DataFrame()

def run_scan():
    print(f"===== BITGET 200 ALTS SCAN START ({datetime.now(timezone.utc)}) =====")
    
    # 🔥 비트겟 선물 주요 알트코인 200개 (대형주 + 유동성 좋은 중소형주)
    target_symbols = [
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOTUSDT',
        'LINKUSDT', 'NEARUSDT', 'SUIUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT', 'TIAUSDT', 'SEIUSDT',
        'STXUSDT', 'INJUSDT', 'LTCUSDT', 'BCHUSDT', 'SHIBUSDT', 'TRXUSDT', 'UNIUSDT', 'PEPEUSDT',
        'WIFUSDT', 'BONKUSDT', 'FLOKIUSDT', 'JUPUSDT', 'ORDIUSDT', 'FETUSDT', 'RNDRUSDT', 'TAOUSDT',
        'HBARUSDT', 'ATOMUSDT', 'LUNCUSDT', 'MEMEUSDT', 'BEAMUSDT', 'PYTHUSDT', 'GALAUSDT', 'FILUSDT',
        'ETCUSDT', 'DYDXUSDT', 'CRVUSDT', 'AAVEUSDT', 'LDOUSDT', 'PENDLEUSDT', 'ENAUSDT', 'WUSDT',
        'ARUSDT', 'STRKUSDT', 'ANKRUSDT', 'GRTUSDT', 'AGIXUSDT', 'OCEANUSDT', 'SANDUSDT', 'MANAUSDT',
        'ALGOUSDT', 'EGLDUSDT', 'CHZUSDT', 'AXSUSDT', 'FLOWUSDT', 'ICPUSDT', 'QNTUSDT', 'FTMUSDT',
        'THETAUSDT', 'MKRUSDT', 'SNXUSDT', 'NEOUSDT', 'IOTAUSDT', 'KAVAUSDT', 'ZILUSDT', 'ENJUSDT',
        'COMPUSDT', '1INCHUSDT', 'RUNESDT', 'WOOUSDT', 'DYMUSDT', 'METISUSDT', 'BOMEUSDT', 'SLERFUSDT',
        'MEWUSDT', 'ALTUSDT', 'MANTAUSDT', 'JTOSDT', 'BLURUSDT', 'MINAUSDT', 'RONUSDT', 'AXLUSDT',
        'IDUSDT', 'EDUUSDT', 'MAVUSDT', 'CYBERUSDT', 'ARKMUSDT', 'GALUSDT', 'ARKUSDT', 'PIXELUSDT',
        'PORTALUSDT', 'XAIUSDT', 'RONINUSDT', 'ZETASDT', 'JUPUSDT', 'MYROUSDT', 'POPCATUSDT', 'BRETTUSDT',
        'AEVOUSDT', 'VANRYUSDT', 'ANKRUSDT', 'SCUSDT', 'GLMUSDT', 'RAYUSDT', 'MASKUSDT', 'GNSUSDT',
        'SUSHIUSDT', 'DYDXUSDT', 'YGGUSDT', 'AGLDUSDT', 'LRCUSDT', 'ONEUSDT', 'ZECUSDT', 'DASHUSDT',
        'XLMUSDT', 'ONTUSDT', 'VETUSDT', 'IOSTUSDT', 'QTUMUSDT', 'BATUSDT', 'ZRXUSDT', 'KNCUSDT',
        'SXPUSDT', 'OMGUSDT', 'RENUSDT', 'BALUSDT', 'KNCUSDT', 'RLCUSDT', 'BANDUSDT', 'TOMOUSDT',
        'REEFUSDT', 'KAVAUSDT', 'SKLUSDT', 'STMXUSDT', 'ANKRUSDT', 'OGNUSDT', 'CTSIUSDT', 'ALPHAUSDT',
        'LINAUSDT', 'BAKEUSDT', 'BELUSDT', 'TLMUSDT', 'LITUSDT', 'C98USDT', 'MASKUSDT', 'ATAUSDT',
        'DYDXUSDT', 'GALAUSDT', 'CELOUSDT', 'RAREUSDT', 'IDEXUSDT', 'DARUSDT', 'BNXUSDT', 'MOVRUSDT',
        'JOEUSDT', 'ACHUSDT', 'API3USDT', 'WOOUSDT', 'TUSDT', 'ASTRUSDT', 'GALUSDT', 'GMTUSDT',
        'KNCUSDT', 'LDOUSDT', 'LEOUSDT', 'LRCUSDT', 'OKBUSDT', 'XAUTUSDT', 'KASUSDT', 'BEAMUSDT',
        'ONDOUSDT', 'JUPUSDT', 'ZETASDT', 'STRKUSDT', 'MAVIAUSDT', 'DYMUSDT', 'PIXELUSDT', 'PORTALUSDT'
    ]
    
    # 중복 제거 (리스트 작성 시 실수 방지)
    target_symbols = list(set(target_symbols))
    print(f"Scanning {len(target_symbols)} symbols...")
    
    found_count = 0
    for symbol in target_symbols:
        df = get_df(symbol)
        if df.empty or len(df) < 50:
            continue
            
        last = df.iloc[-2]
        prev = df.iloc[-3]
        
        rsi, plus_di, adx = last['rsi'], last['plus_di'], last['adx']
        v_now, v_prev = last['volume'], prev['volume']

        # 조건: RSI < 30 AND +DI > 36 AND ADX >= 20 AND 거래량 증가
        if (not pd.isna(rsi) and rsi < 30 and 
            plus_di > 36 and 
            adx >= 20 and 
            v_now > v_prev):
            
            found_count += 1
            msg = (f"🚨 [BITGET MEGA SIGNAL]\n"
                   f"Symbol: {symbol}\n"
                   f"Price: {last['close']}\n\n"
                   f"RSI: {round(rsi, 2)}\n"
                   f"ADX: {round(adx, 2)}\n"
                   f"+DI: {round(plus_di, 2)}\n"
                   f"Vol: Up ✅")
            send_telegram(msg)
            print(f"Signal: {symbol}")

        # 200개 스캔 시 API 부하 방지를 위해 딜레이 조정 (0.15초)
        time.sleep(0.15)

    print(f"===== SCAN END (Total Found: {found_count}) =====")

if __name__ == "__main__":
    run_scan()
