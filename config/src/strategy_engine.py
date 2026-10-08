import pandas as pd
import pandas_ta as ta

class StrategyEngine:
    @staticmethod
    def add_indicators(df_4h: pd.DataFrame, df_1d: pd.DataFrame):
        df_4h['ema34'] = ta.ema(df_4h['close'], length=34)
        df_4h['ema89'] = ta.ema(df_4h['close'], length=89)
        df_4h['rsi21'] = ta.rsi(df_4h['close'], length=21)
        df_4h['atr14'] = ta.atr(df_4h['high'], df_4h['low'], df_4h['close'], length=14)

        macd = ta.macd(df_4h['close'], fast=12, slow=26, signal=9)
        df_4h['macd'] = macd['MACD_12_26_9']
        df_4h['macd_signal'] = macd['MACDs_12_26_9']
        df_4h['macd_hist'] = macd['MACDh_12_26_9']

        df_1d['sma200'] = ta.sma(df_1d['close'], length=200)
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
            "market_price": float(last['close'])
        }

        above = daily['close'] > daily['sma200']
        below = daily['close'] < daily['sma200']

        bullish_cross = prev['macd'] < prev['macd_signal'] and last['macd'] > last['macd_signal']
        bearish_cross = prev['macd'] > prev['macd_signal'] and last['macd'] < last['macd_signal']

        if above and last['ema34'] > last['ema89'] and bullish_cross and last['macd_hist'] > 0:
            return {"type": "BUY_LIMIT", "trend": f"Above Daily 200 SMA ({daily['sma200']:.4f})"}, context

        if below and last['ema34'] < last['ema89'] and bearish_cross and last['macd_hist'] < 0:
            return {"type": "SELL_LIMIT", "trend": f"Below Daily 200 SMA ({daily['sma200']:.4f})"}, context

        return None, context
