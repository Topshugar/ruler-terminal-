from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests, os
from datetime import datetime
from collections import deque

app = FastAPI()
TWELVE_KEY = os.getenv("TWELVE_KEY", "680fed911532416a84b624c94fd78549")
BINANCE_MAP = {"BTCUSD":"BTCUSDT","ETHUSD":"ETHUSDT","SOLUSD":"SOLUSDT","XRPUSD":"XRPUSDT","BNBUSD":"BNBUSDT","ADAUSD":"ADAUSDT","DOGEUSD":"DOGEUSDT","AVAXUSD":"AVAXUSDT"}
GROUPS = {
    "CRYPTO": [["BTC-USD","BTCUSD"],["ETH-USD","ETHUSD"],["SOL-USD","SOLUSD"],["XRP-USD","XRPUSD"],["BNB-USD","BNBUSD"],["ADA-USD","ADAUSD"],["DOGE-USD","DOGEUSD"],["AVAX-USD","AVAXUSD"]],
    "FOREX": [["EURUSD=X","EURUSD"],["GBPUSD=X","GBPUSD"],["AUDUSD=X","AUDUSD"],["USDCAD=X","USDCAD"]],
    "COMMODITIES": [["GC=F","XAUUSD"],["SI=F","XAGUSD"],["CL=F","USOIL"],["BZ=F","UKOIL"]],
    "BONDS": [["^TNX","US10Y"],["^GDAXI","GER40"],["^GSPC","US500"]]
}
ALL = [(t,n,g) for g,arr in GROUPS.items() for t,n in arr]
LIVE = {"ts":0,"prices":{},"history":{}}
SYMBOL_MAP_TWELVE = {"EURUSD":"EUR/USD","GBPUSD":"GBP/USD","AUDUSD":"AUD/USD","USDCAD":"USD/CAD","XAUUSD":"XAU/USD","XAGUSD":"XAG/USD","USOIL":"WTI/USD","UKOIL":"BRENT/USD","US10Y":"US10Y/USD","GER40":"DAX","US500":"SPX"}
for _,name,_ in ALL:
    LIVE["history"][name]=deque(maxlen=300)
    LIVE["prices"][name]=0.0

class MT5Tick(BaseModel):
    symbol: str
    bid: float
    ask: float
    time: str = ""

@app.post("/api/mt5/prices")
def mt5_push(ticks: list[MT5Tick]):
    now=datetime.utcnow().timestamp()
    c=0
    for t in ticks:
        raw=t.symbol.upper().replace(".","")
        name=raw
        for clean in ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD","EURUSD","GBPUSD","AUDUSD","USDCAD","XAUUSD","XAGUSD","USOIL","UKOIL","US10Y","GER40","US500"]:
            if clean in raw: name=clean; break
        price=(t.bid+t.ask)/2 if t.bid>0 and t.ask>0 else (t.bid or t.ask)
        if price>0:
            LIVE["prices"][name]=float(price)
            LIVE["history"][name].append(float(price))
            c+=1
    LIVE["ts"]=now
    return {"ok":True,"count":c}

@app.get("/api/mt5/status")
def mt5_status():
    age=datetime.utcnow().timestamp()-LIVE["ts"] if LIVE["ts"] else 9999
    return {"age_sec":age,"connected":age<30,"prices":LIVE["prices"]}

def ema_calc(c,p=21):
    if not c: return 0
    if len(c)<p: return sum(c)/len(c)
    k=2/(p+1); e=sum(c[:p])/p
    for v in c[p:]: e=v*k+e*(1-k)
    return e
def sma_calc(c,p=200):
    if not c: return 0
    return sum(c[-p:])/p if len(c)>=p else sum(c)/len(c)
def rsi_calc(c,p=21):
    if len(c)<p+1: return 50
    g=l=0
    for i in range(-p,0):
        d=c[i]-c[i-1]
        if d>0: g+=d
        else: l+=-d
    if l==0: return 65
    return 100-(100/(1+g/l))
def bb_calc(c,p=21,dev=2.0):
    if len(c)<p: return (c[-1]*1.01,c[-1],c[-1]*0.99)
    import math
    ma=sum(c[-p:])/p
    var=sum((x-ma)**2 for x in c[-p:])/p
    return (ma+dev*math.sqrt(var),ma,ma-dev*math.sqrt(var))

def get_real_history(symbol, tf):
    # ALWAYS try Binance/Twelve first (REAL)
    if symbol in BINANCE_MAP:
        try:
            iv={"M15":"15m","M30":"30m","H1":"1h","H4":"4h","D1":"1d"}[tf]
            k=requests.get(f"https://api.binance.com/api/v3/klines?symbol={BINANCE_MAP[symbol]}&interval={iv}&limit=200", timeout=5).json()
            if isinstance(k,list) and len(k)>30:
                closes=[float(x[4]) for x in k]
                LIVE["prices"][symbol]=closes[-1]
                LIVE["history"][symbol].append(closes[-1])
                return closes
        except: pass
    if symbol in SYMBOL_MAP_TWELVE:
        try:
            iv={"M15":"15min","M30":"30min","H1":"1h","H4":"4h","D1":"1day"}[tf]
            r=requests.get(f"https://api.twelvedata.com/time_series?symbol={SYMBOL_MAP_TWELVE[symbol]}&interval={iv}&outputsize=200&apikey={TWELVE_KEY}", timeout=6).json()
            if "values" in r and len(r["values"])>30:
                closes=[float(x["close"]) for x in r["values"][::-1]]
                LIVE["prices"][symbol]=closes[-1]
                LIVE["history"][symbol].append(closes[-1])
                return closes
        except: pass
    # If MT5 is LIVE, use it
    hist=list(LIVE["history"].get(symbol,[]))
    if len(hist)>=20:
        return hist
    pr=LIVE["prices"].get(symbol,0)
    if pr>0: return [pr]*60
    return []

class M:
    def __init__(self): self.c=[]
    async def connect(self,w): await w.accept(); self.c.append(w)
    def disc(self,w):
        if w in self.c: self.c.remove(w)
    async def broad(self,m):
        for x in self.c[:]:
            try: await x.send_json(m)
            except: self.disc(x)
manager=M()

def get_htf_ltf(tf):
    if tf in ("M15","M30"): return ("H1","DAY")
    if tf=="H1": return ("H4","DAY")
    if tf=="H4": return ("D1","SWING")
    return ("D1","SWING")

def calc_mtf_ruler(symbol, tf, group):
    try:
        htf,mode=get_htf_ltf(tf)
        closes_ltf=get_real_history(symbol, tf)
        closes_htf=get_real_history(symbol, htf)
        if len(closes_ltf)<20:
            pr=LIVE["prices"].get(symbol,0)
            if pr==0: return None
            closes_ltf=[pr]*60; closes_htf=[pr]*60
        price_ltf=closes_ltf[-1]; price_htf=closes_htf[-1]
        ema21_htf=ema_calc(closes_htf,21); sma200_htf=sma_calc(closes_htf,200); rsi21_htf=rsi_calc(closes_htf,21)
        ema21_ltf=ema_calc(closes_ltf,21); rsi21_ltf=rsi_calc(closes_ltf,21)
        bb_up,bb_mid,bb_low=bb_calc(closes_ltf,21,2.0)
        bb_range=bb_up-bb_low; bb_pos=(price_ltf-bb_low)/bb_range if bb_range!=0 else 0.5
        dist_ema=abs(price_ltf-ema21_ltf)/price_ltf*100 if price_ltf!=0 else 10
        htf_score=0
        if price_htf>sma200_htf and ema21_htf>sma200_htf: htf_score+=7
        elif price_htf<sma200_htf and ema21_htf<sma200_htf: htf_score+=2
        else: htf_score+=4
        htf_score+=3 if rsi21_htf>50 else 1
        ltf_score=5
        if group=="CRYPTO":
            if 55<=rsi21_ltf<70 and dist_ema<1.5: ltf_score=8.5
            elif 45<=rsi21_ltf<=55 and 0.35<=bb_pos<=0.65: ltf_score=7.5
            elif rsi21_ltf<40: ltf_score=3
        elif group=="BONDS":
            if 40<=rsi21_ltf<=48 and bb_pos<=0.45: ltf_score=9.0
            elif 45<=rsi21_ltf<55: ltf_score=8.0
            else: ltf_score=4.5
        else:
            if 45<=rsi21_ltf<=50 and dist_ema<1.0: ltf_score=8.5
            elif 40<=rsi21_ltf<45 and bb_pos<=0.4: ltf_score=8.0
            elif 50<rsi21_ltf<60 and 0.4<=bb_pos<=0.7: ltf_score=7.0
        ltf_score=min(10,ltf_score); htf_score=min(10,htf_score)
        final=htf_score*0.6+ltf_score*0.4
        if htf_score<5: final=min(final,4.9)
        action="ENTRY" if htf_score>=6 and ltf_score>=7 else "WAIT" if htf_score>=6 and ltf_score>=5 else "NO TRADE"
        return {"price":round(price_ltf,4 if price_ltf<10 else 2),"action":action,"score":round(final*10,1),"htf_score":round(htf_score,1),"ltf_score":round(ltf_score,1),"name":symbol,"mode":mode,"htf":htf,"rsi_ltf":round(rsi21_ltf),"rsi_htf":round(rsi21_htf)}
    except: return None

def build_signals(tf):
    out=[]
    for _,sym,grp in ALL:
        d=calc_mtf_ruler(sym,tf,grp)
        if d: out.append(d)
    return sorted(out, key=lambda x:x["score"], reverse=True)

@app.get("/api/signals")
def api_signals(tf: str="M30"):
    age=datetime.utcnow().timestamp()-LIVE["ts"] if LIVE["ts"] else 9999
    return {"signals": build_signals(tf), "mt5_connected": age<30}

@app.get("/", response_class=HTMLResponse)
def home():
    html = """<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RULER v2.3</title><style>
*{box-sizing:border-box}html,body{margin:0;background:#020202;color:#8aff6a;font-family:monospace;height:100dvh;overflow:hidden}
.phone{width:100%;max-width:460px;margin:0 auto;height:100dvh;background:#050805;display:flex;flex-direction:column;border:1px solid #1a2a1a}
.header{display:flex;justify-content:space-between;padding:14px 12px;background:#0a0f0a;border-bottom:2px solid #8aff6a33}
.search{margin:8px 10px;background:#0a0f0a;border:1px solid #1a3a1a;border-radius:10px;padding:10px 12px;display:flex;gap:8px;color:#5a7a5a;font-size:12px}.search input{background:transparent;border:none;outline:none;color:#8aff6a;font-family:monospace;font-size:12px;width:100%}
.tf-bar{display:flex;gap:6px;padding:0 10px 8px;overflow:auto}.tf-btn{padding:6px 14px;border-radius:20px;font-size:11px;font-weight:900;border:1px solid #1a3a1a;color:#5a7a5a;background:#0a0f0a;cursor:pointer;white-space:nowrap}.tf-btn.active{background:#8aff6a;color:#000;border-color:#8aff6a}
.folder{margin:8px 10px;border:1px solid #1a3a1a;border-radius:12px;overflow:hidden;background:#080f08}.folder-head{display:flex;justify-content:space-between;padding:12px 12px;background:#0f1a0f;font-weight:900;font-size:13px}.folder-count{background:#1a2a3a;border-radius:12px;padding:2px 8px;font-size:11px;color:#8aff6a;border:1px solid #2a3a4a}
.table-head{display:flex;padding:8px 10px;font-size:8px;color:#5a7a5a;border-bottom:1px solid #111;background:#050805}.row{display:flex;padding:10px 10px;font-size:10px;border-bottom:1px solid #111;align-items:center}.col-pair{width:22%}.col-price{width:18%}.col-htf{width:16%}.col-ltf{width:16%}.col-score{width:12%;text-align:center}.col-action{width:16%;text-align:right;font-weight:900;font-size:9px}
.green{color:#8aff6a}.yellow{color:#ffeb3b}.red{color:#ff4444}.content{flex:1;overflow:auto;padding-bottom:80px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}.dot.green{background:#8aff6a}.dot.yellow{background:#ffeb3b}.dot.red{background:#ff4444}
</style></head><body><div class="phone">
<div class="header"><div style="font-weight:900">RULER v2.3 <span id="clock" style="color:#5a7a5a;font-size:11px">--:--:--</span></div><div style="font-size:9px;color:#5a7a5a" id="status"><span id="dot" class="dot red"></span><span id="statTxt">LOADING</span></div></div>
<div class="search">🔍 <input id="searchBox" placeholder="Search BTC, EUR, XAU, SPX..." oninput="render()" /></div>
<div class="tf-bar"><div class="tf-btn" id="tf-M15" onclick="setTF('M15')">M15</div><div class="tf-btn active" id="tf-M30" onclick="setTF('M30')">M30</div><div class="tf-btn" id="tf-H1" onclick="setTF('H1')">H1</div><div class="tf-btn" id="tf-H4" onclick="setTF('H4')">H4</div><div class="tf-btn" id="tf-D1" onclick="setTF('D1')">D1</div></div>
<div class="content" id="content">Fetching REAL prices...</div>
</div>
<script>
let all=[]; let curTF='M30'; let ws=null;
function setTF(tf){curTF=tf; document.querySelectorAll('.tf-btn').forEach(b=>b.classList.remove('active')); document.getElementById('tf-'+tf).classList.add('active'); document.getElementById('content').innerHTML='Fetching REAL prices...'; if(ws)ws.close(); fetchPoll(); conn();}
function render(){
  let q = (document.getElementById('searchBox').value||'').toUpperCase().trim();
  let groups={}; groups["CRYPTO"]=all.filter(s=>["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"].includes(s.name));
  groups["FOREX"]=all.filter(s=>["EURUSD","GBPUSD","AUDUSD","USDCAD"].includes(s.name));
  groups["COMMODITIES"]=all.filter(s=>["XAUUSD","XAGUSD","USOIL","UKOIL"].includes(s.name));
  groups["BONDS"]=all.filter(s=>["US10Y","GER40","US500"].includes(s.name));
  if(q){ Object.keys(groups).forEach(g=>{ groups[g]=groups[g].filter(s=>s.name.includes(q)); }); }
  let html='';
  Object.keys(groups).forEach(g=>{
    let arr=groups[g]; arr.sort((a,b)=>b.score-a.score); if(arr.length==0) return;
    html+=`<div class="folder"><div class="folder-head"><span>📁 ${g}</span><span class="folder-count">${arr.length}</span></div>`;
    html+=`<div class="table-head"><span class="col-pair">PAIR</span><span class="col-price">PRICE</span><span class="col-htf">HTF</span><span class="col-ltf">LTF</span><span class="col-score">SCR</span><span class="col-action">ACT</span></div>`;
    arr.forEach(x=>{
      let col = x.score>=70? 'green' : x.score>=50? 'yellow' : 'red';
      let actCol = x.action.includes('ENTRY')? 'green' : x.action.includes('WAIT')? 'yellow' : 'red';
      html+=`<div class="row"><span class="col-pair">○ ${x.name}</span><span class="col-price" style="color:#fff">${x.price}</span><span class="col-htf">${x.htf}:${x.htf_score}</span><span class="col-ltf">${curTF}:${x.ltf_score}</span><span class="col-score ${col}">${(x.score/10).toFixed(1)}</span><span class="col-action ${actCol}">${x.action}</span></div>`;
    }); html+=`</div>`;
  });
  document.getElementById('content').innerHTML=html || '<div style="padding:20px;color:#ffeb3b">No data yet. Render is waking up, wait 20s...</div>';
}
async function fetchPoll(){
  try{
    let r=await fetch('/api/signals?tf='+curTF); let d=await r.json();
    if(d.signals && d.signals.length>0){
      all=d.signals;
      let dot=document.getElementById('dot'); let txt=document.getElementById('statTxt');
      if(d.mt5_connected){ dot.className='dot green'; txt.innerText='MT5 LIVE'; txt.style.color='#8aff6a'; }
      else { dot.className='dot yellow'; txt.innerText='BINANCE+12 REAL'; txt.style.color='#ffeb3b'; }
      render();
    }
  }catch(e){ console.log(e); }
}
function conn(){
  try{
    let p=location.protocol==='https:'?'wss:':'ws:'; ws=new WebSocket(p+'//'+location.host+'/ws?tf='+curTF);
    ws.onmessage=e=>{let d=JSON.parse(e.data); if(d.signals && d.signals.length>0){ all=d.signals; render(); }};
    ws.onclose=()=>setTimeout(conn,3000);
  }catch(e){}
}
setInterval(()=>{document.getElementById('clock').innerText=new Date().toLocaleTimeString();},1000);
setInterval(fetchPoll,5000);
fetchPoll(); conn();
</script></body></html>"""
    return HTMLResponse(html)

@app.websocket("/ws")
async def ws_ep(websocket: WebSocket, tf: str="M30"):
    await manager.connect(websocket)
    try:
        while True:
            out=build_signals(tf)
            if out: await manager.broad({"signals":out})
            await asyncio.sleep(5)
    except Exception as e:
        print(e); manager.disc(websocket)
