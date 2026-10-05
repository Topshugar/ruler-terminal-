from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests
from datetime import datetime, timezone
from collections import deque

app = FastAPI()

GROUPS = {
 "METALS": ["XAUUSD","XAGUSD"],
 "CRYPTO": ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],
 "FOREX": ["EURUSD","GBPUSD","AUDUSD","USDCAD"],
 "ENERGY": ["USOIL","UKOIL"],
 "INDICES": ["US500","GER40","US10Y"]
}
ALL = [s for v in GROUPS.values() for s in v]

LIVE={"ts":0,"prices":{},"hist":{}}
for s in ALL:
 LIVE["hist"][s]=deque([0]*200,maxlen=200)
 LIVE["prices"][s]=0

class T(BaseModel):
 symbol:str; bid:float; ask:float

@app.post("/api/mt5/prices")
def push(t:list[T]):
 for x in t:
  p=(x.bid+x.ask)/2 if x.bid and x.ask else (x.bid or x.ask)
  name=x.symbol.upper()
  for s in ALL:
   if s in name: name=s
  if p>0:
   LIVE["prices"][name]=p
   LIVE["hist"][name].append(p)
 LIVE["ts"]=datetime.now(timezone.utc).timestamp()
 return {"ok":True}

def fetch_crypto():
 try:
  r=requests.get("https://api.binance.com/api/v3/ticker/price",timeout=3).json()
  mp={"BTCUSDT":"BTCUSD","ETHUSDT":"ETHUSD","SOLUSDT":"SOLUSD","XRPUSDT":"XRPUSD","BNBUSDT":"BNBUSD","ADAUSDT":"ADAUSD","DOGEUSDT":"DOGEUSD","AVAXUSDT":"AVAXUSD"}
  for it in r:
   if it["symbol"] in mp:
    p=float(it["price"]); s=mp[it["symbol"]]; LIVE["prices"][s]=p; LIVE["hist"][s].append(p)
 except: pass

def ema(vals,n):
 if len(vals)<n: return sum(vals)/len(vals) if vals else 0
 k=2/(n+1); e=sum(vals[:n])/n
 for v in vals[n:]: e=v*k+e*(1-k)
 return e

def build(tf):
 fetch_crypto()
 out=[]
 tf_mult = {"M15":1,"M30":1.2,"H1":1.5,"H4":2,"D1":3}.get(tf,1)
 for sym in ALL:
  hist=[x for x in LIVE["hist"][sym] if x>0]
  price=LIVE["prices"].get(sym,0)
  if price==0 and hist: price=hist[-1]
  if price==0:
   out.append({"name":sym,"price":"CLOSED","htf":0,"ltf":0,"score":0,"action":"OFF","dir":"--","tp1":0,"tp2":0,"sl":0,"pb":"--","rr":"--"})
   continue
  e21=ema(hist[-100:] if len(hist)>100 else hist,21)
  e50=ema(hist[-100:] if len(hist)>100 else hist,50)
  htf = 8.0 if price>e21>e50 else 2.5 if price<e21<e50 else 5.5
  ltf = 6.5 if abs(price-e21)/price*100 < 0.6*tf_mult else 4.5
  final = round((htf*0.6+ltf*0.4),1)
  score = round(final*10,1)

  is_buy = price>e21
  atr = price*0.008
  sl = price - atr*1.5 if is_buy else price + atr*1.5
  tp1 = price + atr*1.5 if is_buy else price - atr*1.5
  tp2 = price + atr*3 if is_buy else price - atr*3
  dist = abs(price-e21)/price*100
  pb = "PULLBACK YES" if dist<0.4 else "IN PULLBACK" if dist<0.9 else "WAIT PULLBACK"
  action = "ENTRY" if final>=6.5 and "YES" in pb else "WAIT" if final>=5.5 else "NO TRADE"
  dir_ = "BUY" if is_buy else "SELL"

  out.append({"name":sym,"price":round(price,2),"htf":htf,"ltf":ltf,"score":score,"action":action,"dir":dir_,"tp1":round(tp1,2),"tp2":round(tp2,2),"sl":round(sl,2),"pb":pb,"rr":"1:1.5"})
 return sorted(out,key=lambda x:x["score"],reverse=True)

@app.get("/api/signals")
def signals(tf:str="M30"):
 return {"signals":build(tf),"mt5": (datetime.now(timezone.utc).timestamp()-LIVE["ts"])<40}

@app.get("/", response_class=HTMLResponse)
def ui():
 return HTMLResponse("""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RULER PRO</title><style>
*{box-sizing:border-box}body{margin:0;background:#020202;color:#c9c9c9;font-family:monospace;height:100dvh;overflow:hidden}
.phone{max-width:520px;margin:0 auto;height:100dvh;background:#080a08;display:flex;flex-direction:column;border:1px solid #1a2a1a}
.head{display:flex;justify-content:space-between;padding:14px;background:#0e1210;border-bottom:1px solid #2a3a2a}.head b{color:#8aff6a}
.tf{display:flex;gap:6px;padding:10px;background:#0a0e0a;border-bottom:1px solid #1a2a1a}.btn{padding:6px 14px;border-radius:6px;font-size:10px;font-weight:900;border:1px solid #2a3a2a;color:#6a7a6a;background:#121712}.btn.on{background:#8aff6a;color:#000}
.con{flex:1;overflow:auto;padding:8px 8px 80px}
.box{border:1px solid #1e2e1e;border-radius:10px;overflow:hidden;margin-bottom:12px;background:#0a100a}
.boxh{display:flex;justify-content:space-between;padding:10px 12px;background:#121a12;font-weight:900;font-size:11px}
.row{padding:10px;border-bottom:1px solid #101a10}.main{display:flex;font-size:11px}.c1{width:26%;color:#fff;font-weight:900}.c2{width:22%}.c3{width:14%;text-align:center}.c4{width:14%;text-align:center}.c5{width:24%;text-align:right;font-weight:900;font-size:9px}
.det{display:none;margin-top:8px;background:#0e150e;border:1px solid #1a2a1a;border-radius:6px;padding:8px;font-size:10px;line-height:1.7}.open.det{display:block}
.g{color:#8aff6a}.y{color:#ffeb3b}.r{color:#ff5555}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:4px}.dg{background:#8aff6a;box-shadow:0 0 6px #8aff6a}.dy{background:#ffeb3b}
</style></head><body><div class="phone">
<div class="head"><b>RULER PRO v3</b><div style="font-size:9px"><span id="dot" class="dot dy"></span><span id="st">CHECKING</span> <span id="clk" style="color:#8aff6a;margin-left:6px"></span></div></div>
<div class="tf"><div class="btn on" id="M15" onclick="setTF('M15')">M15</div><div class="btn on" id="M30" onclick="setTF('M30')">M30</div><div class="btn" id="H1" onclick="setTF('H1')">H1</div><div class="btn" id="H4" onclick="setTF('H4')">H4</div><div class="btn" id="D1" onclick="setTF('D1')">D1</div></div>
<div class="con" id="con">Loading your statistics...</div>
</div>
<script>
let cur='M30', all=[];
const MAP={"METALS":["XAUUSD","XAGUSD"],"CRYPTO":["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],"FOREX":["EURUSD","GBPUSD","AUDUSD","USDCAD"],"ENERGY":["USOIL","UKOIL"],"INDICES":["US500","GER40","US10Y"]};
const ICO={"METALS":"🥇","CRYPTO":"₿","FOREX":"💱","ENERGY":"🛢️","INDICES":"📈"};
function setTF(t){cur=t; document.querySelectorAll('.btn').forEach(b=>b.classList.remove('on')); document.getElementById(t).classList.add('on'); load();}
function render(){
 let h=''; Object.keys(MAP).forEach(g=>{
  let arr=all.filter(x=>MAP[g].includes(x.name)); if(!arr.length) return;
  h+=`<div class="box"><div class="boxh"><span>${ICO[g]} ${g}</span><span style="background:#1a2a1a;padding:2px 8px;border-radius:10px;color:#8aff6a;font-size:10px">${arr.length} PAIRS</span></div>`;
  arr.forEach(x=>{
   let sc=(x.score/10).toFixed(1); let col=x.score>=65?'g':x.score>=55?'y':'r'; let act=x.action=='ENTRY'?'g':x.action=='WAIT'?'y':'r'; let name=x.name.replace('XAUUSD','GOLD').replace('XAGUSD','SILVER');
   let price=x.price=='CLOSED'?'<span style="color:#555">CLOSED</span>':x.price;
   h+=`<div class="row" onclick="this.classList.toggle('open')"><div class="main"><span class="c1">● ${name}</span><span class="c2">${price}</span><span class="c3 ${col}">${x.htf}</span><span class="c4 ${col}">${sc}</span><span class="c5 ${act}">${x.action}</span></div>
   <div class="det">DIR: <b class="${x.dir=='BUY'?'g':'r'}">${x.dir}</b> | PB: <b class="${x.pb.includes('YES')?'g':'y'}">${x.pb}</b><br>TP1: ${x.tp1} | TP2: ${x.tp2} | SL: ${x.sl} | RR ${x.rr}<br>SCORE: HTF ${x.htf} | LTF ${x.ltf} | FINAL ${sc}</div></div>`;
  }); h+=`</div>`;
 }); document.getElementById('con').innerHTML=h;
}
async function load(){try{let r=await fetch('/api/signals?tf='+cur);let d=await r.json();all=d.signals; let dot=document.getElementById('dot'),st=document.getElementById('st'); if(d.mt5){dot.className='dot dg';st.innerText='MT5 LIVE';st.style.color='#8aff6a'}else{dot.className='dot dy';st.innerText='CRYPTO ONLY';st.style.color='#ffeb3b'} document.getElementById('clk').innerText=cur+' | '+new Date().toLocaleTimeString('en-GB',{timeZone:'Europe/London',hour:'2-digit',minute:'2-digit'})+' UK'; render();}catch(e){}}
setInterval(load,3000); load();
</script></body></html>
""") 
