import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timezone

# =====================================================
# 1. 바이비트(Bybit) 설정
# =====================================================
exchange = ccxt.bybit({
    'options': {'defaultType': 'linear'},
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
        # 1시간봉 데이터 직접 요청
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        
        # 지표 계산
        df['rsi'] = ta.rsi(df['close'], length=14)
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_df.iloc[:, 0]
        df['plus_di'] = adx_df.iloc[:, 1]
        return df
    except:
        return pd.DataFrame()

def run_scan():
    print(f"===== MEGA 100 ALTS SCAN START ({datetime.now(timezone.utc)}) =====")
    
    # 🔥 바이비트 선물 주요 알트코인 100개 리스트
    target_symbols = [
        'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'XRP/USDT:USDT', 'DOGE/USDT:USDT',
        'ADA/USDT:USDT', 'AVAX/USDT:USDT', 'DOT/USDT:USDT', 'LINK/USDT:USDT', 'MATIC/USDT:USDT',
        'NEAR/USDT:USDT', 'LTC/USDT:USDT', 'BCH/USDT:USDT', 'SHIB/USDT:USDT', 'TRX/USDT:USDT',
        'UNI/USDT:USDT', 'SUI/USDT:USDT', 'APT/USDT:USDT', 'ARB/USDT:USDT', 'OP/USDT:USDT',
        'SEI/USDT:USDT', 'TIA/USDT:USDT', 'STX/USDT:USDT', 'INJ/USDT:USDT', 'IMX/USDT:USDT',
        'KAS/USDT:USDT', 'FET/USDT:USDT', 'RNDR/USDT:USDT', 'TAO/USDT:USDT', 'HBAR/USDT:USDT',
        'ATOM/USDT:USDT', 'PEPE/USDT:USDT', 'WIF/USDT:USDT', 'BONK/USDT:USDT', 'FLOKI/USDT:USDT',
        'JUP/USDT:USDT', 'ORDI/USDT:USDT', '1000LUNC/USDT:USDT', 'MEME/USDT:USDT', 'BEAM/USDT:USDT',
        'PYTH/USDT:USDT', 'GALA/USDT:USDT', 'FIL/USDT:USDT', 'ETC/USDT:USDT', 'DYDX/USDT:USDT',
        'CRV/USDT:USDT', 'AAVE/USDT:USDT', 'LDO/USDT:USDT', 'PENDLE/USDT:USDT', 'ENA/USDT:USDT',
        'W/USDT:USDT', 'AR/USDT:USDT', 'STRK/USDT:USDT', 'TIA/USDT:USDT', 'ANKR/USDT:USDT',
        'GRT/USDT:USDT', 'AGIX/USDT:USDT', 'OCEAN/USDT:USDT', 'SAND/USDT:USDT', 'MANA/USDT:USDT',
        'ALGO/USDT:USDT', 'EGLD/USDT:USDT', 'CHZ/USDT:USDT', 'AXS/USDT:USDT', 'FLOW/USDT:USDT',
        'ICP/USDT:USDT', 'QNT/USDT:USDT', 'FTM/USDT:USDT', 'THETA/USDT:USDT', 'MKR/USDT:USDT',
        'SNX/USDT:USDT', 'NEO/USDT:USDT', 'IOTA/USDT:USDT', 'KAVA/USDT:USDT', 'ZIL/USDT:USDT',
        'ENJ/USDT:USDT', 'COMP/USDT:USDT', '1INCH/USDT:USDT', 'RUNE/USDT:USDT', 'WOO/USDT:USDT',
        'DYM/USDT:USDT', 'METIS/USDT:USDT', 'BOME/USDT:USDT', 'SLERF/USDT:USDT', 'MEW/USDT:USDT',
        'ALT/USDT:USDT', 'MANTA/USDT:USDT', 'PYTH/USDT:USDT', 'JTO/USDT:USDT', 'BLUR/USDT:USDT',
        'MINA/USDT:USDT', 'RON/USDT:USDT', 'AXL/USDT:USDT', 'ID/USDT:USDT', 'EDU/USDT:USDT',
        'MAV/USDT:USDT', 'CYBER/USDT:USDT', 'ARKM/USDT:USDT', 'GAL/USDT:USDT', 'ARK/USDT:USDT'
    ]
    
    print(f"Total Target Alts: {len(target_symbols)}")
    found_count = 0

    for symbol in target_symbols:
        df = get_df(symbol)
        if df.empty or len(df) < 50: continue
            
        last = df.iloc[-2]
        prev = df.iloc[-3]
        
        rsi, plus_di, adx = last['rsi'], last['plus_di'], last['adx']
        v_now, v_prev = last['volume'], prev['volume']

        # 사용자님 조건 (RSI < 30, +DI > 36, ADX > 20, 거래량 증가)
        if not pd.isna(rsi) and rsi < 30 and plus_di > 36 and adx > 20 and v_now > v_prev:
            found_count += 1
            clean_name = symbol.split('/')[0]
            msg = (f"🚨 [MEGA SIGNAL]\n코인: {clean_name}\n"
                   f"RSI: {round(rsi, 2)} / ADX: {round(adx, 2)}\n"
                   f"+DI: {round(plus_di, 2)}\n거래량 증가 ✅")
            send_telegram(msg)
            print(f"Signal: {clean_name}")

        # 100개나 되므로 API 속도 제한을 위해 약간의 대기시간 추가
        time.sleep(0.12)

    print(f"===== SCAN END (Found: {found_count}) =====")

if __name__ == "__main__":
    run_scan()
