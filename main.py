from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import requests, os
from datetime import datetime, timedelta
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

def ema_calc(closes, period=50):
    if not closes: return 0
    if len(closes) < period: return sum(closes)/len(closes)
    k = 2/(period+1)
    ema = sum(closes[:period])/period
    for p in closes[period:]:
        ema = p*k + ema*(1-k)
    return ema

def fetch_real():
    now = datetime.utcnow().timestamp()
    if now - LIVE["ts"] < 8: return
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=5)
        if r.status_code == 200:
            for it in r.json():
                LIVE["prices"][it["symbol"]] = float(it["price"])
                for our, bsym in BINANCE_MAP.items():
                    if bsym == it["symbol"]:
                        LIVE["prices"][our] = float(it["price"])
                        if our not in LIVE["history"]: LIVE["history"][our]=deque(maxlen=60)
                        LIVE["history"][our].append(float(it["price"]))
        symbols = ",".join(SYMBOL_MAP_TWELVE.values())
        r2 = requests.get(f"https://api.twelvedata.com/price?symbol={symbols}&apikey={TWELVE_KEY}", timeout=8)
        if r2.status_code == 200:
            data = r2.json()
            for clean, twelve_sym in SYMBOL_MAP_TWELVE.items():
                if twelve_sym in data and isinstance(data[twelve_sym], dict) and "price" in data[twelve_sym]:
                    try:
                        price = float(data[twelve_sym]["price"])
                        LIVE["prices"][clean] = price
                        if clean not in LIVE["history"]: LIVE["history"][clean]=deque(maxlen=60)
                        LIVE["history"][clean].append(price)
                    except: pass
        LIVE["ts"] = now
    except Exception as e:
        print(e)

def get_real_history(symbol, tf):
    if symbol in BINANCE_MAP:
        try:
            iv = {"M15":"15m","M30":"30m","H1":"1h","H4":"4h","D1":"1d"}[tf]
            k = requests.get(f"https://api.binance.com/api/v3/klines?symbol={BINANCE_MAP[symbol]}&interval={iv}&limit=60", timeout=5).json()
            return [float(x[4]) for x in k]
        except: pass
    if symbol in SYMBOL_MAP_TWELVE:
        try:
            iv = {"M15":"15min","M30":"30min","H1":"1h","H4":"4h","D1":"1day"}[tf]
            sym = SYMBOL_MAP_TWELVE[symbol]
            r = requests.get(f"https://api.twelvedata.com/time_series?symbol={sym}&interval={iv}&outputsize=60&apikey={TWELVE_KEY}", timeout=8).json()
            if "values" in r:
                return [float(x["close"]) for x in r["values"][::-1]]
        except: pass
    return list(LIVE["history"].get(symbol, []))

class M:
    def __init__(self): self.c=[];
    async def connect(self,w): await w.accept(); self.c.append(w)
    def disc(self,w):
        if w in self.c: self.c.remove(w)
    async def broad(self,m):
        for x in self.c[:]:
            try: await x.send_json(m)
            except: self.disc(x)
manager=M()

def stable_calc(pair, tf):
    fetch_real()
    name = next((n for t,n,g in ALL if t==pair), pair)
    live = LIVE["prices"].get(name)
    if not live: return None
    closes = get_real_history(name, tf)
    ema = ema_calc(closes, 50) if closes else live*0.999
    action = "BUY NOW" if live > ema else "SELL NOW"
    diff = (live-ema)/live*100
    score = max(10, min(95, round(50 + diff*12, 1)))
    sl = live*0.996 if "BUY" in action else live*1.004
    tp = live*1.008 if "BUY" in action else live*0.992
    if tf=="H4": sl=live*0.992 if "BUY" in action else live*1.008; tp=live*1.015 if "BUY" in action else live*0.985
    if tf=="D1": sl=live*0.985 if "BUY" in action else live*1.015; tp=live*1.03 if "BUY" in action else live*0.97
    return {"price":round(live,4 if live<100 else 2),"sl":round(sl,4),"tp":round(tp,4),"action":action,"score":score,"rr":2.0,"reason":f"MT5 Real {tf} EMA50 ({len(closes)} candles)","name":name}

@app.get("/", response_class=HTMLResponse)
def home():
    html = """<html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>RULER v1.4</title><style>
*{box-sizing:border-box}html,body{margin:0;background:#020202;color:#8aff6a;font-family:monospace;height:100dvh;overflow:hidden}
.phone{width:100%;max-width:440px;margin:0 auto;height:100dvh;background:#050805;display:flex;flex-direction:column;position:relative;border:1px solid #1a2a1a;overflow:hidden}
.header{display:flex;justify-content:space-between;padding:10px 12px;background:#0a0f0a;border-bottom:2px solid #8aff6a33}.htitle{font-size:14px;font-weight:900;color:#8aff6a;line-height:1.2}.badge{border:1px solid #8aff6a;padding:4px 8px;border-radius:8px;font-size:8px;text-align:center}
.search{margin:8px 10px;background:#0a0f0a;border:1px solid #1a3a1a;border-radius:10px;padding:10px 12px;display:flex;gap:8px;color:#5a7a5a;font-size:12px;align-items:center}.search input{background:transparent;border:none;outline:none;color:#8aff6a;font-family:monospace;font-size:12px;width:100%}
.tf-bar{display:flex;gap:6px;padding:0 10px 8px;overflow:auto}.tf-btn{padding:6px 14px;border-radius:20px;font-size:11px;font-weight:900;border:1px solid #1a3a1a;color:#5a7a5a;background:#0a0f0a;cursor:pointer;white-space:nowrap}.tf-btn.active{background:#8aff6a;color:#000;border-color:#8aff6a}
.folder{margin:8px 10px;border:1px solid #1a3a1a;border-radius:12px;overflow:hidden;background:#080f08}.folder-head{display:flex;justify-content:space-between;padding:12px 12px;background:#0f1a0f;font-weight:900;font-size:13px;cursor:pointer}.folder-count{background:#1a2a3a;border-radius:12px;padding:2px 8px;font-size:11px;color:#8aff6a;border:1px solid #2a3a4a}
.table-head{display:flex;padding:8px 10px;font-size:9px;color:#5a7a5a;border-bottom:1px solid #111;background:#050805}.row{display:flex;padding:11px 10px;font-size:11px;border-bottom:1px solid #111;align-items:center}.col-pair{width:28%}.col-score{width:18%;text-align:center}.col-price{width:28%;text-align:center}.col-action{width:26%;text-align:right;font-weight:900;font-size:10px}
.green{color:#8aff6a}.red{color:#ff4444}.content{flex:1;overflow:auto;padding-bottom:80px}
.bottom-nav{position:absolute;bottom:0;left:0;right:0;background:#050805;border-top:1px solid #1a2a1a;display:flex;justify-content:space-around;padding:10px 0 18px}.nav-item{text-align:center;font-size:10px;color:#4a5a4a}.nav-item.active{color:#8aff6a}.nav-item b{display:block;font-size:18px}
</style></head><body><div class="phone">
<div class="header"><div class="htitle">RULER v1.4 <span id="clock">08:35:04</span> <span style="color:#5a7a5a">9 REAL • LIVE</span><br>[<span id="tfLabel">M30</span>] 🔊<br><span style="font-size:10px;color:#ffeb3b">Next M30 candle: <span id="nextC">24:56</span></span></div><div class="badge">MTS<br>FOLDERS</div></div>
<div style="text-align:right;padding:4px 10px;font-size:9px;color:#5a7a5a">Price live <span id="liveSec">4</span>s</div>
<div class="search">🔍 <input id="searchBox" placeholder="Search PAIR e.g. BTC, EUR, XAU, AAPL..." oninput="render()" /></div>
<div class="tf-bar"><div class="tf-btn" id="tf-M15" onclick="setTF('M15')">M15</div><div class="tf-btn active" id="tf-M30" onclick="setTF('M30')">M30</div><div class="tf-btn" id="tf-H1" onclick="setTF('H1')">H1</div><div class="tf-btn" id="tf-H4" onclick="setTF('H4')">H4</div><div class="tf-btn" id="tf-D1" onclick="setTF('D1')">D1</div></div>
<div class="content" id="content">Fetching MT5 real prices...</div>
<div class="bottom-nav"><div class="nav-item active"><b>◉</b>TERMINAL</div><div class="nav-item"><b>⛽</b>FUEL</div><div class="nav-item"><b>📰</b>NEWS</div><div class="nav-item"><b>📅</b>CALENDAR</div></div>
</div>
<script>
let all=[]; let curTF='M30'; let ws=null;
function setTF(tf){curTF=tf; document.querySelectorAll('.tf-btn').forEach(b=>b.classList.remove('active')); document.getElementById('tf-'+tf).classList.add('active'); document.getElementById('tfLabel').innerText=tf; if(ws)ws.close(); conn();}
function conn(){let p=location.protocol==='https:'?'wss:':'ws:'; ws=new WebSocket(p+'//'+location.host+'/ws?tf='+curTF); ws.onmessage=e=>{let d=JSON.parse(e.data); if(d.signals){all=d.signals; render();}}; ws.onclose=()=>setTimeout(conn,3000);}
function render(){
  let q = (document.getElementById('searchBox').value||'').toUpperCase().trim();
  let groups={};
  groups["CRYPTO"]=all.filter(s=>["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"].includes(s.name));
  groups["FOREX"]=all.filter(s=>["EURUSD","GBPUSD","AUDUSD","USDCAD"].includes(s.name));
  groups["COMMODITIES"]=all.filter(s=>["XAUUSD","XAGUSD","USOIL","UKOIL"].includes(s.name));
  groups["BONDS"]=all.filter(s=>["US10Y","GER40","US500"].includes(s.name));
  // apply search filter
  if(q){
    Object.keys(groups).forEach(g=>{
      groups[g]=groups[g].filter(s=>s.name.includes(q));
    });
  }
  let html='';
  Object.keys(groups).forEach(g=>{
    let arr=groups[g]; arr.sort((a,b)=>b.score-a.score);
    if(arr.length==0) return;
    let count = g==="CRYPTO"? arr.length+"/74" : arr.length+"/"+arr.length;
    html+=`<div class="folder"><div class="folder-head"><span>📁 ${g}</span><span class="folder-count">${count}</span></div>`;
    html+=`<div class="table-head"><span class="col-pair">PAIR [${curTF}]</span><span class="col-score">SCORE</span><span class="col-price">PRICE ●=REAL</span><span class="col-action">ACTION</span></div>`;
    arr.forEach(x=>{
      let colScore = x.score>=55? 'green' : 'red';
      let colAction = x.action.includes('BUY')? 'green' : 'red';
      html+=`<div class="row"><span class="col-pair">○ ${x.name}</span><span class="col-score ${colScore}">${x.score}</span><span class="col-price">${x.price}</span><span class="col-action ${colAction}">${x.action}</span></div>`;
    });
    html+=`</div>`;
  });
  if(!html && q) html=`<div style="padding:20px;text-align:center;color:#5a7a5a">No results for "${q}"</div>`;
  document.getElementById('content').innerHTML=html || 'Waiting for MT5 prices...';
}
setInterval(()=>{let el=document.getElementById('nextC'); if(el){let [m,s]=el.innerText.split(':').map(Number); if(!isNaN(m)&&!isNaN(s)){ if(s>0)s--; else if(m>0){m--;s=59}else{m=29;s=59;} el.innerText=String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');}} let ls=document.getElementById('liveSec'); if(ls){let v=parseInt(ls.innerText)||0; ls.innerText=(v%10)+1;} document.getElementById('clock').innerText=new Date().toLocaleTimeString();},1000);
conn();
</script></body></html>"""
    return HTMLResponse(html)

@app.websocket("/ws")
async def ws_ep(websocket: WebSocket, tf: str="M30"):
    await manager.connect(websocket)
    try:
        while True:
            out=[]
            for tk,name,gr in ALL:
                d=stable_calc(tk,tf)
                if d: d["name"]=name; d["group"]=gr; out.append(d)
            await manager.broad({"signals":sorted(out,key=lambda x:x["score"],reverse=True)})
            await asyncio.sleep(8)
    except: manager.disc(websocket) 
