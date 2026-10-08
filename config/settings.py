import os
from dotenv import load_dotenv
load_dotenv()

class Settings:
    CCXT_EXCHANGE = os.getenv("CCXT_EXCHANGE", "binance")
    CCXT_API_KEY = os.getenv("CCXT_API_KEY")
    CCXT_SECRET = os.getenv("CCXT_SECRET")
    TIMEZONE = "UTC"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    SIGNALS_LOG_FILE = os.getenv("SIGNALS_LOG_FILE", "signals.jsonl")

settings = Settings()
