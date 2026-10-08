class TradeCalculator:
    @staticmethod
    def calculate(signal_type: str, context: dict):
        entry = context['ema_34']
        atr = context['atr']
        is_buy = signal_type == 'BUY_LIMIT'

        if is_buy:
            sl = context['swing_low'] - (1.5 * atr)
            risk = entry - sl
        else:
            sl = context['swing_high'] + (1.5 * atr)
            risk = sl - entry

        if risk <= 0:
            risk = atr * 1.5

        be = entry + risk if is_buy else entry - risk
        tp1 = entry + (risk * 2.0) if is_buy else entry - (risk * 2.0)
        tp2 = entry + (risk * 3.5) if is_buy else entry - (risk * 3.5)

        return {
            "market_price": round(context['market_price'], 5),
            "limit_entry_price": round(entry, 5),
            "stop_loss": round(sl, 5),
            "break_even_price": round(be, 5),
            "take_profit_1": round(tp1, 5),
            "take_profit_2": round(tp2, 5),
            "risk_value": round(risk, 5)
          }
