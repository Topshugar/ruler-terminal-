import json
import os
from datetime import datetime
import pytz
from config.settings import settings

class SignalLogger:
    def __init__(self):
        self.log_file = settings.SIGNALS_LOG_FILE

    def build_payload(self, category, symbol, signal_type, execution_params, indicators, extra=None):
        payload = {
            "timestamp": datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "category_group": category,
            "symbol": symbol,
            "signal_type": signal_type,
            "timeframe": "4H",
            "execution_parameters": execution_params,
            "indicators": indicators
        }
        if extra:
            payload.update(extra)
        return payload

    def log(self, payload: dict):
        # 1. Print to stdout for Render logs
        print(json.dumps(payload, indent=2))

        # 2. Append to JSONL for persistence
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as e:
            print(f"[Logger] File write failed: {e}")

        return payload
