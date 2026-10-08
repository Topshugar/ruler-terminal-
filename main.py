import os, json, time, logging, requests, ccxt, yfinance as yf, pandas as pd, pytz
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

SYMBOLS_CONFIG = {
    "FOREX_MAJORS": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X", "AUDUSD=X", "NZDUSD=X"],
    "FOREX_MINORS_CROSSES": ["EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURAUD=X", "GBPAUD=X", "NZDJPY=X"],
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD"],
    "COMMODITIES_METALS": ["GC=F", "SI=F", "CL=F"],
    "INDICES": ["^DJI", "^GSPC", "^IXIC"]
}

CLEAN_NAMES = {
    "EURUSD=X":"EURUSD","GBPUSD=X":"GBPUSD","USDJPY=X":"USDJPY","USDCHF=X":"USDCHF","USDCAD=X":"USDCAD","AUDUSD=X":"AUDUSD","NZDUSD=X":"NZDUSD",
    "EURGBP=X":"EURGBP","EURJPY=X":"EURJPY","GBPJPY=X":"GBPJPY","AUDJPY=X":"AUDJPY","EURAUD=X":"EURAUD","GBPAUD=X":"GBPAUD","NZDJPY=X":"NZDJPY",
    "BTC-USD":"BTCUSDT","ETH-USD":"ETHUSDT","SOL-USD":"SOLUSDT","XRP-USD":"XRPUSDT","ADA-USD":"ADAUSDT","DOGE-USD":"DOGEUSDT",
    "GC=F":"XAUUSD","SI=F":"XAGUSD","CL=F":"USOIL","^DJI":"US30","^GSPC":"US500","^IXIC":"USTEC"
}

EXCHANGE = getattr(ccxt, os.getenv("CCXT_EXCHANGE", "binance"))()
N8N_WEBHOOK = os.getenv("N8N_WEBHOOK_URL")

def ema(s, l):
    return s.ewm(span=l, adjust=False).mean()

def sma(s, l):
    return s.rolling(l).mean()

def atr(df, l=14):
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift()).abs()
    lc = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(l).mean()

def rsi(s, l=21):
    d = s.diff()
    g = d.clip(lower=0)
    lo = -d.clip(upper=0)
    ag = g.ewm(alpha=1/l, adjust=False).mean()
    al = lo.ewm(alpha=1/l, adjust=False).mean()
    rs = ag / al.replace(0, 1e-10)
    return 100 - (100/(1+rs))

def macd(s):
    e12 = ema(s,12)
    e26 = ema(s,26)
    line = e12-e26
    signal = ema(line,9)
    hist = line-signal
    return line, signal, hist

def fetch_data(symbol):
    try:
        df_4h = yf.download(symbol, period="60d", interval="4h", progress=False, auto_adjust=False)
        df_1d = yf.download(symbol, period="400d", interval="1d", progress=False, auto_adjust=False)
        if df_4h.empty or df_1d.empty:
            return None, None
        if isinstance(df_4h.columns, pd.MultiIndex):
            df_4h.columns = df_4h.columns.get_level_values(0)
        if isinstance(df_1d.columns, pd.MultiIndex):
            df_1d.columns = df_1d.columns.get_level_values(0)
        return df_4h, df_1d
    except Exception as e:
        logging.error(f"Fetch {symbol}: {e}")
        return None, None

def fetch_24h_change(symbol):
    try:
        df = yf.download(symbol, period="2d", interval="1d", progress=False, auto_adjust=False)
        if len(df)>=2:
            return ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2])*100
        return 0.0
    except:
        return 0.0

def evaluate_setup(df_4h, df_1d):
    if len(df_4h) < 100 or len(df_1d) < 210:
        return None, None
    c4 = df_4h['Close']
    c1 = df_1d['Close']
    daily_200_sma = sma(c1, 200).iloc[-1]
    ema34 = ema(c4, 34)
    ema89 = ema(c4, 89)
    e34 = ema34.iloc[-1]
    e89 = ema89.iloc[-1]
    r21 = rsi(c4, 21).iloc[-1]
    m_line, m_signal, m_hist = macd(c4)
    ml = m_line.iloc[-1]
    ms = m_signal.iloc[-1]
    mh = m_hist.iloc[-1]
    ml_prev = m_line.iloc[-2]
    ms_prev = m_signal.iloc[-2]
    atr14 = atr(df_4h, 14).iloc[-1]
    price = float(c4.iloc[-1])

    ctx = {
        "market_price": price,
        "daily_200_sma": float(daily_200_sma),
        "ema_34": float(e34),
        "ema_89": float(e89),
        "rsi_21": float(r21),
        "macd_histogram": float(mh),
        "atr": float(atr14),
        "swing_low": float(df_4h['Low'].tail(10).min()),
        "swing_high": float(df_4h['High'].tail(10).max()),
        "macd_line": float(ml),
        "macd_signal": float(ms)
    }

    macd_cross_up = ml_prev < ms_prev and ml > ms
    if price > daily_200_sma and e34 > e89 and macd_cross_up and mh > 0:
        return {"type": "BUY_LIMIT"}, ctx

    macd_cross_down = ml_prev > ms_prev and ml < ms
    if price < daily_200_sma and e34 < e89 and macd_cross_down and mh < 0:
        return {"type": "SELL_LIMIT"}, ctx

    return None, ctx

def calculate_trade(signal_type, ctx):
    price = ctx['market_price']
    atr_buf = ctx['atr'] * 1.5
    entry = ctx['ema_34']

    if signal_type == "BUY_LIMIT":
        sl = ctx['swing_low'] - atr_buf
        risk = entry - sl
        if risk <=0:
            risk = atr_buf
        be = entry + risk
        tp1 = entry + (risk * 2.0)
        tp2 = entry + (risk * 3.5)
    else:
        sl = ctx['swing_high'] + atr_buf
        risk = sl - entry
        if risk <=0:
            risk = atr_buf
        be = entry - risk
        tp1 = entry - (risk * 2.0)
        tp2 = entry - (risk * 3.5)

    return {
        "market_price": round(price, 5),
        "limit_entry_price": round(entry, 5),
        "stop_loss": round(sl, 5),
        "break_even_price": round(be, 5),
        "take_profit_1": round(tp1, 5),
        "take_profit_2": round(tp2, 5)
    }

def scan_extremes(df_4h, df_1d, change_24h, ctx):
    if not ctx:
        return None
    r = ctx['rsi_21']
    mh = ctx['macd_histogram']
    price = ctx['market_price']
    sma200 = ctx['daily_200_sma']

    try:
        c4 = df_4h['Close']
        _, _, hist = macd(c4)
        mh_prev = hist.iloc[-2]
        curling_up = mh > mh_prev
    except:
        curling_up = False

    if r <= 35:
        return {"signal_type": "OVERSOLD", "rsi": r, "change_24h": change_24h}
    if r >= 65:
        return {"signal_type": "OVERBOUGHT", "rsi": r, "change_24h": change_24h}
    if change_24h <= -6 and price > sma200 and curling_up:
        return {"signal_type": "CRYPTO_DIP", "rsi": r, "change_24h": change_24h}
    return None

def log_signal(payload):
    json_str = json.dumps(payload, indent=2)
    logging.info(f"\n{json_str}\n")
    if N8N_WEBHOOK:
        try:
            requests.post(N8N_WEBHOOK, json=payload, timeout=10)
        except Exception as e:
            logging.error(f"Webhook error: {e}")

def build_payload(category, symbol_raw, signal_type, exec_params, indicators, scanner_meta=None):
    symbol = CLEAN_NAMES.get(symbol_raw, symbol_raw)
    return {
        "timestamp": datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "category_group": category,
        "symbol": symbol,
        "signal_type": signal_type,
        "timeframe": "4H",
        "execution_parameters": exec_params,
        "indicators": indicators,
        "scanner_meta": scanner_meta
    }

def run_scan():
    print("=== 4H Swing Engine Scan Started ===", flush=True)
    for category, symbols in SYMBOLS_CONFIG.items():
        for sym_raw in symbols:
            try:
                df_4h, df_1d = fetch_data(sym_raw)
                if df_4h is None:
                    continue

                signal, ctx = evaluate_setup(df_4h, df_1d)

                if signal:
                    exec_params = calculate_trade(signal['type'], ctx)
                    indicators = {
                        "daily_200_sma": ctx['daily_200_sma'],
                        "ema_34": ctx['ema_34'],
                        "ema_89": ctx['ema_89'],
                        "rsi_21": ctx['rsi_21'],
                        "macd_histogram": ctx['macd_histogram']
                    }
                    payload = build_payload(category, sym_raw, signal['type'], exec_params, indicators)
                    log_signal(payload)
                    continue

                chg = fetch_24h_change(sym_raw)
                scan = scan_extremes(df_4h, df_1d, chg, ctx)
                if scan:
                    indicators = {
                        "daily_200_sma": ctx['daily_200_sma'] if ctx else 0,
                        "ema_34": ctx['ema_34'] if ctx else 0,
                        "ema_89": ctx['ema_89'] if ctx else 0,
                        "rsi_21": scan.get('rsi', ctx['rsi_21'] if ctx else 0),
                        "macd_histogram": ctx['macd_histogram'] if ctx else 0
                    }
                    exec_params = {
                        "market_price": ctx['market_price'] if ctx else 0,
                        "limit_entry_price": 0,
                        "stop_loss": 0,
                        "break_even_price": 0,
                        "take_profit_1": 0,
                        "take_profit_2": 0
                    }
                    payload = build_payload(category, sym_raw, scan['signal_type'], exec_params, indicators, scanner_meta=scan)
                    log_signal(payload)

                time.sleep(0.4)
            except Exception as e:
                print(f"[Error] {sym_raw}: {e}", flush=True)
                continue

if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_scan, 'cron', hour='0,4,8,12,16,20', minute='2')
    print("Bot online. Next run on 4H close.", flush=True)
    run_scan()
    scheduler.start()
