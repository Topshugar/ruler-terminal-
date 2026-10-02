from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import yfinance as yf

app = FastAPI()

PAIRS = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","NZDUSD=X","EURJPY=X","GBPJPY=X","EURGBP=X","AUDJPY=X","EURAUD=X","EURCAD=X","GBPCAD=X","GBPAUD=X","AUDCAD=X","USDCHF=X","EURCHF=X","GBPCHF=X","GC=F"]
NAMES = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","NZDUSD","EURJPY","GBPJPY","EURGBP","AUDJPY","EURAUD","EURCAD","GBPCAD","GBPAUD","AUDCAD","USDCHF","EURCHF","GBPCHF","XAUUSD"]

USDT_TRC20 = "TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4"
USDT_BEP20 = "0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5"

def rsi_label(r):
    if r >= 70: return f"{r} - TIRED (Don't Buy)", "#ff4444"
    if r >= 60: return f"{r} - Getting Tired", "#ffcc00"
    if r >= 45: return f"{r} - FRESH (Good)", "#00ff88"
    if r >= 30: return f"{r} - Weak", "#ffcc00"
    return f"{r} - OVERSOLD (Don't Sell)", "#ff4444"

def calc(pair):
    try:
        df = yf.download(pair, period="5d", interval="1h", progress=False)
        if len(df) < 60: return None
        close = df['Close'].squeeze()
        ema50 = close.ewm(span=50).mean().iloc[-1]
        diff = close.diff()
        up = diff.where(diff>0,0).rolling(14).mean()
        down = -diff.where(diff<0,0).rolling(14).mean()
        rsi = 100 - (100/(1+up/down))
        rsi_v = round(float(rsi.iloc[-1]),1)
        trend = abs(float(close.iloc[-1] - ema50))/float(close.iloc[-1])*1000
        vol = float(close.pct_change().rolling(20).std().iloc[-1]*100)
        score = min(95, trend*2 + (50-abs(rsi_v-50))*0.6 + vol*5)
        action = "BUY NOW" if close.iloc[-1] > ema50 and rsi_v < 70 else "SELL NOW" if close.iloc[-1] < ema50 and rsi_v > 30 else "BUY LIMIT" if close.iloc[-1] > ema50 else "SELL LIMIT"
        label,color = rsi_label(rsi_v)
        return {"score": round(score,1), "price": round(float(close.iloc[-1]),5), "rsi_text": label, "rsi_color": color, "action": action}
    except: return None

@app.get("/", response_class=HTMLResponse)
def home():
    return f"""
<html><head><title>RULER TERMINAL</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{background:#0a0a0a;color:#00ff88;font-family:monospace;padding:10px;padding-bottom:90px}}
table{{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}}th{{color:#888;text-align:left;padding:8px;border-bottom:1px solid #333}}td{{padding:8px;border-bottom:1px solid #222}}
.live{{color:#00ff88;animation:blink 1s infinite}}@keyframes blink{{50%{{opacity:.3}}}}
#popup{{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.92);display:flex;align-items:center;justify-content:center;z-index:9999}}
.box{{background:#111;border:1px solid #00ff88;padding:20px;max-width:380px;border-radius:12px}}
.btn{{background:#00ff88;color:#000;padding:10px;border:none;border-radius:8px;font-weight:bold;width:100%;margin-top:12px;cursor:pointer}}
.donate-bar{{position:fixed;bottom:0;left:0;width:100%;background:#111;border-top:1px solid #00ff88;padding:10px 12px;display:flex;gap:8px;align-items:center;justify-content:space-between;z-index:500}}
.donate-btn{{padding:8px 12px;border-radius:8px;border:none;font-weight:bold;cursor:pointer;font-size:12px}}
#qrModal{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.95);z-index:10000;align-items:center;justify-content:center}}
.tab{{padding:8px 12px;border:1px solid #333;border-radius:8px;cursor:pointer;color:#888;font-size:12px}} .tab.active{{background:#00ff88;color:#000;border-color:#00ff88}}
</style></head><body>

<div id="popup"><div class="box">
<h3 style="margin:0">How to use RULER</h3>
<p style="color:#ccc;font-size:13px;line-height:1.5">🟢 FRESH (45-60) = Best entry<br>🟡 Tired = Wait<br>🔴 TIRED >70 = Don't Buy<br>🔴 OVERSOLD <30 = Don't Sell<br><br>Trade TOP 3 only - 0.01 lot</p>
<button class="btn" onclick="localStorage.setItem('ruler_seen',Date.now());document.getElementById('popup').style.display='none'">I UNDERSTAND</button>
</div></div>

<div id="qrModal" onclick="if(event.target.id=='qrModal')this.style.display='none'"><div class="box" style="text-align:center;max-width:360px">
<h3 style="margin:0">Support RULER 💚</h3>
<div style="display:flex;gap:8px;justify-content:center;margin:14px 0">
  <div id="tabTRC" class="tab active" onclick="showChain('TRC')">TRC20</div>
  <div id="tabBEP" class="tab" onclick="showChain('BEP')">BEP20</div>
</div>
<div id="chainTRC">
  <p style="color:#888;font-size:9px;word-break:break-all">{USDT_TRC20}</p>
  <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={USDT_TRC20}" style="border:8px solid white;border-radius:8px">
  <p style="color:#00ff88;font-size:11px">TRON • Low fee</p>
  <button class="btn" onclick="navigator.clipboard.writeText('{USDT_TRC20}');alert('TRC20 Copied!')">Copy TRC20 Address</button>
</div>
<div id="chainBEP" style="display:none">
  <p style="color:#888;font-size:9px;word-break:break-all">{USDT_BEP20}</p>
  <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={USDT_BEP20}" style="border:8px solid white;border-radius:8px">
  <p style="color:#ffcc00;font-size:11px">BNB Smart Chain • BEP20</p>
  <button class="btn" style="background:#ffcc00" onclick="navigator.clipboard.writeText('{USDT_BEP20}');alert('BEP20 Copied!')">Copy BEP20 Address</button>
</div>
<p style="color:#555;font-size:10px;margin-top:12px">Make sure you select correct network in wallet</p>
</div></div>

<h2>RULER TERMINAL <span class="live">● LIVE</span> <span id="timer" style="font-size:11px;color:#888;margin-left:8px"></span></h2>
<div id="t">Scanning 19 pairs...</div>

<div class="donate-bar">
  <span style="font-size:11px;color:#ccc">Profit today? Fuel radar ⛽</span>
  <div style="display:flex;gap:6px">
    <button class="donate-btn" style="background:#00ff88" onclick="document.getElementById('qrModal').style.display='flex'">💚 Donate USDT</button>
  </div>
</div>

<script>
function showChain(c){{document.getElementById('chainTRC').style.display=c=='TRC'?'block':'none';document.getElementById('chainBEP').style.display=c=='BEP'?'block':'none';document.getElementById('tabTRC').className=c=='TRC'?'tab active':'tab';document.getElementById('tabBEP').className=c=='BEP'?'tab active':'tab';}}
if(localStorage.getItem('ruler_seen') && Date.now()-localStorage.getItem('ruler_seen')<86400000){{document.getElementById('popup').style.display='none';}}
let last=Date.now();setInterval(()=>{{let s=Math.floor((Date.now()-last)/1000);document.getElementById('timer').innerText=s<60?`Live • Updated ${{s}}s ago`:`Live • ${{Math.floor(s/60)}}m ago • Auto 60s`;}},1000);
async function load(){{let r=await fetch('/api/scan');let d=await r.json();d.sort((a,b)=>b.score-a.score);
let h='<table><tr><th>RANK</th><th>PAIR</th><th>SCORE</th><th>PRICE</th><th>ACTION</th><th>ENERGY</th></tr>';
d.forEach((x,i)=>{{let c=x.score>60?'#00ff88':x.score>45?'#ffcc00':'#888';h+=`<tr><td>${{i+1}}</td><td>${{x.name}}</td><td style="color:${{c}};font-weight:bold">${{x.score}}</td><td>${{x.price}}</td><td>${{x.action}}</td><td style="color:${{x.rsi_color}}">${{x.rsi_text}}</td></tr>`;}});
h+='</table>';document.getElementById('t').innerHTML=h;last=Date.now();}}load();setInterval(load,60000);
</script></body></html>
"""
@app.get("/api/scan")
def scan():
    res=[]
    for p,n in zip(PAIRS,NAMES):
        d=calc(p)
        if d: d["name"]=n; res.append(d)
    return res
