from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests, os
from datetime import datetime
from collections import deque

app = FastAPI()
TWELVE_KEY = os.getenv("TWELVE_KEY", "680fed911532416a84b624c94fd78549")

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
    LIVE["history"][s]=deque([100.0]*100, maxlen=200)
    LIVE["prices"][s]=0.0

BINANCE_MAP = {"BTCUSD":"BTCUSDT","ETHUSD":"ETHUSDT","SOLUSD":"SOLUSDT","XRPUSD":"XRPUSDT","BNBUSD":"BNBUSDT","ADAUSD":"ADAUSDT","DOGEUSD":"DOGEUSDT","AVAXUSD":"AVAXUSDT"}
TWELVE_SYMS = {"EURUSD":"EUR/USD","GBPUSD":"GBP/USD","AUDUSD":"AUD/USD","USDCAD":"USD/CAD","XAUUSD":"XAU/USD","XAGUSD":"XAG/USD","USOIL":"WTI/USD","UKOIL":"BRENT/USD","US10Y":"US10Y/USD","GER40":"DAX","US500":"SPX"}

class MT5Tick(BaseModel):
    symbol: str
    bid: float
    ask: float

@app.post("/api/mt5/prices")
def mt5_push(ticks: list[MT5Tick]):
    now=datetime.utcnow().timestamp()
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
    age=datetime.utcnow().timestamp()-LIVE["ts"] if LIVE["ts"] else 9999
    return {"age":age,"connected":age<30,"prices":LIVE["prices"]}

def fetch_all_prices_once():
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price", timeout=4)
        if r.status_code==200:
            for it in r.json():
                for our,bsym in BINANCE_MAP.items():
                    if it["symbol"]==bsym:
                        try:
                            p=float(it["price"])
                            LIVE["prices"][our]=p
                            LIVE["history"][our].append(p)
                        except: pass
        syms=",".join(TWELVE_SYMS.values())
        r2=requests.get(f"https://api.twelvedata.com/price?symbol={syms}&apikey={TWELVE_KEY}", timeout=5)
        if r2.status_code==200:
            data=r2.json()
            for our,td in TWELVE_SYMS.items():
                if td in data and isinstance(data[td],dict) and "price" in data[td]:
                    try:
                        p=float(data[td]["price"])
                        LIVE["prices"][our]=p
                        LIVE["history"][our].append(p)
                    except: pass
    except Exception as e:
        print("fetch err",e)

def ema(c,p=21):
    if not c: return 0
    if len(c)<p: return sum(c)/len(c)
    k=2/(p+1); e=sum(c[:p])/p
    for v in c[p:]: e=v*k+e*(1-k)
    return e
def sma(c,p=200):
    return sum(c[-p:])/p if len(c)>=p else (sum(c)/len(c) if c else 0)
def rsi(c,p=21):
    if len(c)<p+1: return 50
    g=l=0
    for i in range(-p,0):
        d=c[i]-c[i-1]
        if d>0: g+=d
        else: l+=-d
    if l==0: return 65
    return 100-(100/(1+g/l))

def build_signals_fast(tf):
    fetch_all_prices_once()
    out=[]
    for sym in ALL_SYMBOLS:
        hist=list(LIVE["history"][sym])
        if len(hist)<10: hist=[100]*100
        price=hist[-1] if hist[-1]>0 else LIVE["prices"].get(sym,100)
        if price==0: price=100
        r=rsi(hist,21)
        e=ema(hist,21)
        s=sma(hist,50)
        htf=7 if price>s else 3
        ltf=8 if 45<=r<=60 else 5
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
    return sorted(out, key=lambda x:x["score"], reverse=True)

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
    age=datetime.utcnow().timestamp()-LIVE["ts"] if LIVE["ts"] else 9999
    return {"signals": build_signals_fast(tf), "mt5_connected": age<30}

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse("""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RULER PRO v2.3</title><style>
*{box-sizing:border-box}html,body{margin:0;background:#020202;color:#d0d0d0;font-family:monospace;height:100dvh;overflow:hidden}
.phone{width:100%;max-width:480px;margin:0 auto;height:100dvh;background:#080a08;display:flex;flex-direction:column;border:1px solid #1e2e1e}
.header{display:flex;justify-content:space-between;align-items:center;padding:14px 14px;background:#0e1210;border-bottom:1px solid #2a3a2a}
.header b{color:#8aff6a;letter-spacing:1px}
.tf-bar{display:flex;gap:6px;padding:10px 12px;background:#0a0e0a;border-bottom:1px solid #1a2a1a}.tf-btn{padding:6px 16px;border-radius:6px;font-size:11px;font-weight:900;border:1px solid #2a3a2a;color:#6a7a6a;background:#121712;cursor:pointer}.tf-btn.active{background:#8aff6a;color:#000;border-color:#8aff6a}
.content{flex:1;overflow:auto;padding:10px 10px 80px;background:#050805}
.folder{margin-bottom:14px;border:1px solid #1e2e1e;border-radius:10px;overflow:hidden;background:#0a100a}
.folder-head{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;background:#121a12;font-weight:900;font-size:11px;letter-spacing:1px;border-bottom:1px solid #1e2e1e}
.folder-head span:first-child{color:#8aff6a}
.count{font-size:10px;background:#1a2a1a;padding:2px 8px;border-radius:10px;color:#8aff6a;border:1px solid #2a3a2a}
.table-head{display:flex;padding:8px 12px;font-size:8px;color:#5a6a5a;background:#080c08;border-bottom:1px solid #1a2a1a}
.row{display:flex;padding:11px 12px;font-size:11px;border-bottom:1px solid #101a10;align-items:center;background:#0a100a}.row:hover{background:#111a11}
.col-pair{width:26%;font-weight:900;color:#fff}.col-price{width:20%;color:#fff}.col-htf{width:14%;font-size:9px}.col-ltf{width:14%;font-size:9px}.col-score{width:10%;text-align:center;font-weight:900}.col-action{width:16%;text-align:right;font-weight:900;font-size:9px}
.green{color:#8aff6a}.yellow{color:#ffeb3b}.red{color:#ff5555}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:5px}.dot.green{background:#8aff6a;box-shadow:0 0 6px #8aff6a}.dot.yellow{background:#ffeb3b}.dot.red{background:#ff4444}
.search{margin:10px;background:#0e1510;border:1px solid #1e2e1e;border-radius:8px;padding:9px 12px;display:flex;gap:8px;color:#5a7a5a;font-size:11px}.search input{background:transparent;border:none;outline:none;color:#fff;font-family:monospace;font-size:11px;width:100%}
</style></head><body><div class="phone">
<div class="header"><b>RULER PRO v2.3</b><div style="font-size:9px" id="status"><span id="dot" class="dot yellow"></span><span id="statTxt">LOADING</span> <span id="clock" style="color:#5a7a5a;margin-left:6px">--:--</span></div></div>
<div class="search">🔍 <input id="searchBox" placeholder="Search BTC, GOLD, EURUSD..." oninput="render()" /></div>
<div class="tf-bar"><div class="tf-btn" id="tf-M15" onclick="setTF('M15')">M15</div><div class="tf-btn active" id="tf-M30" onclick="setTF('M30')">M30</div><div class="tf-btn" id="tf-H1" onclick="setTF('H1')">H1</div><div class="tf-btn" id="tf-H4" onclick="setTF('H4')">H4</div><div class="tf-btn" id="tf-D1" onclick="setTF('D1')">D1</div></div>
<div class="content" id="content">Loading professional folders...</div>
</div>
<script>
let all=[]; let curTF='M30';
const MAP={"METALS":["XAUUSD","XAGUSD"],"CRYPTO":["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],"FOREX":["EURUSD","GBPUSD","AUDUSD","USDCAD"],"ENERGY":["USOIL","UKOIL"],"INDICES":["US500","GER40","US10Y"]};
const ICONS={"METALS":"🥇","CRYPTO":"₿","FOREX":"💱","ENERGY":"🛢️","INDICES":"📈"};
function setTF(tf){curTF=tf; document.querySelectorAll('.tf-btn').forEach(b=>b.classList.remove('active')); document.getElementById('tf-'+tf).classList.add('active'); fetchPoll();}
function render(){
  let q=(document.getElementById('searchBox').value||'').toUpperCase().trim();
  let html='';
  Object.keys(MAP).forEach(g=>{
    let arr=all.filter(s=>MAP[g].includes(s.name));
    if(q) arr=arr.filter(s=>s.name.includes(q));
    arr.sort((a,b)=>b.score-a.score);
    if(arr.length==0 &&!q) return;
    html+=`<div class="folder"><div class="folder-head"><span>${ICONS[g]} ${g}</span><span class="count">${arr.length} PAIRS</span></div>`;
    html+=`<div class="table-head"><span class="col-pair">SYMBOL</span><span class="col-price">PRICE</span><span class="col-htf">HTF</span><span class="col-ltf">LTF</span><span class="col-score">SCORE</span><span class="col-action">SIGNAL</span></div>`;
    arr.forEach(x=>{
      let col=x.score>=70?'green':x.score>=50?'yellow':'red';
      let actCol=x.action.includes('ENTRY')?'green':x.action.includes('WAIT')?'yellow':'red';
      let displayName=x.name.replace('XAUUSD','GOLD').replace('XAGUSD','SILVER').replace('USOIL','WTI').replace('UKOIL','BRENT');
      html+=`<div class="row"><span class="col-pair">● ${displayName}</span><span class="col-price">${x.price}</span><span class="col-htf">${x.htf_score}</span><span class="col-ltf">${x.ltf_score}</span><span class="col-score ${col}">${(x.score/10).toFixed(1)}</span><span class="col-action ${actCol}">${x.action}</span></div>`;
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
      if(d.mt5_connected){dot.className='dot green'; txt.innerText='MT5 LIVE'; txt.style.color='#8aff6a';}
      else{dot.className='dot yellow'; txt.innerText='REAL FEED'; txt.style.color='#ffeb3b';}
      render();
    }
  }catch(e){}
}
setInterval(()=>{document.getElementById('clock').innerText=new Date().toLocaleTimeString();},1000);
setInterval(fetchPoll,5000);
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
