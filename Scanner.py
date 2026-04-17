import requests
import time
import pandas as pd
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

cooldown = {}

# === TELEGRAM ===
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# === EMA ===
def ema(series, period=20):
    return series.ewm(span=period, adjust=False).mean()

# === BINANCE SYMBOLS ===
def get_binance_symbols():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    data = requests.get(url).json()
    return [
        s['symbol'] for s in data['symbols']
        if s['quoteAsset'] == "USDT" and s['status'] == "TRADING"
    ]

# === BYBIT SYMBOLS ===
def get_bybit_symbols():
    url = "https://api.bybit.com/v5/market/instruments-info"
    params = {"category": "linear"}
    data = requests.get(url, params=params).json()
    return [s['symbol'] for s in data['result']['list'] if "USDT" in s['symbol']]

# === KUCOIN SYMBOLS ===
def get_kucoin_symbols():
    url = "https://api.kucoin.com/api/v1/symbols"
    data = requests.get(url).json()
    return [
        s['symbol'].replace("-", "")
        for s in data['data']
        if s['quoteCurrency'] == "USDT" and s['enableTrading']
    ]

# === GET DATA (generic) ===
def get_klines(exchange, symbol):
    try:
        if exchange == "binance":
            url = "https://api.binance.com/api/v3/klines"
            params = {"symbol": symbol, "interval": "5m", "limit": 50}
            data = requests.get(url, params=params).json()

        elif exchange == "bybit":
            url = "https://api.bybit.com/v5/market/kline"
            params = {"category": "linear", "symbol": symbol, "interval": "5", "limit": 50}
            data = requests.get(url, params=params).json()['result']['list']

        elif exchange == "kucoin":
            url = f"https://api.kucoin.com/api/v1/market/candles"
            params = {"symbol": symbol.replace("USDT","-USDT"), "type": "5min"}
            data = requests.get(url, params=params).json()['data']

        df = pd.DataFrame(data)
        df = df.iloc[:, :6]
        df.columns = ["time","open","high","low","close","volume"]
        df = df.astype(float)
        df = df[::-1]

        return df
    except:
        return None

# === DETECTION ===
def detect_runner(df, key):
    if df is None or len(df) < 30:
        return False

    last = df.iloc[-1]

    df['ema20'] = ema(df['close'])

    # === TREND ===
    trend = last['close'] > df['ema20'].iloc[-1]

    # === VOLUME SPIKE ===
    avg_vol = df['volume'][-20:-1].mean()
    vol_spike = last['volume'] > avg_vol * 3

    # === BREAKOUT ===
    recent_high = df['high'][-20:-1].max()
    breakout = last['close'] > recent_high

    # === STRONG CANDLE ===
    body = abs(last['close'] - last['open'])
    rng = last['high'] - last['low']
    strong = body > rng * 0.6

    # === VOLATILITY EXPANSION ===
    recent_range = (df['high'][-10:-1] - df['low'][-10:-1]).mean()
    expansion = rng > recent_range * 1.8

    # === "WHALE ACTIVITY" PROXY ===
    whale = last['volume'] > avg_vol * 4

    # === COOLDOWN ===
    now = time.time()
    if key in cooldown and now - cooldown[key] < 1800:
        return False

    if trend and vol_spike and breakout and strong and expansion:
        cooldown[key] = now
        return True, whale

    return False, False

# === MAIN ===
print("ULTIMATE SCANNER RUNNING...")

binance = get_binance_symbols()
bybit = get_bybit_symbols()
kucoin = get_kucoin_symbols()

while True:
    try:
        # BINANCE
        for s in binance:
            df = get_klines("binance", s)
            result, whale = detect_runner(df, f"binance_{s}")

            if result:
                price = df.iloc[-1]['close']
                send_telegram(f"""
🚀 BINANCE RUNNER

{s}
Price: {price}
Whale Activity: {"YES" if whale else "NO"}
""")

            time.sleep(0.1)

        # BYBIT
        for s in bybit:
            df = get_klines("bybit", s)
            result, whale = detect_runner(df, f"bybit_{s}")

            if result:
                price = df.iloc[-1]['close']
                send_telegram(f"""
🚀 BYBIT RUNNER

{s}
Price: {price}
Whale Activity: {"YES" if whale else "NO"}
""")

            time.sleep(0.1)

        # KUCOIN
        for s in kucoin:
            df = get_klines("kucoin", s)
            result, whale = detect_runner(df, f"kucoin_{s}")

            if result:
                price = df.iloc[-1]['close']
                send_telegram(f"""
🚀 KUCOIN RUNNER

{s}
Price: {price}
Whale Activity: {"YES" if whale else "NO"}
""")

            time.sleep(0.1)

        print("Full scan complete...")

    except Exception as e:
        print("Error:", e)

    time.sleep(300)