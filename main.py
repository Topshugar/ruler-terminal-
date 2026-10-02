from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import yfinance as yf
from core.scoring import ruler_score
from datetime import datetime
import time

app = FastAPI()
PAIRS = ["EURJPY=X","GBPJPY=X","CADJPY=X","AUDJPY=X","USDJPY=X","CHFJPY=X","NZDJPY=X","EURUSD=X","GBPUSD=X","AUDUSD=X","NZDUSD=X","USDCAD=X","USDCHF=X","EURGBP=X","EURCAD=X","EURAUD=X","GBPCAD=X","GBPAUD=X","GC=F"]

@app.get("/api/ranking")
def ranking():
    res = []
    for t in PAIRS:
        try:
            df = yf.download(t, period="5d", interval="1h", progress=False, auto_adjust=False, threads=False)
            time.sleep(0.3)
            if df is None or df.empty:
                continue
            s = ruler_score(df)
            if s and s.get("price", 0)!= 0:
                s["pair"] = t.replace("=X","").replace("GC=F","XAUUSD")
                res.append(s)
        except Exception as e:
            continue
    res = sorted(res, key=lambda x: x["score"], reverse=True)
    if not res:
        res = [{"pair":"DEBUG","score":99.9,"price":1.2345,"rsi":55.5,"vol":"+5%","action":"YAHOO BLOCK - RETRY","ema":"WAIT"}]
    return {"time": datetime.now().strftime("%H:%M:%S"), "ranking": res}

@app.get("/", response_class=HTMLResponse)
def terminal():
    return """<!DOCTYPE html><html><head><title>RULER</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{background:#000;color:#0f0;font-family:monospace;padding:12px;font-size:13px} table{width:100%;border-collapse:collapse} th{color:#888;text-align:left;padding:6px} td{border-bottom:1px solid #111;padding:8px 6px}.hi{color:#0f0;font-weight:bold}.buy{color:#0ff}.sell{color:#f33}</style></head><body>
<h3 style="margin:0 0 10px 0">RULER TERMINAL v1.1 <span id="t" style="color:#888"></span></h3><table><thead><tr><th>#</th><th>PAIR</th><th>SCORE</th><th>PRICE</th><th>RSI</th><th>VOL</th><th>ACTION</th></tr></thead><tbody id="b"><tr><td colspan=7>Loading Yahoo... 10 sec</td></tr></tbody></table>
<script>async function l(){try{let r=await fetch('/api/ranking');let d=await r.json();document.getElementById('t').innerText=d.time+' LIVE';let h='';d.ranking.forEach((x,i)=>{let c=x.action.includes('BUY')?'buy':x.action.includes('SELL')?'sell':'hi';h+=`<tr><td>${i+1}</td><td>${x.pair}</td><td class="${c}">${x.score}</td><td>${x.price}</td><td>${x.rsi}</td><td>${x.vol}</td><td class="${c}">${x.action}</td></tr>`});document.getElementById('b').innerHTML=h}catch(e){document.getElementById('b').innerHTML='<tr><td colspan=7>Retrying Yahoo... '+e+'</td></tr>'}}l();setInterval(l,60000)</script></body></html>"""
