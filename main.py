from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import yfinance as yf, csv, os, requests, asyncio
from datetime import datetime

app = FastAPI()

# ===== GROUPED MARKET LIBRARY - ALPHABETICAL =====
GROUPS = {
    "COMMODITIES": [("CL=F","USOIL"), ("BZ=F","UKOIL"), ("NG=F","NATGAS")],
    "CRYPTO": [("BTC-USD","BTCUSD"), ("ETH-USD","ETHUSD"), ("BNB-USD","BNBUSD"), ("SOL-USD","SOLUSD")],
    "FOREX": [("AUDCAD=X","AUDCAD"), ("AUDJPY=X","AUDJPY"), ("AUDUSD=X","AUDUSD"), ("EURAUD=X","EURAUD"), ("EURCAD=X","EURCAD"), ("EURCHF=X","EURCHF"), ("EURGBP=X","EURGBP"), ("EURJPY=X","EURJPY"), ("EURUSD=X","EURUSD"), ("GBPAUD=X","GBPAUD"), ("GBPCAD=X","GBPCAD"), ("GBPCHF=X","GBPCHF"), ("GBPJPY=X","GBPJPY"), ("GBPUSD=X","GBPUSD"), ("NZDUSD=X","NZDUSD"), ("USDCAD=X","USDCAD"), ("USDCHF=X","USDCHF"), ("USDJPY=X","USDJPY")],
    "INDICES": [("^GSPC","US500"), ("^DJI","US30"), ("^IXIC","NAS100"), ("^GDAXI","GER40")],
    "METALS": [("GC=F","XAUUSD"), ("SI=F","XAGUSD")],
    "STOCKS": [("AAPL","AAPL"), ("TSLA","TSLA"), ("NVDA","NVDA")]
}
# Flatten for backend scan
ALL_PAIRS = [(t,n,g) for g, lst in GROUPS.items() for t,n in lst]

USDT_TRC20 = "TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4"
USDT_BEP20 = "0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5"
CSV_FILE = "signals.csv"
TF_MAP = {"M15":{"interval":"15m","period":"5d"},"H1":{"interval":"60m","period":"5d"},"H4":{"interval":"60m","period":"20d"},"D1":{"interval":"1d","period":"100d"}}
SITE_URL = "https://ruler-terminal.onrender.com"

class Manager:
    def __init__(self): self.conns=[]
    async def connect(self,w): await w.accept(); self.conns.append(w)
    def disconnect(self,w):
        if w in self.conns: self.conns.remove(w)
    async def broadcast(self,m):
        for c in self.conns:
            try: await c.send_json(m)
            except: pass
manager=Manager()

def calc(pair,tf="H1"):
    try:
        cfg=TF_MAP.get(tf,TF_MAP["H1"])
        df=yf.download(pair,period=cfg["period"],interval=cfg["interval"],progress=False)
        if len(df)<50: return None
        close=df['Close'].squeeze(); high=df['High'].squeeze(); low=df['Low'].squeeze()
        ema=close.ewm(span=50).mean().iloc[-1]
        diff=close.diff(); up=diff.where(diff>0,0).rolling(14).mean(); down=-diff.where(diff<0,0).rolling(14).mean()
        rsi=100-(100/(1+up/down)); rsi_v=round(float(rsi.iloc[-1]),1)
        atr=float((high-low).rolling(14).mean().iloc[-1]); price=float(close.iloc[-1])
        sl_dist=atr*1.5 if atr>0 else price*0.005; tp_dist=sl_dist*1.8
        if price>ema: sl=price-sl_dist; tp=price+tp_dist; action="BUY"
        else: sl=price+sl_dist; tp=price-tp_dist; action="SELL"
        trend=abs(price-ema)/price*1000; vol=float(close.pct_change().rolling(20).std().iloc[-1]*100)
        score=min(95,trend*2+(50-abs(rsi_v-50))*0.6+vol*5)
        label = f"{rsi_v} FRESH" if 45<=rsi_v<60 else f"{rsi_v} TIRED" if rsi_v>=70 else f"{rsi_v}"
        color = "#00ff88" if 45<=rsi_v<60 else "#ffcc00" if rsi_v<70 else "#ff4444"
        return {"score":round(score,1),"price":round(price,5),"rsi_text":label,"rsi_color":color,"action":action,"sl":round(sl,5),"tp":round(tp,5)}
    except: return None

@app.get("/", response_class=HTMLResponse)
def home():
    return f"""
<html><head><title>RULER TERMINAL</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{background:#070a0f;color:#e6e6e6;font-family:monospace;margin:0;padding:0;display:flex;height:100vh}}
.sidebar{{width:170px;background:#0b0f1a;border-right:1px solid #1a233a;padding:12px;overflow-y:auto}}
.group{{padding:10px 12px;margin:4px 0;border-radius:8px;cursor:pointer;color:#8892b0;border:1px solid transparent;font-size:12px;letter-spacing:0.5px}}
.group.active{{background:#0f1a2f;border-color:#c9a227;color:#c9a227;font-weight:bold}}
.group:hover{{border-color:#334}}
.main{{flex:1;overflow-y:auto;padding:14px;padding-bottom:120px;background:radial-gradient(ellipse at top,#0f1a2f 0%,#070a0f 60%)}}
.live{{color:#00ff88;animation:blink 1.2s infinite}}@keyframes blink{{50%{{opacity:.3}}}}
table{{width:100%;border-collapse:collapse;margin-top:12px}}th{{color:#5a6a8a;text-align:left;padding:8px;border-bottom:1px solid #1a233a;font-size:10px}}td{{padding:8px;border-bottom:1px solid #121a2b;font-size:12px}}
.tf{{padding:6px 12px;border:1px solid #1a233a;border-radius:20px;cursor:pointer;color:#8892b0;font-size:11px}}.tf.active{{background:#c9a227;color:#000;font-weight:bold;border-color:#c9a227}}
#intro{{position:fixed;inset:0;background:linear-gradient(180deg,#0b0f1a 0%,#070a0f 100%);z-index:9000;display:flex;align-items:center;justify-content:center;padding:20px}}
.intro-box{{max-width:520px;background:#0f1a2f;border:1px solid #c9a227;border-radius:20px;padding:24px;box-shadow:0 20px 60px rgba(0,0,0,0.6)}}
.pillar{{width:3px;height:40px;background:linear-gradient(#c9a227,#7a5e11);display:inline-block;margin:0 6px;border-radius:2px}}
#fuelAd{{position:fixed;left:-380px;bottom:20px;width:340px;background:#111a2f;border:1px solid #00ff88;border-left:4px solid #00ff88;border-radius:0 16px 16px 0;padding:14px;z-index:6000;transition:left 0.8s cubic-bezier(.68,-0.55,.27,1.55)}}
#fuelAd.show{{left:0}}
</style></head><body>

<div id="intro">
<div class="intro-box">
<div style="text-align:center"><span class="pillar"></span><span class="pillar"></span><span class="pillar"></span></div>
<h2 style="color:#c9a227;text-align:center;margin:10px 0">RULER TERMINAL</h2>
<p style="text-align:center;color:#8892b0;font-size:11px;letter-spacing:2px">CENTRAL BANK GRADE SYSTEM</p>
<p style="color:#e6e6e6;font-size:13px;line-height:1.6;margin-top:16px">
RULER scans <b>19 markets</b> every 30 seconds.<br><br>
<b>1. SCAN</b> — We check Forex, Metals, Crypto, Oil, Stocks.<br>
<b>2. RANK</b> — Best score comes first. Green FRESH = good to enter. Red TIRED = wait.<br>
<b>3. TRADE SAFE</b> — We give you BUY/SELL, Stop Loss and Take Profit so you don't blow your account.<br><br>
No big grammar. Just follow TOP 3.
</p>
<div style="display:flex;gap:10px;margin-top:14px"><div style="flex:1;background:#0b0f1a;padding:10px;border-radius:10px;text-align:center;font-size:11px">🔍 SCAN</div><div style="flex:1;background:#0b0f1a;padding:10px;border-radius:10px;text-align:center;font-size:11px">🏆 RANK</div><div style="flex:1;background:#0b0f1a;padding:10px;border-radius:10px;text-align:center;font-size:11px">🛡️ SAFE</div></div>
<button onclick="enterTerminal()" style="width:100%;margin-top:18px;background:#c9a227;color:#000;border:none;padding:14px;border-radius:12px;font-weight:900;cursor:pointer">ENTER TERMINAL →</button>
<p style="text-align:center;color:#556;font-size:10px;margin-top:10px">Built for traders in Africa, Asia, Europe — low data, fast.</p>
</div>
</div>

<div class="sidebar">
<div style="color:#c9a227;font-weight:900;font-size:12px;margin-bottom:12px;letter-spacing:1px">MARKETS</div>
<div id="groups"></div>
<div style="margin-top:20px;border-top:1px solid #1a233a;padding-top:12px">
<div style="color:#5a6a8a;font-size:10px">FUEL RULER</div>
<button onclick="openFuel()" style="margin-top:8px;width:100%;background:#00ff88;color:#000;border:none;padding:10px;border-radius:10px;font-weight:bold;cursor:pointer">💚 DONATE</button>
</div>
</div>

<div class="main">
<h2 style="margin:0">RULER PRO <span class="live">● LIVE</span> <span id="timer" style="font-size:10px;color:#5a6a8a"></span></h2>
<div style="display:flex;gap:6px;margin:12px 0;overflow-x:auto" id="tfBar">
<span class="tf" id="tf_M15" onclick="setTF('M15')">M15</span>
<span class="tf" id="tf_H1" onclick="setTF('H1')">H1</span>
<span class="tf" id="tf_H4" onclick="setTF('H4')">H4</span>
<span class="tf" id="tf_D1" onclick="setTF('D1')">D1</span>
</div>
<div id="t">Connecting live feed...</div>
</div>

<div id="fuelAd">
<div style="display:flex;justify-content:space-between;align-items:center"><b style="color:#00ff88">⚡ FUEL RULER</b><span style="cursor:pointer;color:#888" onclick="document.getElementById('fuelAd').classList.remove('show')">✕</span></div>
<p style="font-size:11px;color:#aaa;margin:6px 0">Keep server alive. 1 USDT = 1 day fuel.</p>
<div style="display:flex;gap:6px;margin-top:8px">
<a href="trust://send?coin=195&address={USDT_TRC20}" style="flex:1;background:#00ff88;color:#000;text-align:center;padding:10px;border-radius:10px;font-weight:900;text-decoration:none;font-size:11px">PAY TRC20</a>
<a href="https://link.trustwallet.com/send?coin=60&address={USDT_BEP20}" style="flex:1;background:#ffcc00;color:#000;text-align:center;padding:10px;border-radius:10px;font-weight:900;text-decoration:none;font-size:11px">PAY BEP20</a>
</div>
<p style="font-size:9px;color:#555;margin-top:6px;word-break:break-all">TRC20: {USDT_TRC20}</p>
</div>

<div id="donateSheet" style="position:fixed;bottom:0;left:0;width:100%;background:#0f1a2f;border-top:2px solid #c9a227;border-radius:20px 20px 0 0;transform:translateY(100%);transition:0.5s;z-index:8000;max-height:80vh;overflow:auto"><div style="padding:16px"><div style="display:flex;justify-content:space-between"><h3 style="margin:0;color:#c9a227">FUEL TERMINAL</h3><span onclick="document.getElementById('donateSheet').style.transform='translateY(100%)'" style="cursor:pointer">✕</span></div><div style="margin-top:12px;text-align:center;background:#070a0f;padding:12px;border-radius:12px"><p style="font-size:10px;color:#00ff88">TRC20 TRON</p><p style="font-size:8px;word-break:break-all;color:#555">{USDT_TRC20}</p><img src="https://api.qrserver.com/v1/create-qr-code/?size=160x160&data={USDT_TRC20}" style="border:6px solid white;border-radius:10px"><br><button onclick="navigator.clipboard.writeText('{USDT_TRC20}');alert('Copied TRC20')" style="margin-top:8px;background:#00ff88;border:none;padding:10px 20px;border-radius:8px;font-weight:bold">COPY TRC20</button><br><br><a href="trust://send?coin=195&address={USDT_TRC20}" style="background:#00ff88;color:#000;padding:12px 20px;border-radius:10px;text-decoration:none;font-weight:900;display:inline-block">OPEN IN TRUST WALLET</a></div><div style="margin-top:12px;text-align:center;background:#070a0f;padding:12px;border-radius:12px"><p style="font-size:10px;color:#ffcc00">BEP20 BSC</p><p style="font-size:8px;word-break:break-all;color:#555">{USDT_BEP20}</p><img src="https://api.qrserver.com/v1/create-qr-code/?size=160x160&data={USDT_BEP20}" style="border:6px solid white;border-radius:10px"><br><button onclick="navigator.clipboard.writeText('{USDT_BEP20}');alert('Copied BEP20')" style="margin-top:8px;background:#ffcc00;border:none;padding:10px 20px;border-radius:8px;font-weight:bold">COPY BEP20</button><br><br><a href="https://link.trustwallet.com/send?coin=60&address={USDT_BEP20}" style="background:#ffcc00;color:#000;padding:12px 20px;border-radius:10px;text-decoration:none;font-weight:900;display:inline-block">OPEN IN BINANCE / TRUST</a></div></div></div>

<script>
const GROUPS = {json_str(GROUPS)};
let currentGroup = localStorage.getItem('ruler_group') || 'FOREX';
let currentTF = localStorage.getItem('ruler_tf') || 'M15';
let allData = [];
let ws=null; let last=Date.now();

function json_str(o){{return JSON.stringify(o)}}
function renderGroups(){{
  let html=''; Object.keys(GROUPS).sort().forEach(g=>{{
    html+=`<div class="group ${{g===currentGroup?'active':''}}" onclick="selectGroup('${{g}}')">${{g}} <span style="float:right;color:#556">${{GROUPS[g].length}}</span></div>`;
  }});
  document.getElementById('groups').innerHTML=html;
}}
function selectGroup(g){{currentGroup=g; localStorage.setItem('ruler_group',g); renderGroups(); render();}}
function enterTerminal(){{localStorage.setItem('ruler_seen','1'); document.getElementById('intro').style.display='none';}}
if(localStorage.getItem('ruler_seen')) document.getElementById('intro').style.display='none';

function setTF(tf){{currentTF=tf; localStorage.setItem('ruler_tf',tf); document.querySelectorAll('.tf').forEach(e=>e.classList.remove('active')); document.getElementById('tf_'+tf).classList.add('active'); if(ws) ws.close(); connect();}}
function connect(){{
  let proto=location.protocol==='https:'?'wss:':'ws:';
  ws=new WebSocket(proto+'//'+location.host+'/ws?tf='+currentTF);
  ws.onmessage=(e)=>{{let d=JSON.parse(e.data); allData=d.signals; last=Date.now(); render();}};
  ws.onclose=()=>setTimeout(connect,3000);
}}
function render(){{
  let filtered = allData.filter(s=>{{
    let list = GROUPS[currentGroup]||[]; return list.some(([t,n])=>n===s.name);
  }});
  filtered.sort((a,b)=>b.score-a.score);
  let h=`<div style="color:#5a6a8a;font-size:11px;margin-top:8px">${{currentGroup}} • ${{filtered.length}} pairs • TF:${{currentTF}}</div>`;
  h+='<table><tr><th>PAIR</th><th>SCORE</th><th>ACTION</th><th>PRICE</th><th>SL</th><th>TP</th><th>ENERGY</th></tr>';
  filtered.forEach(x=>{{
    let c=x.score>60?'#00ff88':x.score>45?'#ffcc00':'#888';
    h+=`<tr><td>${{x.name}}</td><td style="color:${{c}};font-weight:bold">${{x.score}}</td><td>${{x.action}}</td><td>${{x.price}}</td><td style="color:#ff4444">${{x.sl}}</td><td style="color:#00ff88">${{x.tp}}</td><td style="color:${{x.rsi_color}}">${{x.rsi_text}}</td></tr>`;
  }});
  h+='</table>'; document.getElementById('t').innerHTML=h;
}}
function openFuel(){{document.getElementById('donateSheet').style.transform='translateY(0)';}}

// Auto slide fuel ad left->right every 30s
function showFuelAd(){{document.getElementById('fuelAd').classList.add('show'); setTimeout(()=>document.getElementById('fuelAd').classList.remove('show'),6000);}}
setTimeout(showFuelAd,4000);
setInterval(showFuelAd,30000);

setInterval(()=>{{let s=Math.floor((Date.now()-last)/1000); document.getElementById('timer').innerText=`Live ${{s}}s ago`;}},1000);
renderGroups(); document.getElementById('tf_'+currentTF).classList.add('active'); connect();
</script></body></html>
    """

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, tf: str="H1"):
    await manager.connect(websocket)
    try:
        while True:
            res=[]
            for ticker,name,group in ALL_PAIRS:
                d=calc(ticker,tf)
                if d: d["name"]=name; d["group"]=group; res.append(d)
            await manager.broadcast({"tf":tf,"signals":sorted(res,key=lambda x:x['score'],reverse=True)})
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/scan")
def scan(tf: str=Query("H1")):
    res=[]
    for ticker,name,group in ALL_PAIRS:
        d=calc(ticker,tf)
        if d: d["name"]=name; d["group"]=group; res.append(d)
    return sorted(res,key=lambda x:x['score'],reverse=True)
