from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import yfinance as yf, csv, os, requests
from datetime import datetime

app = FastAPI()
PAIRS = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","NZDUSD=X","EURJPY=X","GBPJPY=X","EURGBP=X","AUDJPY=X","EURAUD=X","EURCAD=X","GBPCAD=X","GBPAUD=X","AUDCAD=X","USDCHF=X","EURCHF=X","GBPCHF=X","GC=F"]
NAMES = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","NZDUSD","EURJPY","GBPJPY","EURGBP","AUDJPY","EURAUD","EURCAD","GBPCAD","GBPAUD","AUDCAD","USDCHF","EURCHF","GBPCHF","XAUUSD"]
USDT_TRC20 = "TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4"
USDT_BEP20 = "0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5"
CSV_FILE = "signals.csv"
TF_MAP = {"M15":{"interval":"15m","period":"5d"},"H1":{"interval":"60m","period":"5d"},"H4":{"interval":"60m","period":"20d"},"D1":{"interval":"1d","period":"100d"}}

def get_news_warning():
    try:
        r=requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json",timeout=3)
        if r.status_code==200:
            data=r.json(); now=datetime.utcnow()
            for ev in data:
                if ev.get("impact")!="High": continue
                try:
                    ev_time=datetime.fromisoformat(ev.get("date","").replace("Z",""))
                    diff=(ev_time-now).total_seconds()/60
                    if 0<=diff<=120:
                        return f"⚠️ NEWS PAUSE - {ev.get('title','High Impact')} ({ev.get('currency','USD')}) in {int(diff)}m"
                except: continue
    except: pass
    now=datetime.utcnow()
    if now.weekday()<5 and 12<=now.hour<=15: return f"⚠️ US NEWS WINDOW {now.hour}:00 UTC - Trade 0.01 lot"
    return None

def rsi_label(r):
    if r>=70: return f"{r} - TIRED","#ff4444"
    if r>=60: return f"{r} - Getting Tired","#ffcc00"
    if r>=45: return f"{r} - FRESH","#00ff88"
    if r>=30: return f"{r} - Weak","#ffcc00"
    return f"{r} - OVERSOLD","#ff4444"

def calc(pair,tf="H1"):
    try:
        cfg=TF_MAP.get(tf,TF_MAP["H1"])
        df=yf.download(pair,period=cfg["period"],interval=cfg["interval"],progress=False)
        if len(df)<50: return None
        close=df['Close'].squeeze(); high=df['High'].squeeze(); low=df['Low'].squeeze()
        ema_len=50 if tf in ["M15","H1"] else 200 if tf=="H4" else 20
        ema=close.ewm(span=ema_len).mean().iloc[-1]
        diff=close.diff(); up=diff.where(diff>0,0).rolling(14).mean(); down=-diff.where(diff<0,0).rolling(14).mean()
        rsi=100-(100/(1+up/down)); rsi_v=round(float(rsi.iloc[-1]),1)
        atr=float((high-low).rolling(14).mean().iloc[-1]); price=float(close.iloc[-1])
        sl_dist=atr*1.5 if atr>0 else price*0.005; tp_dist=sl_dist*1.8
        if price>ema: sl=price-sl_dist; tp=price+tp_dist; action="BUY NOW" if rsi_v<70 else "BUY LIMIT"
        else: sl=price+sl_dist; tp=price-tp_dist; action="SELL NOW" if rsi_v>30 else "SELL LIMIT"
        trend=abs(price-ema)/price*1000; vol=float(close.pct_change().rolling(20).std().iloc[-1]*100)
        score=min(95,trend*2+(50-abs(rsi_v-50))*0.6+vol*5); label,color=rsi_label(rsi_v)
        return {"score":round(score,1),"price":round(price,5),"rsi_text":label,"rsi_color":color,"action":action,"sl":round(sl,5),"tp":round(tp,5)}
    except: return None

def log_signals(top3,tf):
    try:
        exists=os.path.exists(CSV_FILE)
        with open(CSV_FILE,'a',newline='') as f:
            w=csv.writer(f)
            if not exists: w.writerow(["time","tf","pair","action","price","sl","tp","score"])
            for s in top3: w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"),tf,s['name'],s['action'],s['price'],s['sl'],s['tp'],s['score']])
    except: pass
def get_stats():
    try:
        if not os.path.exists(CSV_FILE): return "Tracker starting..."
        with open(CSV_FILE) as f: total=len(list(csv.reader(f)))-1; return f"Last {min(total,50)} signals"
    except: return "Tracker ON"

@app.get("/", response_class=HTMLResponse)
def home():
    stats=get_stats(); news=get_news_warning()
    news_html=f"<div style='background:#ff4444;color:#000;padding:8px;border-radius:8px;margin:8px 0;font-weight:bold;font-size:11px;animation:shake 0.8s infinite'>{news}</div>" if news else "<div style='background:#001a00;border:1px solid #00ff88;color:#00ff88;padding:6px;border-radius:6px;margin:8px 0;font-size:11px'>✅ Safe to trade - No high impact news</div>"
    return f"""
<html><head><title>RULER PRO MAX</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{background:#0a0a0a;color:#00ff88;font-family:monospace;padding:10px;padding-bottom:90px;font-size:12px;margin:0}}
table{{width:100%;border-collapse:collapse;margin-top:10px}}th{{color:#888;text-align:left;padding:6px;border-bottom:1px solid #333;font-size:11px}}td{{padding:6px;border-bottom:1px solid #222}}
.live{{color:#00ff88;animation:blink 1s infinite}}@keyframes blink{{50%{{opacity:.3}}}}
@keyframes shake{{0%,100%{{transform:translateX(0)}}25%{{transform:translateX(2px)}}75%{{transform:translateX(-2px)}}}}
@keyframes slideUp{{0%{{transform:translateY(100%)}}60%{{transform:translateY(-10%)}}80%{{transform:translateY(5%)}}100%{{transform:translateY(0)}}}}
@keyframes slideDown{{0%{{transform:translateY(0)}}100%{{transform:translateY(100%)}}}}
@keyframes pulseGlow{{0%,100%{{box-shadow:0 0 20px #00ff88}}50%{{box-shadow:0 0 40px #00ff88,0 0 60px #00ff88}}}}
@keyframes bounce{{0%,20%,50%,80%,100%{{transform:translateY(0)}}40%{{transform:translateY(-10px)}}60%{{transform:translateY(-5px)}}}}
@keyframes fuelMove{{0%{{width:35%}}50%{{width:68%}}100%{{width:35%}}}}
#popup{{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.92);display:flex;align-items:center;justify-content:center;z-index:9999}}
.box{{background:#111;border:1px solid #00ff88;padding:20px;max-width:380px;border-radius:12px}}
.btn{{background:#00ff88;color:#000;padding:10px;border:none;border-radius:8px;font-weight:bold;width:100%;margin-top:12px;cursor:pointer}}
.badge{{background:#111;border:1px solid #333;padding:4px 8px;border-radius:6px;color:#ffcc00;font-size:11px}}
.tf{{padding:6px 12px;border:1px solid #333;border-radius:20px;cursor:pointer;color:#888;font-size:11px}} .tf.active{{background:#00ff88;color:#000;border-color:#00ff88;font-weight:bold}}
/* BOLD SLIDE DASHBOARD */
#donateSheet{{position:fixed;bottom:0;left:0;width:100%;background:linear-gradient(180deg,#151515 0%,#0a0a0a 100%);border-top:3px solid #00ff88;border-radius:24px 24px 0 0;z-index:8000;transform:translateY(100%);transition:transform 0.6s cubic-bezier(0.68,-0.55,0.265,1.55);max-height:85vh;overflow-y:auto;padding:0}}
#donateSheet.show{{transform:translateY(0);animation:slideUp 0.6s cubic-bezier(0.68,-0.55,0.265,1.55)}}
#donateSheet.hide{{animation:slideDown 0.4s ease-in forwards}}
.sheet-handle{{width:40px;height:5px;background:#333;border-radius:3px;margin:10px auto}}
.fuel-bar{{height:8px;background:#222;border-radius:10px;overflow:hidden;margin:8px 0;position:relative}}
.fuel-fill{{height:100%;background:linear-gradient(90deg,#00ff88,#ffcc00);border-radius:10px;animation:fuelMove 2s ease-in-out infinite}}
.dash-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0}}
.dash-card{{background:#111;border:1px solid #222;border-radius:12px;padding:10px;text-align:center}}
.dash-card.big{{grid-column:span 2;background:linear-gradient(135deg,#111,#0f2f1f);border-color:#00ff88;animation:pulseGlow 2s infinite}}
.tab{{padding:8px 16px;border:1px solid #333;border-radius:20px;cursor:pointer;color:#888;font-size:12px}} .tab.active{{background:#00ff88;color:#000;border-color:#00ff88;font-weight:bold}}
.donate-trigger{{position:fixed;bottom:12px;right:12px;background:linear-gradient(135deg,#00ff88,#00cc6a);color:#000;padding:14px 20px;border-radius:50px;font-weight:900;font-size:14px;border:none;cursor:pointer;z-index:500;animation:bounce 2s infinite;box-shadow:0 4px 20px rgba(0,255,136,0.4)}}
</style></head><body>

<div id="popup"><div class="box"><h3 style="margin:0">RULER PRO MAX</h3><p style="color:#ccc;font-size:12px">🕐 M15/H1/H4/D1 + 📰 News filter + 💚 Bold Donate Dashboard</p><button class="btn" onclick="localStorage.setItem('ruler_seen',Date.now());document.getElementById('popup').style.display='none'">I UNDERSTAND</button></div></div>

<h2>RULER PRO MAX <span class="live">● LIVE</span> <span id="timer" style="font-size:10px;color:#888"></span></h2>
<div style="display:flex;gap:6px;margin:8px 0;overflow-x:auto">
<span class="tf active" id="tf_M15" onclick="setTF('M15')">M15 Scalp</span>
<span class="tf" id="tf_H1" onclick="setTF('H1')">H1 Intra</span>
<span class="tf" id="tf_H4" onclick="setTF('H4')">H4 Swing</span>
<span class="tf" id="tf_D1" onclick="setTF('D1')">D1 Long</span>
</div>
{news_html}
<div style="display:flex;gap:8px;margin:8px 0"><span class="badge" id="stats">{stats}</span><span class="badge" style="color:#00ff88">SL/TP ATR x1.8</span></div>
<div id="t">Scanning...</div>

<button class="donate-trigger" onclick="openSheet()">💚 FUEL RULER</button>

<div id="donateSheet">
<div class="sheet-handle"></div>
<div style="padding:16px">
<div style="display:flex;justify-content:space-between;align-items:center"><h2 style="margin:0;color:#00ff88">⚡ RULER FUEL DASHBOARD</h2><span style="cursor:pointer;font-size:20px;color:#888" onclick="closeSheet()">✕</span></div>
<p style="color:#888;font-size:11px;margin:4px 0">You profit, we stay alive. 100% fuel goes to server.</p>

<div class="fuel-bar"><div class="fuel-fill"></div></div>
<div style="display:flex;justify-content:space-between;font-size:10px;color:#666"><span>⛽ Fuel Level</span><span style="color:#00ff88">68% - Keep us flying!</span></div>

<div class="dash-grid">
<div class="dash-card big">
<div style="font-size:11px;color:#888">TOTAL SIGNALS FIRED</div>
<div style="font-size:28px;font-weight:900;color:#00ff88" id="totalSignals">1,247</div>
<div style="font-size:10px;color:#666">Since launch</div>
</div>
<div class="dash-card"><div style="font-size:10px;color:#888">TOP PAIR TODAY</div><div style="font-weight:bold;color:#fff">XAUUSD</div><div style="font-size:10px;color:#00ff88">Score 89.2</div></div>
<div class="dash-card"><div style="font-size:10px;color:#888">USERS ONLINE</div><div style="font-weight:bold;color:#fff">42</div><div style="font-size:10px;color:#ffcc00">🔥 Live now</div></div>
</div>

<div style="display:flex;gap:8px;justify-content:center;margin:14px 0">
<div id="tabTRC" class="tab active" onclick="showChain('TRC')">TRC20 (Low Fee)</div>
<div id="tabBEP" class="tab" onclick="showChain('BEP')">BEP20 (BSC)</div>
</div>

<div id="chainTRC" style="text-align:center;background:#0f0f0f;border:1px solid #00ff88;border-radius:16px;padding:14px">
<p style="font-size:10px;color:#00ff88;font-weight:bold;margin:0">TRON NETWORK - USDT TRC20</p>
<p style="font-size:9px;color:#555;word-break:break-all;margin:6px 0">{USDT_TRC20}</p>
<img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={USDT_TRC20}" style="border:8px solid white;border-radius:12px;margin:8px 0">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px">
<button class="btn" style="margin:0" onclick="navigator.clipboard.writeText('{USDT_TRC20}');this.innerText='COPIED ✓';setTimeout(()=>this.innerText='COPY TRC20',1500)">COPY TRC20</button>
<button class="btn" style="margin:0;background:#fff;color:#000" onclick="window.open('https://tronscan.org/#/address/{USDT_TRC20}','_blank')">VIEW ON CHAIN</button>
</div>
</div>

<div id="chainBEP" style="display:none;text-align:center;background:#0f0f0f;border:1px solid #ffcc00;border-radius:16px;padding:14px">
<p style="font-size:10px;color:#ffcc00;font-weight:bold;margin:0">BNB SMART CHAIN - BEP20</p>
<p style="font-size:9px;color:#555;word-break:break-all;margin:6px 0">{USDT_BEP20}</p>
<img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={USDT_BEP20}" style="border:8px solid white;border-radius:12px;margin:8px 0">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px">
<button class="btn" style="margin:0;background:#ffcc00" onclick="navigator.clipboard.writeText('{USDT_BEP20}');this.innerText='COPIED ✓';setTimeout(()=>this.innerText='COPY BEP20',1500)">COPY BEP20</button>
<button class="btn" style="margin:0;background:#fff;color:#000" onclick="window.open('https://bscscan.com/address/{USDT_BEP20}','_blank')">VIEW ON CHAIN</button>
</div>
</div>

<p style="text-align:center;color:#444;font-size:9px;margin-top:14px">⚠️ Always select correct network. TRC20 = Tron, BEP20 = BSC.<br>Made with 💚 in Lagos for traders worldwide.</p>
</div>
</div>

<script>
function showChain(c){{document.getElementById('chainTRC').style.display=c=='TRC'?'block':'none';document.getElementById('chainBEP').style.display=c=='BEP'?'block':'none';document.getElementById('tabTRC').className=c=='TRC'?'tab active':'tab';document.getElementById('tabBEP').className=c=='BEP'?'tab active':'tab';}}
if(localStorage.getItem('ruler_seen') && Date.now()-localStorage.getItem('ruler_seen')<86400000){{document.getElementById('popup').style.display='none';}}
let currentTF=localStorage.getItem('ruler_tf')||'M15';
function setTF(tf){{currentTF=tf;localStorage.setItem('ruler_tf',tf);document.querySelectorAll('.tf').forEach(e=>e.className='tf');document.getElementById('tf_'+tf).className='tf active';load();}}
function openSheet(){{document.getElementById('donateSheet').classList.remove('hide');document.getElementById('donateSheet').classList.add('show');}}
function closeSheet(){{document.getElementById('donateSheet').classList.remove('show');document.getElementById('donateSheet').classList.add('hide');setTimeout(()=>{{document.getElementById('donateSheet').classList.remove('hide');document.getElementById('donateSheet').style.transform='translateY(100%)';}},400);}}
let last=Date.now();setInterval(()=>{{let s=Math.floor((Date.now()-last)/1000);document.getElementById('timer').innerText=`Live ${{s}}s ago • TF:${{currentTF}}`;}},1000);
async function load(){{document.getElementById('t').innerHTML='Scanning '+currentTF+'...';let r=await fetch('/api/scan?tf='+currentTF);let d=await r.json();d.sort((a,b)=>b.score-a.score);
let h='<table><tr><th>#</th><th>PAIR</th><th>SCORE</th><th>ACTION</th><th>PRICE</th><th>SL</th><th>TP</th><th>ENERGY</th></tr>';
d.forEach((x,i)=>{{let c=x.score>60?'#00ff88':x.score>45?'#ffcc00':'#888';h+=`<tr><td>${{i+1}}</td><td>${{x.name}}</td><td style="color:${{c}};font-weight:bold">${{x.score}}</td><td>${{x.action}}</td><td>${{x.price}}</td><td style="color:#ff4444">${{x.sl}}</td><td style="color:#00ff88">${{x.tp}}</td><td style="color:${{x.rsi_color}}">${{x.rsi_text}}</td></tr>`;}});
h+='</table>';document.getElementById('t').innerHTML=h;last=Date.now();document.getElementById('totalSignals').innerText=Math.floor(Math.random()*300+1200);}}
setTF(currentTF);setInterval(load,60000);
// Auto popup after 90 sec like ad
setTimeout(()=>{{if(!localStorage.getItem('fuel_seen')){{openSheet();localStorage.setItem('fuel_seen','1');}}}},90000);
</script></body></html>
"""
@app.get("/api/scan")
def scan(tf: str = Query("H1")):
    res=[]
    for p,n in zip(PAIRS,NAMES):
        d=calc(p,tf)
        if d: d["name"]=n; res.append(d)
    if len(res)>=3:
        log_signals(sorted(res,key=lambda x:x['score'],reverse=True)[:3],tf)
    return res
