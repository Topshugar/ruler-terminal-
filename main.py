from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import yfinance as yf, csv, os, requests
from datetime import datetime, timedelta

app = FastAPI()

PAIRS = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","NZDUSD=X","EURJPY=X","GBPJPY=X","EURGBP=X","AUDJPY=X","EURAUD=X","EURCAD=X","GBPCAD=X","GBPAUD=X","AUDCAD=X","USDCHF=X","EURCHF=X","GBPCHF=X","GC=F"]
NAMES = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","NZDUSD","EURJPY","GBPJPY","EURGBP","AUDJPY","EURAUD","EURCAD","GBPCAD","GBPAUD","AUDCAD","USDCHF","EURCHF","GBPCHF","XAUUSD"]
USDT_TRC20 = "TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4"
USDT_BEP20 = "0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5"
CSV_FILE = "signals.csv"

# --- MAP TIMEFRAME ---
TF_MAP = {
    "M15": {"interval": "15m", "period": "5d"},
    "H1": {"interval": "60m", "period": "5d"},
    "H4": {"interval": "60m", "period": "20d"}, # yf has no 4h, we simulate with 1h ema 200
    "D1": {"interval": "1d", "period": "100d"}
}

def get_news_warning():
    # Try fetch real ForexFactory calendar
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=4)
        if r.status_code==200:
            data = r.json()
            now = datetime.utcnow()
            for ev in data:
                # fields: date, time, impact, currency, title
                if ev.get("impact")!="High": continue
                # parse time - this feed gives timestamp
                ev_time_str = ev.get("date")  # often "2026-10-02T12:30:00"
                try:
                    ev_time = datetime.fromisoformat(ev_time_str.replace("Z",""))
                except: continue
                diff_min = (ev_time - now).total_seconds()/60
                if 0 <= diff_min <= 120: # next 2 hours
                    cur = ev.get("currency","USD")
                    title = ev.get("title","High Impact")
                    return f"⚠️ NEWS PAUSE - {title} ({cur}) in {int(diff_min)} mins - Don't trade {cur}"
    except:
        pass
    # Fallback: US session high risk hours
    now = datetime.utcnow()
    if now.weekday()<5 and 12 <= now.hour <= 15:
        return f"⚠️ HIGH IMPACT ZONE - US News window {now.hour}:00 UTC - Trade USD with 0.01 lot only"
    return None

def rsi_label(r):
    if r >= 70: return f"{r} - TIRED", "#ff4444"
    if r >= 60: return f"{r} - Getting Tired", "#ffcc00"
    if r >= 45: return f"{r} - FRESH", "#00ff88"
    if r >= 30: return f"{r} - Weak", "#ffcc00"
    return f"{r} - OVERSOLD", "#ff4444"

def calc(pair, tf="H1"):
    try:
        cfg = TF_MAP.get(tf, TF_MAP["H1"])
        df = yf.download(pair, period=cfg["period"], interval=cfg["interval"], progress=False)
        if len(df) < 50: return None
        close = df['Close'].squeeze()
        high = df['High'].squeeze()
        low = df['Low'].squeeze()
        # Adjust EMA for timeframe simulation
        ema_len = 50 if tf in ["M15","H1"] else 200 if tf=="H4" else 20
        ema = close.ewm(span=ema_len).mean().iloc[-1]
        diff = close.diff()
        up = diff.where(diff>0,0).rolling(14).mean()
        down = -diff.where(diff<0,0).rolling(14).mean()
        rsi = 100 - (100/(1+up/down))
        rsi_v = round(float(rsi.iloc[-1]),1)
        atr = float((high - low).rolling(14).mean().iloc[-1])
        price = float(close.iloc[-1])
        sl_dist = atr * 1.5 if atr>0 else price*0.005
        tp_dist = sl_dist * 1.8
        if price > ema:
            sl = price - sl_dist
            tp = price + tp_dist
            action = "BUY NOW" if rsi_v < 70 else "BUY LIMIT"
        else:
            sl = price + sl_dist
            tp = price - tp_dist
            action = "SELL NOW" if rsi_v > 30 else "SELL LIMIT"
        trend = abs(price - ema)/price*1000
        vol = float(close.pct_change().rolling(20).std().iloc[-1]*100)
        score = min(95, trend*2 + (50-abs(rsi_v-50))*0.6 + vol*5)
        label,color = rsi_label(rsi_v)
        return {"score": round(score,1), "price": round(price,5), "rsi_text": label, "rsi_color": color, "action": action, "sl": round(sl,5), "tp": round(tp,5)}
    except: return None

def log_signals(top3, tf):
    try:
        exists = os.path.exists(CSV_FILE)
        with open(CSV_FILE, 'a', newline='') as f:
            w = csv.writer(f)
            if not exists: w.writerow(["time","tf","pair","action","price","sl","tp","score"])
            for s in top3:
                w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), tf, s['name'], s['action'], s['price'], s['sl'], s['tp'], s['score']])
    except: pass

def get_stats():
    try:
        if not os.path.exists(CSV_FILE): return "Tracker starting..."
        with open(CSV_FILE) as f:
            rows = list(csv.reader(f))
            total = len(rows)-1
            return f"Last {min(total,50)} signals logged"
    except: return "Tracker ON"

@app.get("/", response_class=HTMLResponse)
def home():
    stats = get_stats()
    news = get_news_warning()
    news_html = f"<div style='background:#ff4444;color:#000;padding:8px;border-radius:6px;margin:8px 0;font-weight:bold;font-size:11px'>{news}</div>" if news else "<div style='background:#001a00;border:1px solid #00ff88;color:#00ff88;padding:6px;border-radius:6px;margin:8px 0;font-size:11px'>✅ No high impact news - Safe to trade</div>"
    return f"""
<html><head><title>RULER PRO MAX</title><meta name="viewport" content="width=device-width, initial-scale=1">
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
.tf{{padding:6px 12px;border:1px solid #333;border-radius:20px;cursor:pointer;color:#888;font-size:11px}} .tf.active{{background:#00ff88;color:#000;border-color:#00ff88;font-weight:bold}}
</style></head><body>

<div id="popup"><div class="box">
<h3 style="margin:0">RULER PRO MAX</h3>
<p style="color:#ccc;font-size:12px;line-height:1.4">🕐 Switch Timeframe above<br>📰 News filter protects you<br>🟢 FRESH = Trade TOP 3<br>Copy SL/TP to MT5</p>
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

<h2>RULER PRO MAX <span class="live">● LIVE</span> <span id="timer" style="font-size:10px;color:#888"></span></h2>
<div style="display:flex;gap:6px;margin:8px 0">
<span class="tf active" id="tf_M15" onclick="setTF('M15')">M15 Scalp</span>
<span class="tf" id="tf_H1" onclick="setTF('H1')">H1 Intra</span>
<span class="tf" id="tf_H4" onclick="setTF('H4')">H4 Swing</span>
<span class="tf" id="tf_D1" onclick="setTF('D1')">D1 Long</span>
</div>
{news_html}
<div style="display:flex;gap:8px;margin:8px 0"><span class="badge" id="stats">{stats}</span><span class="badge" style="color:#00ff88">SL/TP: ATR x1.8</span></div>
<div id="t">Scanning...</div>
<div class="donate-bar"><span style="font-size:10px;color:#ccc">Profit? Fuel radar ⛽</span><button style="background:#00ff88;border:none;padding:6px 12px;border-radius:6px;font-weight:bold;cursor:pointer" onclick="document.getElementById('qrModal').style.display='flex'">💚 USDT</button></div>

<script>
function showChain(c){{document.getElementById('chainTRC').style.display=c=='TRC'?'block':'none';document.getElementById('chainBEP').style.display=c=='BEP'?'block':'none';document.getElementById('tabTRC').className=c=='TRC'?'tab active':'tab';document.getElementById('tabBEP').className=c=='BEP'?'tab active':'tab';}}
if(localStorage.getItem('ruler_seen') && Date.now()-localStorage.getItem('ruler_seen')<86400000){{document.getElementById('popup').style.display='none';}}
let currentTF = localStorage.getItem('ruler_tf') || 'M15';
function setTF(tf){{currentTF=tf;localStorage.setItem('ruler_tf',tf);document.querySelectorAll('.tf').forEach(e=>e.className='tf');document.getElementById('tf_'+tf).className='tf active';load();}}
let last=Date.now();setInterval(()=>{{let s=Math.floor((Date.now()-last)/1000);document.getElementById('timer').innerText=`Live • ${{s}}s ago • TF:${{currentTF}}`;}},1000);
async function load(){{document.getElementById('t').innerHTML='Scanning '+currentTF+'...';let r=await fetch('/api/scan?tf='+currentTF);let d=await r.json();d.sort((a,b)=>b.score-a.score);
let h='<table><tr><th>#</th><th>PAIR</th><th>SCORE</th><th>ACTION</th><th>PRICE</th><th>SL</th><th>TP</th><th>ENERGY</th></tr>';
d.forEach((x,i)=>{{let c=x.score>60?'#00ff88':x.score>45?'#ffcc00':'#888';h+=`<tr><td>${{i+1}}</td><td>${{x.name}}</td><td style="color:${{c}};font-weight:bold">${{x.score}}</td><td>${{x.action}}</td><td>${{x.price}}</td><td style="color:#ff4444">${{x.sl}}</td><td style="color:#00ff88">${{x.tp}}</td><td style="color:${{x.rsi_color}}">${{x.rsi_text}}</td></tr>`;}});
h+='</table>';document.getElementById('t').innerHTML=h;last=Date.now();}}
setTF(currentTF);
setInterval(load,60000);
</script></body></html>
"""

@app.get("/api/scan")
def scan(tf: str = Query("H1")):
    res=[]
    for p,n in zip(PAIRS,NAMES):
        d=calc(p, tf)
        if d: 
            d["name"]=n
            res.append(d)
    if len(res)>=3:
        res_sorted = sorted(res, key=lambda x: x['score'], reverse=True)[:3]
        log_signals(res_sorted, tf)
    return res

@app.get("/api/news")
def news():
    return {"alert": get_news_warning()}
