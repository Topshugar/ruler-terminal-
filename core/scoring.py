import pandas as pd
import numpy as np

def calc_rsi(s, p=14):
    d = s.diff()
    g = d.where(d > 0, 0).rolling(p).mean()
    l = -d.where(d < 0, 0).rolling(p).mean()
    rs = g / l
    return 100 - (100 / (1 + rs))

def ruler_score(df):
    try:
        close = df['Close'].squeeze()
        if len(close) < 50:
            return None
        ema = close.ewm(span=50).mean()
        rsi = calc_rsi(close)
        price = float(close.iloc[-1])
        ema_v = float(ema.iloc[-1])
        rsi_v = float(rsi.iloc[-1])
        
        is_bear = price < ema_v
        trend_strength = min(40, abs(price - ema_v) / price * 5000)
        
        if is_bear:
            rsi_edge = min(30, max(0, 50 - rsi_v) * 1.5)
            action = "SELL NOW" if (trend_strength + rsi_edge) > 35 else "SELL LIMIT"
            ema_label = "BEAR"
        else:
            rsi_edge = min(30, max(0, rsi_v - 50) * 1.5)
            action = "BUY NOW" if (trend_strength + rsi_edge) > 35 else "BUY LIMIT"
            ema_label = "BULL"
        
        vol_today = float((df['High'] - df['Low']).tail(48).mean())
        vol_avg = float((df['High'] - df['Low']).tail(200).mean())
        vol_bonus = min(20, max(0, (vol_today / vol_avg - 1) * 100)) if vol_avg > 0 else 0
        
        score = trend_strength + rsi_edge + vol_bonus
        
        vol_pct = round((vol_today / vol_avg - 1) * 100) if vol_avg else 0
        sign = "+" if vol_pct > 0 else ""
        vol_label = f"{sign}{vol_pct}%"

        return {
            "price": round(price, 4),
            "rsi": round(rsi_v, 1),
            "ema": ema_label,
            "vol": vol_label,
            "score": round(float(score), 1),
            "action": action,
            "is_bear": is_bear
        }
    except:
        return None
