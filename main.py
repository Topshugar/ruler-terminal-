import json, time
from apscheduler.schedulers.blocking import BlockingScheduler
from config.settings import settings
from src.market_data_fetcher import MarketDataFetcher
from src.strategy_engine import StrategyEngine
from src.trade_calculator import TradeCalculator
from src.scanner_engine import ScannerEngine
from src.signal_logger import SignalLogger

with open("config/symbols_config.json") as f:
    CONFIG = json.load(f)

fetcher = MarketDataFetcher(settings.CCXT_EXCHANGE)
logger = SignalLogger()

def run_scan():
    print("=== 4H Swing Engine Scan Started ===")
    for category, symbols in CONFIG.items():
        if category == "YFINANCE_MAP": continue
        for symbol in symbols:
            is_crypto = category == "CRYPTO"
            df_4h, df_1d = fetcher.fetch(symbol, is_crypto=is_crypto)
            if df_4h is None or df_1d is None:
                continue

            signal, ctx = StrategyEngine.evaluate(df_4h, df_1d)

            if signal:
                exec_params = TradeCalculator.calculate(signal['type'], ctx)
                indicators = {
                    "daily_200_sma": ctx['daily_200_sma'],
                    "ema_34": ctx['ema_34'],
                    "ema_89": ctx['ema_89'],
                    "rsi_21": ctx['rsi_21'],
                    "macd_histogram": ctx['macd_histogram']
                }
                payload = logger.build_payload(
                    category_group=category,
                    symbol=symbol,
                    signal_type=signal['type'],
                    execution_params=exec_params,
                    indicators=indicators
                )
                logger.log(payload)
                continue

            # Scanner only if no primary signal
            change = fetcher.fetch_24h_change_crypto(symbol) if is_crypto else 0.0
            scan = ScannerEngine.scan(df_4h, df_1d, change)
            if scan:
                indicators = {
                    "daily_200_sma": ctx['daily_200_sma'] if ctx else 0,
                    "ema_34": ctx['ema_34'] if ctx else 0,
                    "ema_89": ctx['ema_89'] if ctx else 0,
                    "rsi_21": scan.get('rsi', ctx['rsi_21'] if ctx else 0),
                    "macd_histogram": ctx['macd_histogram'] if ctx else 0
                }
                payload = logger.build_payload(
                    category_group=category,
                    symbol=symbol,
                    signal_type=scan['signal_type'],
                    execution_params={
                        "market_price": ctx['market_price'] if ctx else 0,
                        "limit_entry_price": 0,
                        "stop_loss": 0,
                        "break_even_price": 0,
                        "take_profit_1": 0,
                        "take_profit_2": 0
                    },
                    indicators=indicators,
                    extra={"scanner_meta": scan}
                )
                logger.log(payload)

            time.sleep(0.3)

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(run_scan, 'cron', hour='0,4,8,12,16,20', minute='2', timezone='UTC')
    print("Bot online. Next run on 4H close.")
    run_scan()
    scheduler.start()
