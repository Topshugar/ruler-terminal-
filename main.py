from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime, timezone
from collections import deque
import math

app = FastAPI()

GROUPS = {
 "METALS": ["XAUUSD","XAGUSD"],
 "CRYPTO": ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],
 "FOREX": ["EURUSD","GBPUSD","AUDUSD","USDCAD"],
 "ENERGY": ["USOIL","UKOIL"],
 "INDICES": ["US500","GER40"],
 "BONDS": ["US10Y","US02Y","DE10Y","UK10Y"]
}
ALL = [s for v in GROUPS.values() for s in v]

LIVE={"ts":0,"prices":{},"hist":{}}
for s in ALL:
 LIVE["hist"][s]=deque([0]*250,maxlen=250)
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

def ema(vals,n):
 if len(vals)<n: return sum(vals)/len(vals) if vals else 0
 k=2/(n+1); e=sum(vals[:n])/n
 for v in vals[n:]: e=v*k+e*(1-k)
 return e

def sma(vals,n):
 if len(vals)<n: return sum(vals)/len(vals) if vals else 0
 return sum(vals[-n:])/n

def rsi(vals,n=21):
 if len(vals)<n+1: return 50.0
 gains=0; losses=0
 for i in range(1,n+1):
  ch=vals[-i]-vals[-i-1]
  if ch>0: gains+=ch
  else: losses+=abs(ch)
 if losses==0: return 70.0
 rs=gains/losses
 return round(100-(100/(1+rs)),1)

def bb(vals,n=21,std=2.0):
 if len(vals)<n: return 0,0,0,0
 mid=ema(vals[-n:],n)
 slice_vals=vals[-n:]
 mean=sum(slice_vals)/n
 var=sum((x-mean)**2 for x in slice_vals)/n
 dev=math.sqrt(var)
 upper=mid+std*dev
 lower=mid-std*dev
 width=((upper-lower)/mid*100) if mid else 0
 return mid, upper, lower, width

def build(tf):
 out=[]
 tf_mult = {"M15":0.6,"M30":0.8,"H1":1.0,"H4":1.5,"D1":2.5}.get(tf,1)
 for sym in ALL:
  hist=[x for x in LIVE["hist"][sym] if x>0]
  price=LIVE["prices"].get(sym,0)
  if price==0 and hist: price=hist[-1]
  if price==0 or len(hist)<30:
   out.append({"name":sym,"price":"--","bias":"NEUTRAL","vol":"--","rsi":50,"signal":"NO DATA","pattern":"None","dir":"--","sl":0,"tp1":0,"tp2":0,"rr":"--","mid":0,"up":0,"low":0})
   continue
  ema21=ema(hist,21)
  sma200=sma(hist,200)
  mid, up, low, width = bb(hist,21,2.0)
  r=rsi(hist,21)

  bias = "BULLISH" if price > sma200 else "BEARISH" if price < sma200 else "NEUTRAL"
  # Volatility
  avg_width = sum([bb(hist[i-21:i],21,2.0)[3] for i in range(len(hist)-10,len(hist)) if i>21])/10 if len(hist)>40 else width
  if width < avg_width*0.85: vol="SQUEEZE"
  elif width > avg_width*1.15: vol="EXPANSION"
  else: vol="NORMAL"

  is_buy = price > sma200
  dist_mid = abs(price-mid)/price*100 if price else 100

  signal="NO SETUP"; pattern="None"
  # Setup A: Trend Pullback
  if bias=="BULLISH" and dist_mid < 0.8*tf_mult and r>45 and r<62:
   signal="VALID ENTRY"; pattern="Setup A (Pullback)"
  elif bias=="BEARISH" and dist_mid < 0.8*tf_mult and r<55 and r>38:
   signal="VALID ENTRY"; pattern="Setup A (Pullback)"
  # Setup B: Squeeze Breakout
  elif vol=="SQUEEZE" and ((r>55 and bias=="BULLISH") or (r<45 and bias=="BEARISH")):
   signal="VALID ENTRY"; pattern="Setup B (Breakout)"
  elif vol=="SQUEEZE" and 45 <= r <= 55:
   signal="WATCHLIST"; pattern="Setup B forming"

  atr = (up-low)/2 if up and low else price*0.008
  if is_buy:
   sl=mid - atr*0.2
   tp1=up
   tp2=0
  else:
   sl=mid + atr*0.2
   tp1=low
   tp2=0
  rr="1:1.8" if pattern.startswith("Setup A") else "1:3.2" if pattern.startswith("Setup B") else "--"
  dir_="BUY" if is_buy else "SELL"

  out.append({"name":sym,"price":round(price,2),"bias":bias,"vol":vol,"rsi":r,"signal":signal,"pattern":pattern,"dir":dir_,"sl":round(sl,2),"tp1":round(tp1,2),"tp2":f"Trail {round(mid,2)}","rr":rr,"mid":round(mid,2),"up":round(up,2),"low":round(low,2),"width":round(width,2)})

 # Sort: VALID ENTRY first
 return sorted(out,key=lambda x: (0 if x["signal"]=="VALID ENTRY" else 1 if x["signal"]=="WATCHLIST" else 2, -x["rsi"]))

@app.get("/api/signals")
def signals(tf:str="M30"):
 return {"signals":build(tf),"mt5": (datetime.now(timezone.utc).timestamp()-LIVE["ts"])<90}

@app.get("/", response_class=HTMLResponse)
def ui():
 return HTMLResponse("""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RULER PRO</title><style>
*{box-sizing:border-box}body{margin:0;background:#020202;color:#c9c9c9;font-family:monospace;height:100dvh;overflow:hidden}
.phone{max-width:520px;margin:0 auto;height:100dvh;background:#080a08;display:flex;flex-direction:column;border:1px solid #1a2a1a}
.head{display:flex;justify-content:space-between;padding:14px;background:#0e1210;border-bottom:1px solid #2a3a2a}.head b{color:#8aff6a}
.tf{display:flex;gap:6px;padding:10px;background:#0a0e0a;border-bottom:1px solid #1a2a1a;overflow:auto}.btn{padding:6px 14px;border-radius:6px;font-size:10px;font-weight:900;border:1px solid #2a3a2a;color:#6a7a6a;background:#121712;white-space:nowrap;cursor:pointer}.btn.on{background:#8aff6a;color:#000;border-color:#8aff6a}
.con{flex:1;overflow:auto;padding:8px 8px 80px}
.box{border:1px solid #1e2e1e;border-radius:10px;overflow:hidden;margin-bottom:10px;background:#0a100a}
.boxh{display:flex;justify-content:space-between;align-items:center;padding:12px;background:#121a12;font-weight:900;font-size:11px;cursor:pointer}
.boxh.cnt{background:#1a2a1a;padding:2px 8px;border-radius:10px;color:#8aff6a;font-size:10px}
.drawer{display:none}.drawer.open{display:block}
.row{padding:10px;border-bottom:1px solid #101a10;cursor:pointer}.main{display:flex;font-size:10px;align-items:center}.c1{width:22%;color:#fff;font-weight:900}.c2{width:18%}.c3{width:30%;font-size:9px}.c4{width:30%;text-align:right;font-weight:900;font-size:9px}
.det{display:none;margin-top:8px;background:#0e150e;border:1px solid #1a2a1a;border-radius:6px;padding:8px;font-size:10px;line-height:1.8}.row.open.det{display:block}
.g{color:#8aff6a}.y{color:#ffeb3b}.r{color:#ff5555}.dot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:4px}.dg{background:#8aff6a;box-shadow:0 0 6px #8aff6a}.dy{background:#ffeb3b}
.tag{padding:1px 5px;border-radius:4px;font-size:8px;border:1px solid #2a3a2a}
</style></head><body><div class="phone">
<div class="head"><b>RULER PRO v4 TRIPLE</b><div style="font-size:9px"><span id="dot" class="dot dy"></span><span id="st">CHECKING</span> <span id="clk" style="color:#8aff6a;margin-left:6px"></span></div></div>
<div class="tf"><div class="btn on" id="M15" onclick="setTF('M15')">M15</div><div class="btn" id="M30" onclick="setTF('M30')">M30</div><div class="btn" id="H1" onclick="setTF('H1')">H1</div><div class="btn" id="H4" onclick="setTF('H4')">H4</div><div class="btn" id="D1" onclick="setTF('D1')">D1</div></div>
<div class="con" id="con">Loading triple-confluence...</div>
</div>
<script>
let cur='M30', all=[];
const MAP={"METALS":["XAUUSD","XAGUSD"],"CRYPTO":["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],"FOREX":["EURUSD","GBPUSD","AUDUSD","USDCAD"],"ENERGY":["USOIL","UKOIL"],"INDICES":["US500","GER40"],"BONDS":["US10Y","US02Y","DE10Y","UK10Y"]};
const ICO={"METALS":"🥇","CRYPTO":"₿","FOREX":"💱","ENERGY":"🛢️","INDICES":"📈","BONDS":"🏦"};
function setTF(t){cur=t; document.querySelectorAll('.btn').forEach(b=>b.classList.remove('on')); document.getElementById(t).classList.add('on'); load();}
function toggleDrawer(g){const d=document.getElementById('drawer-'+g); d.classList.toggle('open');}
function render(){
 let h=''; Object.keys(MAP).forEach(g=>{
  let arr=all.filter(x=>MAP[g].includes(x.name)); if(!arr.length) return;
  let validCount=arr.filter(x=>x.signal=='VALID ENTRY').length;
  h+=`<div class="box"><div class="boxh" onclick="toggleDrawer('${g}')"><span>${ICO[g]} ${g} ${validCount?`<span style='color:#8aff6a'>• ${validCount} ENTRY</span>`:''}</span><span style="display:flex;gap:8px;align-items:center"><span class="cnt">${arr.length} PAIRS</span><span style="color:#6a7a6a">▼</span></span></div><div class="drawer open" id="drawer-${g}">`;
  arr.forEach(x=>{
   let biasCol=x.bias=='BULLISH'?'g':x.bias=='BEARISH'?'r':'y';
   let sigCol=x.signal=='VALID ENTRY'?'g':x.signal=='WATCHLIST'?'y':'r';
   let volTag=x.vol=='SQUEEZE'?'🟡 SQUEEZE':x.vol=='EXPANSION'?'🟢 EXPANSION':'NORMAL';
   let price=x.price=='--'?'<span style="color:#555">--</span>':x.price;
   h+=`<div class="row" onclick="this.classList.toggle('open')"><div class="main"><span class="c1">● ${x.name.replace('XAUUSD','GOLD').replace('XAGUSD','SILVER')}</span><span class="c2">${price}</span><span class="c3"><span class="${biasCol}">${x.bias}</span> | ${volTag} | RSI ${x.rsi}</span><span class="c4 ${sigCol}">${x.signal}</span></div>
   <div class="det">
   <b>[${x.name} / ${cur}] Strategy Evaluation</b><br>
   * <b>Macro Bias:</b> <span class="${biasCol}">${x.bias}</span> (Price vs 200 SMA)<br>
   * <b>Volatility State:</b> ${x.vol} (BB Width ${x.width}% | Mid ${x.mid} | Upper ${x.up} | Lower ${x.low})<br>
   * <b>Momentum (RSI 21):</b> ${x.rsi} - ${x.rsi>55?'BULLISH':x.rsi<45?'BEARISH':'NEUTRAL'}<br><br>
   <b>Signal Status:</b> <span class="${sigCol}">${x.signal}</span><br>
   <b>Primary Pattern:</b> ${x.pattern}<br><br>
   <b>Execution Framework:</b><br>
   - <b>Trigger:</b> ${x.pattern.includes('Pullback')?'Bounce off 21 EMA / Mid Band '+x.mid:'Breakout close outside '+ (x.dir=='BUY'?x.up:x.low)}<br>
   - <b>Stop Loss:</b> ${x.sl} (Below 21 EMA)<br>
   - <b>Take Profit 1:</b> ${x.tp1} (${x.dir=='BUY'?'Upper BB':'Lower BB'})<br>
   - <b>Take Profit 2:</b> ${x.tp2} (Trail 21 EMA)<br>
   - <b>Risk-to-Reward:</b> ${x.rr}<br>
   - <b>Direction:</b> <span class="${x.dir=='BUY'?'g':'r'}">${x.dir}</span>
   </div></div>`;
  }); h+=`</div></div>`;
 }); document.getElementById('con').innerHTML=h;
}
async function load(){try{let r=await fetch('/api/signals?tf='+cur);let d=await r.json();all=d.signals; let dot=document.getElementById('dot'),st=document.getElementById('st'); if(d.mt5){dot.className='dot dg';st.innerText='MT5 LIVE';st.style.color='#8aff6a'}else{dot.className='dot dy';st.innerText='MT5 OFF - WAITING';st.style.color='#ffeb3b'} document.getElementById('clk').innerText=cur+' | '+new Date().toLocaleTimeString('en-GB',{timeZone:'Europe/London',hour:'2-digit',minute:'2-digit'})+' UK'; render();}catch(e){}}
setInterval(load,3500); load();
</script></body></html>
""") 
