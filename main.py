from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import yfinance as yf
import pandas as pd
import time

app = FastAPI()

PAIRS = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","NZDUSD=X","EURJPY=X","GBPJPY=X","EURGBP=X","AUDJPY=X","EURAUD=X","EURCAD=X","GBPCAD=X","GBPAUD=X","AUDCAD=X","USDCHF=X","EURCHF=X","GBPCHF=X","GC=F"]
NAMES = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","NZDUSD","EURJPY","GBPJPY","EURGBP","AUDJPY","EURAUD","EURCAD","GBPCAD","GBPAUD","AUDCAD","USDCHF","EURCHF","GBPCHF","XAUUSD"]

def calc(pair):
    try:
        df = yf.download(pair, period="5d", interval="1h", progress=False)
        if len(df) < 60: return None
        close = df['Close'].squeeze()
        ema50 = close.ewm(span=50).mean().iloc[-1]
        rsi = 100 - (100 / (1 + close.diff().where(close.diff()>0,0).rolling(14).mean() / -close.diff().where(close.diff()<0,0).rolling(14).mean().abs()))
        rsi = float(rsi.iloc[-1])
        trend = abs(float(close.iloc[-1] - ema50)) / float(close.iloc[-1]) * 1000
        vol = float(close.pct_change().rolling(20).std().iloc[-1]*100)
        score = min(95, trend*2 + (50-abs(rsi-50))*0.6 + vol*5)
        action = "BUY NOW" if close.iloc[-1] > ema50 and rsi < 70 else "SELL NOW" if close.iloc[-1] < ema50 and rsi > 30 else "BUY LIMIT" if close.iloc[-1] > ema50 else "SELL LIMIT"
        return {"score": round(score,1), "price": round(float(close.iloc[-1]),5), "rsi": round(rsi,1), "action": action, "vol": round(vol,2)}
    except: return None

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>RULER TERMINAL</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#0a0a0a;color:#00ff88;font-family:monospace;padding:10px}
table{width:100%;border-collapse:collapse;margin-top:10px}
th{color:#888;text-align:left;padding:8px;border-bottom:1px solid #333}
td{padding:8px;border-bottom:1px solid #222}
.live{color:#00ff88;animation:blink 1s infinite}
@keyframes blink{50%{opacity:0.3}}
#popup{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.92);display:flex;align-items:center;justify-content:center;z-index:9999}
.box{background:#111;border:1px solid #00ff88;padding:20px;max-width:380px;border-radius:12px}
.btn{background:#00ff88;color:#000;padding:10px 18px;border:none;border-radius:8px;font-weight:bold;cursor:pointer;width:100%;margin-top:12px}
</style>
</head>
<body>

<div id="popup">
  <div class="box">
    <h3 style="margin:0">How to use RULER in 30 seconds:</h3>
    <p style="color:#ccc;line-height:1.5;font-size:14px">
    Ruler is not predicting the future.<br><br>
    It scans 19 pairs and checks 3 things:<br>
    <b>1. Is it moving?</b> (Trend)<br>
    <b>2. Is it tired?</b> (Momentum)<br>
    <b>3. Are many people trading it?</b> (Volatility)<br><br>
    Top score = cleanest pair to trade TODAY.<br>
    Use top 3 only. Test with 0.01 lot on demo MT5.<br><br>
    <span style="color:#888">Not financial advice. For education only.</span>
    </p>
    <button class="btn" onclick="closePop()">I UNDERSTAND — SHOW TERMINAL</button>
    <p style="text-align:center;margin-top:10px"><a href="#" onclick="closePop()" style="color:#555;font-size:12px">Don't show again today</a></p>
  </div>
</div>

<h2>RULER TERMINAL <span class="live">● LIVE</span> <span id="timer" style="font-size:12px;color:#888;margin-left:10px">Loading...</span></h2>
<div id="t">Scanning 19 pairs...</div>

<script>
function closePop(){
  document.getElementById('popup').style.display='none';
  localStorage.setItem('ruler_seen', Date.now());
}
if(localStorage.getItem('ruler_seen') && Date.now() - localStorage.getItem('ruler_seen') < 86400000){
  document.getElementById('popup').style.display='none';
}

let lastUpdate = Date.now();
function updateTimer(){
  let s = Math.floor((Date.now()-lastUpdate)/1000);
  document.getElementById('timer').innerText = s<60 ? `Updated ${s}s ago` : `Updated ${Math.floor(s/60)}m ${s%60}s ago • Auto-refresh 60s`;
}
setInterval(updateTimer,1000);

async function load(){
  let r = await fetch('/api/scan'); let d = await r.json();
  d.sort((a,b)=>b.score-a.score);
  let h='<table><tr><th>RANK</th><th>PAIR</th><th>SCORE</th><th>PRICE</th><th>ACTION</th><th>RSI</th></tr>';
  d.forEach((x,i)=>{
    let c = x.score>60?'#00ff88':x.score>45?'#ffcc00':'#888';
    h+=`<tr><td>${i+1}</td><td>${x.name}</td><td style="color:${c};font-weight:bold">${x.score}</td><td>${x.price}</td><td>${x.action}</td><td>${x.rsi}</td></tr>`;
  });
  h+='</table>';
  document.getElementById('t').innerHTML=h;
  lastUpdate=Date.now();
}
load(); setInterval(load,60000);
</script>
</body>
</html>
    """

@app.get("/api/scan")
def scan():
    res=[]
    for p,n in zip(PAIRS,NAMES):
        d=calc(p)
        if d: d["name"]=n; res.append(d)
    return res
