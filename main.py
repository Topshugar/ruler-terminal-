from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import yfinance as yf, csv, os
from datetime import datetime

app = FastAPI()

PAIRS = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","NZDUSD=X","EURJPY=X","GBPJPY=X","EURGBP=X","AUDJPY=X","EURAUD=X","EURCAD=X","GBPCAD=X","GBPAUD=X","AUDCAD=X","USDCHF=X","EURCHF=X","GBPCHF=X","GC=F"]
NAMES = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","NZDUSD","EURJPY","GBPJPY","EURGBP","AUDJPY","EURAUD","EURCAD","GBPCAD","GBPAUD","AUDCAD","USDCHF","EURCHF","GBPCHF","XAUUSD"]
USDT_TRC20 = "TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4"
USDT_BEP20 = "0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5"
CSV_FILE = "signals.csv"

def rsi_label(r):
    if r >= 70: return f"{r} - TIRED", "#ff4444"
    if r >= 60: return f"{r} - Getting Tired", "#ffcc00"
    if r >= 45: return f"{r} - FRESH", "#00ff88"
    if r >= 30: return f"{r} - Weak", "#ffcc00"
    return f"{r} - OVERSOLD", "#ff4444"

def calc(pair):
    try:
        df = yf.download(pair, period="5d", interval="1h", progress=False)
        if len(df) < 60: return None
        close = df['Close'].squeeze()
        high = df['High'].squeeze()
        low = df['Low'].squeeze()
        ema50 = close.ewm(span=50).mean().iloc[-1]
        diff = close.diff()
        up = diff.where(diff>0,0).rolling(14).mean()
        down = -diff.where(diff<0,0).rolling(14).mean()
        rsi = 100 - (100/(1+up/down))
        rsi_v = round(float(rsi.iloc[-1]),1)
        atr = float((high - low).rolling(14).mean().iloc[-1])
        price = float(close.iloc[-1])
        sl_dist = atr * 1.5 if atr > 0 else price*0.005
        tp_dist = sl_dist * 1.8
        if price > ema50:
            sl = price - sl_dist
            tp = price + tp_dist
            action = "BUY NOW" if rsi_v < 70 else "BUY LIMIT"
        else:
            sl = price + sl_dist
            tp = price - tp_dist
            action = "SELL NOW" if rsi_v > 30 else "SELL LIMIT"
        trend = abs(price - ema50)/price*1000
        vol = float(close.pct_change().rolling(20).std().iloc[-1]*100)
        score = min(95, trend*2 + (50-abs(rsi_v-50))*0.6 + vol*5)
        label,color = rsi_label(rsi_v)
        return {"score": round(score,1), "price": round(price,5), "rsi_text": label, "rsi_color": color, "action": action, "sl": round(sl,5), "tp": round(tp,5), "raw_price": price}
    except:
        return None

def log_signals(top3):
    try:
        exists = os.path.exists(CSV_FILE)
        with open(CSV_FILE, 'a', newline='') as f:
            w = csv.writer(f)
            if not exists: w.writerow(["time","pair","action","price","sl","tp","score"])
            for s in top3:
                w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), s['name'], s['action'], s['price'], s['sl'], s['tp'], s['score']])
    except: pass

def get_stats():
    try:
        if not os.path.exists(CSV_FILE): return "Tracker starting..."
        with open(CSV_FILE) as f:
            rows = list(csv.reader(f))
            total = len(rows)-1
            if total <=0: return "Tracking started..."
            return f"Last {min(total,50)} signals logged | Win tracker ON"
    except: return "Tracker ON"

@app.get("/", response_class=HTMLResponse)
def home():
    stats = get_stats()
    return f"""
<html><head><title>RULER PRO</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{background:#0a0a0a;color:#00ff88;font-family:monospace;padding:10px;padding-bottom:90px;font-size:12px}}
table{{width:100%;border-collapse:collapse;margin-top:10px}}th{{color:#888;text-align:left;padding:6px;border-bottom:1px solid #333;font-size:11px}}td{{padding:6px;border-bottom:1px solid #222}}
.live{{color:#00ff88;animation:blink 1s infinite}}@keyframes blink{{50%{{opacity:.3}}}}
#popup{{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.92);display:flex;align-items:center;justify-content:center;z-index:9999}}
.box{{background:#111;border:1px solid #00ff88;padding:20px;max-width:380px;border-radius:12px}}
.btn{{background:#00ff88;color:#000;padding:10px;border:none;border-radius:8px;font-weight:bold;width:100%;margin-top:12px;cursor:pointer}}
.donate-bar{{position:fixed;bottom:0;left:0;width:100%;background:#111;border-top:1px solid #00ff88;padding:8px 12px;display:flex;justify-content:space-between;z-index:500}}
#qrModal{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.95);z-index:10000;align-items:center;justify-content:center}}
.tab{{padding:6px 10px;border:1px solid #333;border-radius:6px;cursor:pointer;color:#888}} .tab.active{{background:#00ff88;color:#000}}
.badge{{background:#111;border:1px solid #333;padding:4px 8px;border-radius:6px;color:#ffcc00;font-size:11px}}
</style></head><body>

<div id="popup"><div class="box">
<h3 style="margin:0">RULER PRO</h3>
<p style="color:#ccc;font-size:12px;line-height:1.4">🟢 FRESH = Good to trade<br>🔴 TIRED = Skip<br>SL/TP included - copy to MT5</p>
<button class="btn" onclick="localStorage.setItem('ruler_seen',Date.now());document.getElementById('popup').style.display='none'">I UNDERSTAND</button>
</div></div>

<div id="qrModal" onclick="if(event.target.id=='qrModal')this.style.display='none'"><div class="box" style="text-align:center">
<h3>Support RULER 💚</h3>
<div style="display:flex;gap:8px;justify-content:center;margin:10px 0">
<div id="tabTRC" class="tab active" onclick="showChain('TRC')">TRC20</div>
<div id="tabBEP" class="tab" onclick="showChain('BEP')">BEP20</div>
</div>
<div id="chainTRC"><p style="font-size:9px;color:#888;word-break:break-all">{USDT_TRC20}</p><img src="https://api.qrserver.com/v1/create-qr-code/?size=170x170&data={USDT_TRC20}" style="border:6px solid white;border-radius:8px"><br><button class="btn" onclick="navigator.clipboard.writeText('{USDT_TRC20}')">Copy TRC20</button></div>
<div id="chainBEP" style="display:none"><p style="font-size:9px;color:#888;word-break:break-all">{USDT_BEP20}</p><img src="https://api.qrserver.com/v1/create-qr-code/?size=170x170&data={USDT_BEP20}" style="border:6px solid white;border-radius:8px"><br><button class="btn" style="background:#ffcc00" onclick="navigator.clipboard.writeText('{USDT_BEP20}')">Copy BEP20</button></div>
</div></div>

<h2>RULER PRO <span class="live">● LIVE</span> <span id="timer" style="font-size:10px;color:#888"></span></h2>
<div style="display:flex;gap:8px;margin:8px 0"><span class="badge" id="stats">{stats}</span><span class="badge" style="color:#00ff88">SL/TP: ATR x1.8</span></div>
<div id="t">Scanning 19 pairs...</div>

<div class="donate-bar"><span style="font-size:10px;color:#ccc">Profit? Fuel radar ⛽</span><button style="background:#00ff88;border:none;padding:6px 12px;border-radius:6px;font-weight:bold;cursor:pointer" onclick="document.getElementById('qrModal').style.display='flex'">💚 USDT</button></div>

<script>
function showChain(c){{document.getElementById('chainTRC').style.display=c=='TRC'?'block':'none';document.getElementById('chainBEP').style.display=c=='BEP'?'block':'none';document.getElementById('tabTRC').className=c=='TRC'?'tab active':'tab';document.getElementById('tabBEP').className=c=='BEP'?'tab active':'tab';}}
if(localStorage.getItem('ruler_seen') && Date.now()-localStorage.getItem('ruler_seen')<86400000){{document.getElementById('popup').style.display='none';}}
let last=Date.now();setInterval(()=>{{let s=Math.floor((Date.now()-last)/1000);document.getElementById('timer').innerText=`Live • ${{s}}s ago`;}},1000);
async function load(){{let r=await fetch('/api/scan');let d=await r.json();d.sort((a,b)=>b.score-a.score);
let h='<table><tr><th>#</th><th>PAIR</th><th>SCORE</th><th>ACTION</th><th>PRICE</th><th>SL</th><th>TP</th><th>ENERGY</th></tr>';
d.forEach((x,i)=>{{let c=x.score>60?'#00ff88':x.score>45?'#ffcc00':'#888';h+=`<tr><td>${{i+1}}</td><td>${{x.name}}</td><td style="color:${{c}};font-weight:bold">${{x.score}}</td><td>${{x.action}}</td><td>${{x.price}}</td><td style="color:#ff4444">${{x.sl}}</td><td style="color:#00ff88">${{x.tp}}</td><td style="color:${{x.rsi_color}}">${{x.rsi_text}}</td></tr>`;}});
h+='</table>';document.getElementById('t').innerHTML=h;last=Date.now();}}load();setInterval(load,60000);
</script></body></html>
"""

@app.get("/api/scan")
def scan():
    res=[]
    for p,n in zip(PAIRS,NAMES):
        d=calc(p)
        if d: 
            d["name"]=n
            res.append(d)
    # Log TOP 3 automatically - no POST needed
    if len(res)>=3:
        res_sorted = sorted(res, key=lambda x: x['score'], reverse=True)[:3]
        log_signals(res_sorted)
    return res
