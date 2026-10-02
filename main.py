from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import yfinance as yf
from core.scoring import ruler_score
from datetime import datetime

app = FastAPI()

PAIRS = ["EURJPY=X","GBPJPY=X","CADJPY=X","AUDJPY=X","USDJPY=X","CHFJPY=X","NZDJPY=X","EURUSD=X","GBPUSD=X","AUDUSD=X","NZDUSD=X","USDCAD=X","USDCHF=X","EURGBP=X","EURCAD=X","EURAUD=X","GBPCAD=X","GBPAUD=X","GC=F"]

@app.get("/api/ranking")
def ranking():
    res = []
    for t in PAIRS:
        try:
            df = yf.download(t, period="5d", interval="30m", progress=False, auto_adjust=True)
            s = ruler_score(df)
            if s:
                s["pair"] = t.replace("=X","").replace("GC=F","XAUUSD")
                res.append(s)
        except:
            continue
    res = sorted(res, key=lambda x: x["score"], reverse=True)
    return {"time": datetime.now().strftime("%H:%M:%S"), "ranking": res}

@app.get("/", response_class=HTMLResponse)
def terminal():
    return """<!DOCTYPE html><html><head><title>RULER</title>
<style>body{background:#000;color:#0f0;font-family:monospace;padding:12px} table{width:100%} th{color:#888} td{border-bottom:1px solid #111;padding:6px} .hi{color:#0f0;font-weight:bold}</style></head><body>
<h3>RULER TERMINAL v1.0 <span id="t"></span></h3><table><thead><tr><th>#</th><th>PAIR</th><th>SCORE</th><th>PRICE</th><th>RSI</th><th>VOL</th><th>ACTION</th></tr></thead><tbody id="b"></tbody></table>
<script>async function l(){let r=await fetch('/api/ranking');let d=await r.json();document.getElementById('t').innerText=d.time+' LIVE';let h='';d.ranking.forEach((x,i)=>{h+=`<tr><td>${i+1}</td><td>${x.pair}</td><td class="hi">${x.score}</td><td>${x.price}</td><td>${x.rsi}</td><td>${x.vol}</td><td>${x.action}</td></tr>`});document.getElementById('b').innerHTML=h}l();setInterval(l,60000)</script></body></html>"""
