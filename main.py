from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests, os
from datetime import datetime, timezone
from collections import deque
from zoneinfo import ZoneInfo

app = FastAPI()

# --- PROFESSIONAL FOLDERS ---
GROUPS = {
    "METALS": ["XAUUSD","XAGUSD"],
    "CRYPTO": ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],
    "FOREX": ["EURUSD","GBPUSD","AUDUSD","USDCAD"],
    "ENERGY": ["USOIL","UKOIL"],
    "INDICES": ["US500","GER40","US10Y"]
}
ALL_SYMBOLS = [s for arr in GROUPS.values() for s in arr]

LIVE = {"ts":0, "prices":{}, "history":{}}
for s in ALL_SYMBOLS:
    LIVE["history"][s]=deque([0.0]*100, maxlen=200)
    LIVE["prices"][s]=0.0

BINANCE_MAP = {"BTCUSD":"BTCUSDT","ETHUSD":"ETHUSDT","SOLUSD":"SOLUSDT","XRPUSD":"XRPUSDT","BNBUSD":"BNBUSDT","ADAUSD":"ADAUSDT","DOGEUSD":"DOGEUSDT","AVAXUSD":"AVAXUSDT"}

class MT5Tick(BaseModel):
    symbol: str
    bid: float
    ask: float

@app.post("/api/mt5/prices")
def mt5_push(ticks: list[MT5Tick]):
    now=datetime.now(timezone.utc).timestamp()
    for t in ticks:
        raw=t.symbol.upper()
        name=raw
        for c in ALL_SYMBOLS:
            if c in raw: name=c; break
        price=(t.bid+t.ask)/2 if t.bid>0 and t.ask>0 else (t.bid or t.ask)
        if price>0:
            LIVE["prices"][name]=float(price)
            LIVE["history"][name].append(float(price))
    LIVE["ts"]=now
    return {"ok":True}

@app.get("/api/mt5/status")
def mt5_status():
    age=datetime.now(timezone.utc).timestamp()-LIVE["ts"] if LIVE["ts"] else 9999
    return {"age":age,"connected":age<30,"uk_time": datetime.now(ZoneInfo("Europe/London")).strftime("%H:%M:%S")}

def fetch_crypto_only():
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price", timeout=4)
        if r.status_code==200:
            for it in r.json():
                for our,bsym in BINANCE_MAP.items():
                    if it["symbol"]==bsym:
                        p=float(it["price"])
                        LIVE["prices"][our]=p
                        LIVE["history"][our].append(p)
    except: pass

def ema(c,p=21):
    vals=[x for x in c if x>0]
    if len(vals)<p: return sum(vals)/len(vals) if vals else 0
    k=2/(p+1); e=sum(vals[:p])/p
    for v in vals[p:]: e=v*k+e*(1-k)
    return e

def build_signals_fast(tf):
    fetch_crypto_only()
    out=[]
    for sym in ALL_SYMBOLS:
        hist=[x for x in list(LIVE["history"][sym]) if x>0]
        price=LIVE["prices"].get(sym,0)
        if price==0 and hist: price=hist[-1]
        if price==0:
            out.append({"name":sym,"price":"CLOSED","score":0,"htf_score":0,"ltf_score":0,"action":"OFF","htf":"--"})
            continue
        e=ema(hist or [price],21)
        htf=7 if price>e else 3 if e!=0 else 5
        ltf=6
        final=htf*0.6+ltf*0.4
        action="ENTRY" if final>=6.5 else "WAIT" if final>=5.5 else "NO TRADE"
        out.append({
            "name":sym,
            "price":round(price,4 if price<10 else 2),
            "score":round(final*10,1),
            "htf_score":round(htf,1),
            "ltf_score":round(ltf,1),
            "action":action,
            "htf":"H1" if tf in ("M15","M30") else "D1",
        })
    return sorted(out, key=lambda x: x["score"], reverse=True)

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

@app.get("/api/signals")
def api_signals(tf: str="M30"):
    age=datetime.now(timezone.utc).timestamp()-LIVE["ts"] if LIVE["ts"] else 9999
    uk_now = datetime.now(ZoneInfo("Europe/London")).strftime("%H:%M:%S")
    return {"signals": build_signals_fast(tf), "mt5_connected": age<30, "uk_time": uk_now, "mt5_age": int(age)}

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse("""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RULER PRO v2.3 UK</title><style>
*{box-sizing:border-box}html,body{margin:0;background:#020202;color:#d0d0d0;font-family:monospace;height:100dvh;overflow:hidden}
.phone{width:100%;max-width:480px;margin:0 auto;height:100dvh;background:#080a08;display:flex;flex-direction:column;border:1px solid #1e2e1e}
.header{display:flex;justify-content:space-between;align-items:center;padding:14px;background:#0e1210;border-bottom:1px solid #2a3a2a}.header b{color:#8aff6a}
.tf-bar{display:flex;gap:6px;padding:10px 12px;background:#0a0e0a;border-bottom:1px solid #1a2a1a}.tf-btn{padding:6px 16px;border-radius:6px;font-size:11px;font-weight:900;border:1px solid #2a3a2a;color:#6a7a6a;background:#121712;cursor:pointer}.tf-btn.active{background:#8aff6a;color:#000}
.content{flex:1;overflow:auto;padding:10px 10px 80px;background:#050805}
.folder{margin-bottom:14px;border:1px solid #1e2e1e;border-radius:10px;overflow:hidden;background:#0a100a}
.folder-head{display:flex;justify-content:space-between;padding:10px 12px;background:#121a12;font-weight:900;font-size:11px}.folder-head span:first-child{color:#8aff6a}
.count{font-size:10px;background:#1a2a1a;padding:2px 8px;border-radius:10px;color:#8aff6a;border:1px solid #2a3a2a}
.table-head{display:flex;padding:8px 12px;font-size:8px;color:#5a6a5a;background:#080c08;border-bottom:1px solid #1a2a1a}
.row{display:flex;padding:11px 12px;font-size:11px;border-bottom:1px solid #101a10;align-items:center;background:#0a100a}
.col-pair{width:26%;font-weight:900;color:#fff}.col-price{width:24%;color:#fff}.col-htf{width:12%}.col-ltf{width:12%}.col-score{width:10%;text-align:center;font-weight:900}.col-action{width:16%;text-align:right;font-weight:900;font-size:9px}
.green{color:#8aff6a}.yellow{color:#ffeb3b}.red{color:#ff5555}.grey{color:#666}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:5px}.dot.green{background:#8aff6a;box-shadow:0 0 6px #8aff6a}.dot.yellow{background:#ffeb3b}.dot.red{background:#555}
.search{margin:10px;background:#0e1510;border:1px solid #1e2e1e;border-radius:8px;padding:9px 12px;display:flex;gap:8px;color:#5a7a5a;font-size:11px}.search input{background:transparent;border:none;outline:none;color:#fff;font-family:monospace;font-size:11px;width:100%}
</style></head><body><div class="phone">
<div class="header"><b>RULER PRO v2.3 UK</b><div style="font-size:9px" id="status"><span id="dot" class="dot yellow"></span><span id="statTxt">CHECKING</span> <span id="clock" style="color:#8aff6a;margin-left:6px;font-weight:900">--:-- UK</span></div></div>
<div class="search">🔍 <input id="searchBox" placeholder="Search BTC, GOLD, EURUSD..." oninput="render()" /></div>
<div class="tf-bar"><div class="tf-btn" id="tf-M15" onclick="setTF('M15')">M15</div><div class="tf-btn active" id="tf-M30" onclick="setTF('M30')">M30</div><div class="tf-btn" id="tf-H1" onclick="setTF('H1')">H1</div><div class="tf-btn" id="tf-H4" onclick="setTF('H4')">H4</div><div class="tf-btn" id="tf-D1" onclick="setTF('D1')">D1</div></div>
<div class="content" id="content">Loading UK SESSION...</div>
</div>
<script>
let all=[]; let curTF='M30';
const MAP={"METALS":["XAUUSD","XAGUSD"],"CRYPTO":["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],"FOREX":["EURUSD","GBPUSD","AUDUSD","USDCAD"],"ENERGY":["USOIL","UKOIL"],"INDICES":["US500","GER40","US10Y"]};
const ICONS={"METALS":"🥇","CRYPTO":"₿","FOREX":"💱","ENERGY":"🛢️","INDICES":"📈"};
function setTF(tf){curTF=tf; document.querySelectorAll('.tf-btn').forEach(b=>b.classList.remove('active')); document.getElementById('tf-'+tf).classList.add('active'); fetchPoll();}
function getSessionUK(){
  let now=new Date();
  let uk = new Date(now.toLocaleString('en-US',{timeZone:'Europe/London'}));
  let h=uk.getHours(); let d=uk.getDay();
  if(d==0) return "SUNDAY - MARKET CLOSED";
  if(d==6) return "SATURDAY - MARKET CLOSED";
  if(h>=8 && h<13) return "LONDON OPEN";
  if(h>=13 && h<17) return "LONDON + NY OVERLAP";
  if(h>=17 && h<22) return "NEW YORK OPEN";
  if(h>=22 || h<1) return "SYDNEY OPEN";
  return "ASIAN / TOKYO OPEN";
}
function render(){
  let q=(document.getElementById('searchBox').value||'').toUpperCase().trim();
  let html='';
  Object.keys(MAP).forEach(g=>{
    let arr=all.filter(s=>MAP[g].includes(s.name));
    if(q) arr=arr.filter(s=>s.name.includes(q));
    if(arr.length==0 &&!q) return;
    arr.sort((a,b)=>b.score-a.score);
    html+=`<div class="folder"><div class="folder-head"><span>${ICONS[g]} ${g}</span><span class="count">${arr.length} PAIRS</span></div>`;
    html+=`<div class="table-head"><span class="col-pair">SYMBOL</span><span class="col-price">PRICE</span><span class="col-htf">HTF</span><span class="col-ltf">LTF</span><span class="col-score">SCORE</span><span class="col-action">SIGNAL</span></div>`;
    arr.forEach(x=>{
      let col=x.score>=70?'green':x.score>=50?'yellow':x.score==0?'grey':'red';
      let actCol=x.action.includes('ENTRY')?'green':x.action.includes('WAIT')?'yellow':x.action=='OFF'?'grey':'red';
      let displayName=x.name.replace('XAUUSD','GOLD').replace('XAGUSD','SILVER').replace('USOIL','WTI').replace('UKOIL','BRENT');
      let priceDisplay = x.price=='CLOSED'? '<span class=grey>CLOSED</span>' : x.price;
      html+=`<div class="row"><span class="col-pair">● ${displayName}</span><span class="col-price">${priceDisplay}</span><span class="col-htf">${x.htf_score}</span><span class="col-ltf">${x.ltf_score}</span><span class="col-score ${col}">${x.score>0?(x.score/10).toFixed(1):'--'}</span><span class="col-action ${actCol}">${x.action}</span></div>`;
    });
    html+=`</div>`;
  });
  document.getElementById('content').innerHTML=html || '<div style="padding:20px;color:#5a7a5a">No results</div>';
}
async function fetchPoll(){
  try{
    let r=await fetch('/api/signals?tf='+curTF); let d=await r.json();
    if(d.signals){ all=d.signals;
      let dot=document.getElementById('dot'); let txt=document.getElementById('statTxt');
      let session = getSessionUK();
      document.getElementById('clock').innerText = session;
      if(d.mt5_connected){dot.className='dot green'; txt.innerText='MT5 LIVE'; txt.style.color='#8aff6a';}
      else{dot.className='dot yellow'; if(session.includes('CLOSED')){txt.innerText='MARKET CLOSED';} else {txt.innerText='CRYPTO ONLY';} txt.style.color='#ffeb3b';}
      render();
    }
  }catch(e){}
}
setInterval(fetchPoll,4000);
fetchPoll();
</script></body></html>
    """)

@app.websocket("/ws")
async def ws_ep(websocket: WebSocket, tf: str="M30"):
    await manager.connect(websocket)
    try:
        while True:
            out=build_signals_fast(tf)
            await manager.broad({"signals":out})
            import asyncio; await asyncio.sleep(5)
    except: manager.disc(websocket)
