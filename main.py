from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime, timezone
from collections import deque
import math, random, threading, time

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
 LIVE["hist"][s]=deque(maxlen=300)
 LIVE["prices"][s]=0
SEED = {"XAUUSD":2690,"XAGUSD":31.8,"BTCUSD":68500,"ETHUSD":2680,"SOLUSD":158,"XRPUSD":0.62,"BNBUSD":620,"ADAUSD":0.39,"DOGEUSD":0.16,"AVAXUSD":28.5,"EURUSD":1.088,"GBPUSD":1.295,"AUDUSD":0.662,"USDCAD":1.391,"USOIL":71.8,"UKOIL":75.4,"US500":5830,"GER40":19250,"US10Y":4.28,"US02Y":4.05,"DE10Y":2.35,"UK10Y":4.26}
for s in ALL:
 base=SEED.get(s,100)
 for i in range(300):
  LIVE["hist"][s].append(base*(1+(random.random()-0.5)*0.01))
 LIVE["prices"][s]=base

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
def rsi_vals(vals,n=21):
 if len(vals)<n+1: return [50.0]*len(vals)
 rs=[]
 for idx in range(len(vals)):
  if idx < n: rs.append(50.0)
  else:
   gains=losses=0
   for i in range(idx-n+1,idx+1):
    ch=vals[i]-vals[i-1]
    if ch>0: gains+=ch
    else: losses+=abs(ch)
   if losses==0: rs.append(70.0)
   else:
    r=100-(100/(1+gains/losses))
    rs.append(r)
 return rs
def rsi(vals,n=21):
 return rsi_vals(vals,n)[-1] if vals else 50.0
def bb(vals,n=21,std=2.0):
 if len(vals)<n: return 0,0,0,0
 mid=ema(vals[-n:],n)
 slice_vals=vals[-n:]
 mean=sum(slice_vals)/n
 var=sum((x-mean)**2 for x in slice_vals)/n
 dev=math.sqrt(var)
 up=mid+std*dev; lo=mid-std*dev
 width=((up-lo)/mid*100) if mid else 0
 return mid,up,lo,width

def divergence(vals,rsi_arr):
 # simple: price lower low but RSI higher low in last 12
 if len(vals)<15 or len(rsi_arr)<15: return False, False
 recent_price=vals[-12:]; recent_rsi=rsi_arr[-12:]
 p_low=min(recent_price[:-3]); p_now=vals[-1]
 r_low=min(recent_rsi[:-3]); r_now=rsi_arr[-1]
 bull_div = p_now < p_low*0.998 and r_now > r_low
 bear_div = p_now > max(recent_price[:-3])*1.002 and r_now < max(recent_rsi[:-3])
 return bull_div, bear_div

def build(tf):
 out=[]
 for sym in ALL:
  hist=[x for x in LIVE["hist"][sym] if x>0]
  if len(hist)<220: continue
  price=LIVE["prices"].get(sym,0)
  ema21=ema(hist,21); sma200=sma(hist,200)
  mid,up,low,width=bb(hist,21,2.0)
  rsi_arr=rsi_vals(hist,21); r=rsi_arr[-1]
  # Avg width last 20 for squeeze formula <80%
  widths=[]
  for i in range(len(hist)-20,len(hist)):
   if i>=21:
    _,u,l,w=bb(hist[i-21:i],21,2.0)
    widths.append(w)
  avg_w=sum(widths)/len(widths) if widths else width
  is_squeeze = width < avg_w*0.80
  is_expansion = width > avg_w*1.12
  vol = "SQUEEZE" if is_squeeze else "EXPANSION" if is_expansion else "NORMAL"
  bias = "BULLISH" if price > sma200 else "BEARISH" if price < sma200 else "NEUTRAL"
  dist_sma = abs(price-sma200)/price*100 if price else 100
  # 0.3% filter
  if dist_sma < 0.30:
   bias_status = "NO TRADE - Chop near 200SMA"
   signal="NO SETUP"; pattern="Chop Zone (0.3%)"
  else:
   bias_status=bias
  dist_mid = abs(price-mid)/price*100 if price else 100
  bull_div, bear_div = divergence(hist,rsi_arr)
  # RSI stuck 45-55 for 5 candles in squeeze
  stuck = all(45 <= rsi_arr[-i] <= 55 for i in range(1,6)) and is_squeeze
  # ATR proxy
  atr = (up-low)/2 if up and low else price*0.008
  is_buy = price > sma200
  signal="NO SETUP"; pattern="None"; trig="Waiting"; rr="--"
  if dist_sma >= 0.30:
   # FINAL FILTER v4.1
   if bias=="BULLISH" and (vol in ["NORMAL","SQUEEZE"]) and (r>50 or bull_div):
    if dist_mid < 1.2 and not is_expansion:
     signal="VALID ENTRY"; pattern="Setup A (Pullback)"; trig=f"Bounce CLOSE off 21EMA {round(mid,2)}"; rr="1:2.4"
     if bull_div: pattern+=" + Bull Div"
    elif is_squeeze and (r>55 or stuck or bull_div):
     signal="VALID ENTRY"; pattern="Setup B (Breakout Retest)"; trig=f"Retest outer {round(up,2)} after squeeze"; rr="1:3.5"
    elif is_squeeze:
     signal="WATCHLIST"; pattern="Setup B forming (Squeeze)"; trig=f"Wait break >55, now RSI {r:.1f}"; rr="1:3.5"
   elif bias=="BEARISH" and (vol in ["NORMAL","SQUEEZE"]) and (r<50 or bear_div):
    if dist_mid < 1.2 and not is_expansion:
     signal="VALID ENTRY"; pattern="Setup A (Pullback)"; trig=f"Bounce CLOSE off 21EMA {round(mid,2)}"; rr="1:2.4"
     if bear_div: pattern+=" + Bear Div"
    elif is_squeeze and (r<45 or stuck or bear_div):
     signal="VALID ENTRY"; pattern="Setup B (Breakout Retest)"; trig=f"Retest outer {round(low,2)} after squeeze"; rr="1:3.5"
    elif is_squeeze:
     signal="WATCHLIST"; pattern="Setup B forming (Squeeze)"; trig=f"Wait break <45, now RSI {r:.1f}"; rr="1:3.5"
   if stuck and signal=="NO SETUP":
    signal="WATCHLIST"; pattern="RSI 45-55 x5 in Squeeze"; trig="Breakout imminent"

  sl = (mid - atr*1.2) if is_buy else (mid + atr*1.2)
  tp1 = up if is_buy else low
  tp2 = f"Trail 21EMA {round(mid,2)} - Exit early if RSI<{40} for BUY / >{60} for SELL"
  out.append({"name":sym,"price":round(price,2),"bias":bias_status,"vol":vol,"rsi":round(r,1),"signal":signal,"pattern":pattern,"trig":trig,"dir":"BUY" if is_buy else "SELL","sl":round(sl,2),"tp1":round(tp1,2),"tp2":tp2,"rr":rr,"mid":round(mid,2),"up":round(up,2),"low":round(low,2),"div": "BullDiv" if bull_div else "BearDiv" if bear_div else "","chop": dist_sma < 0.30})
 return sorted(out,key=lambda x: (0 if x["signal"]=="VALID ENTRY" else 1 if x["signal"]=="WATCHLIST" else 2, -x["rsi"]))

@app.get("/api/signals")
def signals(tf:str="M15"):
 return {"signals":build(tf),"mt5": (datetime.now(timezone.utc).timestamp()-LIVE["ts"])<90}

def fallback():
 while True:
  try:
   if (datetime.now(timezone.utc).timestamp()-LIVE["ts"])>90:
    for s in ALL:
     p=LIVE["prices"][s]
     if p:
      np=p*(1+(random.random()-0.5)*0.0009)
      LIVE["prices"][s]=np
      LIVE["hist"][s].append(np)
  except: pass
  time.sleep(5)
threading.Thread(target=fallback,daemon=True).start()

@app.get("/", response_class=HTMLResponse)
def ui():
 return HTMLResponse("""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RULER v4.1</title><style>
*{box-sizing:border-box}body{margin:0;background:#000;color:#d0d0d0;font-family:Arial,monospace;height:100dvh;overflow:hidden}
.phone{max-width:520px;margin:0 auto;height:100dvh;background:#0a0a0a;display:flex;flex-direction:column}
.top{display:flex;align-items:center;justify-content:space-between;padding:16px;background:#141414;border-bottom:1px solid #222}
.top b{font-size:18px;color:#fff}
.pills{display:flex;gap:6px;padding:10px;background:#0f0f0f;border-bottom:1px solid #1f1f1f}
.pill{padding:6px 14px;border-radius:6px;font-size:10px;font-weight:900;border:1px solid #333;color:#777;background:#1a1a1a;cursor:pointer}.pill.on{background:#ffcc00;color:#000;border-color:#ffcc00}
.con{flex:1;overflow:auto;padding:0 0 70px;background:#000}
.folder{background:#171717;border-bottom:1px solid #1f1f1f;padding:14px 16px;display:flex;justify-content:space-between;align-items:center;cursor:pointer}
.folder b{font-size:14px;color:#fff;letter-spacing:0.5px;display:flex;align-items:center;gap:10px}
.arrow{color:#666;transition:0.2s}.open.arrow{transform:rotate(90deg)}
.list{display:none;background:#0e0e0e}.list.open{display:block}
.row{padding:12px 16px 12px 44px;border-bottom:1px solid #111;display:flex;justify-content:space-between;align-items:center;cursor:pointer}
.row:hover{background:#151515}
.nm{font-weight:900;color:#fff;font-size:13px}.nm small{font-weight:400;color:#888;display:block;font-size:11px;margin-top:2px}
.pr{font-size:13px;font-weight:700}
.tag{font-size:8px;padding:3px 6px;border-radius:4px;font-weight:900;margin-left:6px}
.bull{background:#00c853;color:#000}.bear{background:#ff3d00;color:#fff}
.valid{background:#00e676;color:#000}.watch{background:#555;color:#fff}.no{color:#555}
.det{display:none;padding:10px 16px 10px 44px;background:#121212;border-left:3px solid #ffcc00;font-size:11px;line-height:1.9;color:#aaa}.row.open +.det{display:block}
.g{color:#00e676}.r{color:#ff5252}.y{color:#ffcc00}
.bot{display:flex;justify-content:space-around;background:#141414;border-top:1px solid #222;padding:8px 0;font-size:10px;color:#666}
.dot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:6px}.dg{background:#00e676}.dy{background:#ffcc00}
</style></head><body><div class="phone">
<div class="top"><b>◀ Market Watch v4.1</b><div style="font-size:10px"><span id="dot" class="dot dy"></span><span id="st">MT5 SIM</span></div></div>
<div class="pills"><div class="pill on" id="M15" onclick="setTF('M15')">M15</div><div class="pill" id="M30" onclick="setTF('M30')">M30</div><div class="pill" id="H1" onclick="setTF('H1')">H1</div><div class="pill" id="H4" onclick="setTF('H4')">H4</div><div class="pill" id="D1" onclick="setTF('D1')">D1</div><div id="clk" style="margin-left:auto;color:#666;font-size:10px;padding:6px"></div></div>
<div class="con" id="con"></div>
<div class="bot"><span style="color:#ffcc00">★<br>Quotes</span><span>📈<br>Chart</span><span>⇄<br>Trade</span><span>🕒<br>History</span><span>⚙️<br>Settings</span></div>
</div>
<script>
let cur='M15', all=[];
const MAP={"METALS":["XAUUSD","XAGUSD"],"CRYPTO":["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],"FOREX":["EURUSD","GBPUSD","AUDUSD","USDCAD"],"ENERGY":["USOIL","UKOIL"],"INDICES":["US500","GER40"],"BONDS":["US10Y","US02Y","DE10Y","UK10Y"]};
function setTF(t){cur=t; document.querySelectorAll('.pill').forEach(b=>b.classList.remove('on')); document.getElementById(t).classList.add('on'); load();}
function toggle(g){document.getElementById('list-'+g).classList.toggle('open'); document.getElementById('fold-'+g).classList.toggle('open');}
function render(){
 let h=''; Object.keys(MAP).forEach(g=>{
  let arr=all.filter(x=>MAP[g].includes(x.name)); if(!arr.length) return;
  let v=arr.filter(x=>x.signal=='VALID ENTRY').length;
  h+=`<div class="folder open" id="fold-${g}" onclick="toggle('${g}')"><b>📁 ${g} ${v?`<span style='color:#00e676;font-size:11px'>• ${v} ENTRY</span>`:''}</b><span class="arrow">▶</span></div><div class="list open" id="list-${g}">`;
  arr.forEach(x=>{
   let bull=x.bias.includes('BULLISH'); let sc=x.signal;
   h+=`<div class="row" onclick="this.classList.toggle('open')"><div><div class="nm">${x.name}<small>RSI ${x.rsi} • ${x.vol} ${x.div?`• <b style='color:#ffcc00'>${x.div}</b>`:''} ${x.chop?'• CHOP 0.3%':''}</small></div></div><div style="text-align:right"><div class="pr" style="color:${bull?'#00e676':x.bias.includes('BEARISH')?'#ff5252':'#888'}">${x.price} <span class="tag ${bull?'bull':x.bias.includes('BEARISH')?'bear':'no'}">${x.bias}</span></div><div style="margin-top:4px"><span class="tag ${sc=='VALID ENTRY'?'valid':sc=='WATCHLIST'?'watch':'no'}">${sc}</span></div></div></div><div class="det"><b>[${x.name} / ${cur}] v4.1 Triple</b><br>Macro: <span class="${bull?'g':'r'}">${x.bias}</span> 200SMA Filter 0.3%<br>Vol: ${x.vol} (${x.mid} / ${x.up} / ${x.low}) Squeeze=Width <80% avg20<br>RSI21: ${x.rsi} ${x.div?`+ ${x.div} Detected`:''}<br><br><b>${x.signal}</b> - ${x.pattern}<br>Trigger: ${x.trig}<br>SL: ${x.sl} (1.2xATR beyond 21EMA) | TP1: ${x.tp1} | ${x.tp2}<br>R:R ${x.rr} | DIR <span class="${x.dir=='BUY'?'g':'r'}">${x.dir}</span><br><br><i style='color:#666'>Body close through 21EMA against trend = SKIP. Wick touch + body bounce = VALID. Early exit if RSI<40 BUY / >60 SELL</i></div>`;
  }); h+=`</div>`;
 }); document.getElementById('con').innerHTML=h;
}
async function load(){try{let r=await fetch('/api/signals?tf='+cur);let d=await r.json();all=d.signals; document.getElementById('dot').className='dot '+(d.mt5?'dg':'dy'); document.getElementById('st').innerText=d.mt5?'MT5 LIVE':'MT5 SIM'; document.getElementById('clk').innerText=cur+' '+new Date().toLocaleTimeString(); render();}catch(e){}}
setInterval(load,3500); load();
</script></body></html>
""") 
