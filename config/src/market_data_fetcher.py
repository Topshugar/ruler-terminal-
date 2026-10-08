import ccxt
import yfinance as yf
import pandas as pd
import json

with open("config/symbols_config.json") as f:
    SYMBOL_MAP = json.load(f)["YFINANCE_MAP"]

class MarketDataFetcher:
    def __init__(self, exchange_id='binance'):
        self.exchange = getattr(ccxt, exchange_id)({
            'enableRateLimit': True,
        })

    def fetch_crypto_ohlcv(self, symbol, timeframe='4h', limit=300):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"[Fetcher] CCXT Error {symbol}: {e}")
            return None

    def fetch_yfinance_ohlcv(self, symbol, is_4h=True):
        ticker = SYMBOL_MAP.get(symbol, symbol)
        try:
            interval = "60m" if is_4h else "1d"
            period = "60d" if is_4h else "2y"
            df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
            if df.empty: return None
            df.columns = [c.lower() for c in df.columns]
            if 'datetime' in df.columns or 'date' in str(df.index.name).lower():
                df.reset_index(inplace=True)
            else:
                df.reset_index(inplace=True)

            col = df.columns[0]
            df.rename(columns={col: 'timestamp'}, inplace=True)

            if is_4h:
                df.set_index('timestamp', inplace=True)
                df = df.resample('4h').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna().reset_index()
            return df
        except Exception as e:
            print(f"[Fetcher] yfinance Error {symbol}: {e}")
            return None

    def fetch(self, symbol, is_crypto=False):
        df_4h = self.fetch_crypto_ohlcv(symbol, '4h') if is_crypto else self.fetch_yfinance_ohlcv(symbol, True)
        df_1d = self.fetch_crypto_ohlcv(symbol, '1d') if is_crypto else self.fetch_yfinance_ohlcv(symbol, False)
        return df_4h, df_1d

    def fetch_24h_change_crypto(self, symbol):
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker.get('percentage', 0) or 0)
        except:
            return 0.0
