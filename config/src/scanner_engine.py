import pandas_ta as ta

class ScannerEngine:
    @staticmethod
    def scan(df_4h, df_1d, change_24h=0.0):
        if df_4h is None: return None

        # Ensure RSI exists
        if 'rsi21' not in df_4h.columns:
            df_4h['rsi21'] = ta.rsi(df_4h['close'], length=21)

        last = df_4h.iloc[-1]
        rsi = float(last['rsi21']) if 'rsi21' in last else 50

        if rsi <= 35:
            return {"signal_type": "OVERSOLD", "rsi": rsi}
        if rsi >= 65:
            return {"signal_type": "OVERBOUGHT", "rsi": rsi}

        # Crypto Dip Logic
        if change_24h <= -6.0 and df_1d is not None:
            if 'sma200' not in df_1d.columns:
                df_1d['sma200'] = ta.sma(df_1d['close'], length=200)

            macd = ta.macd(df_4h['close'], fast=12, slow=26, signal=9)
            if macd is not None and len(macd) >= 2:
                hist_now = macd['MACDh_12_26_9'].iloc[-1]
                hist_prev = macd['MACDh_12_26_9'].iloc[-2]
                is_uptrend = df_1d.iloc[-1]['close'] > df_1d.iloc[-1]['sma200']
                if is_uptrend and hist_now > hist_prev:
                    return {"signal_type": "CRYPTO_DIP", "change_24h": change_24h}

        return None
