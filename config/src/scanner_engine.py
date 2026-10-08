import pandas as pd
from typing import Tuple, Optional, Dict, Any

class StrategyEngine:

    @staticmethod
    def ema(series: pd.Series, length: int):
        return series.ewm(span=length, adjust=False).mean()

    @staticmethod
    def sma(series: pd.Series, length: int):
        return series.rolling(window=length).mean()

    @staticmethod
    def rsi(series: pd.Series, length: int = 21):
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=length-1, adjust=False).mean()
        avg_loss = loss.ewm(com=length-1, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14):
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(alpha=1/length, adjust=False).mean()

    @staticmethod
    def macd(close: pd.Series, fast=12, slow=26, signal=9):
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return macd_line, signal_line, hist

    @staticmethod
    def add_indicators(df_4h: pd.DataFrame, df_1d: pd.DataFrame):
        df_4h['ema34'] = StrategyEngine.ema(df_4h['close'], 34)
        df_4h['ema89'] = StrategyEngine.ema(df_4h['close'], 89)
        df_4h['rsi21'] = StrategyEngine.rsi(df_4h['close'], 21)
        df_4h['atr14'] = StrategyEngine.atr(df_4h['high'], df_4h['low'], df_4h['close'], 14)
        macd, sig, hist = StrategyEngine.macd(df_4h['close'])
        df_4h['macd'] = macd
        df_4h['macd_signal'] = sig
        df_4h['macd_hist'] = hist

        df_1d['sma200'] = StrategyEngine.sma(df_1d['close'], 200)
        return df_4h, df_1d

    @staticmethod
    def evaluate(df_4h, df_1d):
        if df_4h is None or df_1d is None or len(df_4h) < 100 or len(df_1d) < 200:
            return None, None

        df_4h, df_1d = StrategyEngine.add_indicators(df_4h.copy(), df_1d.copy())
        last = df_4h.iloc[-1]
        prev = df_4h.iloc[-2]
        daily = df_1d.iloc[-1]

        if pd.isna(last['ema34']) or pd.isna(daily['sma200']):
            return None, None

        context = {
            "daily_200_sma": float(daily['sma200']),
            "ema_34": float(last['ema34']),
            "ema_89": float(last['ema89']),
            "rsi_21": float(last['rsi21']),
            "macd_histogram": float(last['macd_hist']),
            "atr": float(last['atr14']),
            "swing_low": float(df_4h['low'].tail(20).min()),
            "swing_high": float(df_4h['high'].tail(20).max()),
            "market_price": float(last['close']),
            "daily_close": float(daily['close'])
        }

        above = context['daily_close'] > context['daily_200_sma']
        below = context['daily_close'] < context['daily_200_sma']

        bullish_cross = prev['macd'] < prev['macd_signal'] and last['macd'] > last['macd_signal']
        bearish_cross = prev['macd'] > prev['macd_signal'] and last['macd'] < last['macd_signal']

        if above and last['ema34'] > last['ema89'] and bullish_cross and last['macd_hist'] > 0:
            return {"type": "BUY_LIMIT"}, context
        if below and last['ema34'] < last['ema89'] and bearish_cross and last['macd_hist'] < 0:
            return {"type": "SELL_LIMIT"}, context

        return None, context
