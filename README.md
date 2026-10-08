## Deploy to Render
1. Push to GitHub
2. Render > New > Background Worker
3. Build: pip install -r requirements.txt
4. Start: python main.py (from Procfile)
5. ENV: CCXT_EXCHANGE=binance
6. Logs: View JSON signals in Render Logs or download signals.jsonl

Output is JSONL - plug directly into your backend DB/API.
