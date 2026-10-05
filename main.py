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
  LIVE["hist"][s].append(base*(1+(random.random()-0.5)*0.012))
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
   else: rs.append(100-(100/(1+gains/losses)))
 return rs
def bb(vals,n=21,std=2.0):
 if len(vals)<n: return 0,0,0,0
 mid=ema(vals[-n:],n)
 sv=vals[-n:]; mean=sum(sv)/n
 var=sum((x-mean)**2 for x in sv)/n
 dev=math.sqrt(var); up=mid+std*dev; lo=mid-std*dev
 width=((up-lo)/mid*100) if mid else 0
 return mid,up,lo,width

def build():
 out=[]
 is_live = (datetime.now(timezone.utc).timestamp()-LIVE["ts"])<90
 chop_limit = 0.30 if is_live else 0.15
 for sym in ALL:
  hist=[x for x in LIVE["hist"][sym] if x>0]
  if len(hist)<210: continue
  price=LIVE["prices"][sym]
  sma200=sma(hist,200); mid,up,low,width=bb(hist,21,2.0)
  rsi_arr=rsi_vals(hist,21); r=rsi_arr[-1]
  widths=[]
  for i in range(len(hist)-20,len(hist)):
   if i>=21: widths.append(bb(hist[i-21:i],21,2.0)[3])
  avg_w=sum(widths)/len(widths) if widths else width
  fuel_pct = int(max(10,min(100,(width/avg_w*50)+25))) if avg_w else 50
  power_pct = int(max(0,min(100,r)))
  bull_div = hist[-1] < min(hist[-15:-3])*0.998 and r > min(rsi_arr[-15:-3])
  bear_div = hist[-1] > max(hist[-15:-3])*1.002 and r < max(rsi_arr[-15:-3])
  dist_sma = abs(price-sma200)/price*100 if price else 0
  bias = "Buy" if price>sma200 else "Sell"
  if dist_sma < chop_limit:
   signal="Wait"; reason="Market is flat"
  else:
   signal="Wait"; reason="Waiting for setup"
   if bias=="Buy" and (power_pct>50 or bull_div):
    if abs(price-mid)/price*100 <1.3 and fuel_pct<85:
     signal="Buy Now"; reason=f"Pullback to {mid:.2f}"
    elif fuel_pct<45 and (power_pct>55 or bull_div):
     signal="Buy Now"; reason=f"Breakout fuel low {fuel_pct}%"
    elif fuel_pct<50:
     signal="Watch"; reason="Low fuel, ready"
   if bias=="Sell" and (power_pct<50 or bear_div):
    if abs(price-mid)/price*100 <1.3 and fuel_pct<85:
     signal="Sell Now"; reason=f"Pullback to {mid:.2f}"
    elif fuel_pct<45 and (power_pct<45 or bear_div):
     signal="Sell Now"; reason=f"Breakout fuel low {fuel_pct}%"
    elif fuel_pct<50:
     signal="Watch"; reason="Low fuel, ready"
  atr=(up-low)/2 if up and low else price*0.008
  sl = mid - atr*1.2 if bias=="Buy" else mid + atr*1.2
  tp = up if bias=="Buy" else low
  out.append({"name":sym,"price":price,"trend":bias,"power":power_pct,"fuel":fuel_pct,"signal":signal,"reason":reason,"tp":tp,"sl":sl,"mid":mid,"dist":dist_sma})
 return sorted(out,key=lambda x:(0 if "Now" in x["signal"] else 1 if x["signal"]=="Watch" else 2))

@app.get("/api/signals")
def sig():
 return {"signals":build(),"mt5":(datetime.now(timezone.utc).timestamp()-LIVE["ts"])<90}

def fallback():
 while True:
  try:
   if (datetime.now(timezone.utc).timestamp()-LIVE["ts"])>90:
    for s in ALL:
     p=LIVE["prices"][s]
     if p:
      np=p*(1+(random.random()-0.5)*0.0011)
      LIVE["prices"][s]=np; LIVE["hist"][s].append(np)
  except: pass
  time.sleep(4)
threading.Thread(target=fallback,daemon=True).start()

@app.get("/", response_class=HTMLResponse)
def ui():
 return HTMLResponse("""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Terminal v4.2 Pro</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#000;color:#e6e6e6;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;height:100dvh;overflow:hidden;-webkit-font-smoothing:antialiased}
.phone{max-width:520px;margin:0 auto;height:100dvh;background:#000;display:flex;flex-direction:column}
.top{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#0a0a0a;border-bottom:1px solid #1a1a1a}
.top b{font-size:14px;font-weight:600;color:#fff}
.live{font-size:10px;color:#8a8a8a;display:flex;align-items:center;gap:6px}
.dot{width:6px;height:6px;border-radius:50%;background:#555}.dot.on{background:#26a69a;box-shadow:0 0 6px #26a69a}
.tfs{display:flex;gap:18px;padding:10px 14px;background:#080808;border-bottom:1px solid #151515}
.tfs span{font-size:11px;color:#666;cursor:pointer;padding-bottom:3px;border-bottom:1px solid transparent}
.tfs span.on{color:#fff;border-color:#fff}
.con{flex:1;overflow:auto;background:#000}
.folder{height:42px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#0d0d0d;border-bottom:1px solid #1a1a1a;cursor:pointer}
.folder b{font-size:12px;font-weight:600;color:#cfcfcf;letter-spacing:.4px;display:flex;align-items:center;gap:10px}
.folder b i{font-style:normal;color:#555;font-size:10px;transition:.2s;display:inline-block}
.folder.open b i{transform:rotate(90deg)}
.folder.cnt{font-size:10px;color:#555}
.list{display:none}.list.open{display:block}
.row{height:56px;display:flex;align-items:center;justify-content:space-between;padding:0 14px 0 28px;border-bottom:1px solid #0f0f0f;cursor:pointer}
.row:hover{background:#0a0a0a}
.left.sym{font-size:12.5px;font-weight:600;color:#fff;letter-spacing:.3px}
.left.meta{font-size:10px;color:#6a6a6a;margin-top:2px}
.right{text-align:right}.right.pr{font-size:12.5px;font-weight:500;color:#fff}
.right.trend{font-size:10px;margin-top:2px}
.trend.buy{color:#26a69a}.trend.sell{color:#ef5350}.trend.wait{color:#555}
.det{display:none;padding:10px 14px 12px 28px;background:#0a0a0a;border-bottom:1px solid #161616}
.det.open{display:block}.det.l{font-size:11px;color:#888;line-height:18px}.det.l b{color:#ddd;font-weight:600}
.det.box{display:flex;gap:8px;margin-top:8px}
.box div{flex:1;background:#111;border:1px solid #1e1e1e;padding:8px 10px}
.box div span{display:block;font-size:9px;color:#666;letter-spacing:.5px;margin-bottom:3px}
.box div b{font-size:12px;font-weight:600;color:#fff}
.bot{height:52px;display:flex;justify-content:space-around;align-items:center;background:#0a0a0a;border-top:1px solid #1a1a1a}
.bot div{font-size:9px;color:#555;text-align:center;line-height:12px}.bot div.on{color:#fff}
</style></head><body><div class="phone">
<div class="top"><b>Market Watch</b><div class="live"><div id="dot" class="dot"></div><span id="st">SIM</span> <span id="clk" style="margin-left:8px;color:#444"></span></div></div>
<div class="tfs"><span class="on">M15</span><span>M30</span><span>H1</span><span>H4</span><span>D1</span></div>
<div class="con" id="con"></div>
<div class="bot"><div class="on">Quotes</div><div>Charts</div><div>Trade</div><div>History</div><div>Settings</div></div>
</div>
<script>
const MAP={"METALS":["XAUUSD","XAGUSD"],"CRYPTO":["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],"FOREX":["EURUSD","GBPUSD","AUDUSD","USDCAD"],"ENERGY":["USOIL","UKOIL"],"INDICES":["US500","GER40"],"BONDS":["US10Y","US02Y","DE10Y","UK10Y"]};
const NAMES={"XAUUSD":"Gold","XAGUSD":"Silver","BTCUSD":"Bitcoin","ETHUSD":"Ethereum","SOLUSD":"Solana","XRPUSD":"XRP","BNBUSD":"BNB","ADAUSD":"Cardano","DOGEUSD":"Doge","AVAXUSD":"Avax","EURUSD":"Euro","GBPUSD":"Pound","AUDUSD":"Aussie","USDCAD":"USDCAD","USOIL":"US Oil","UKOIL":"UK Oil","US500":"US500","GER40":"GER40","US10Y":"US10Y","US02Y":"US02Y","DE10Y":"DE10Y","UK10Y":"UK10Y"};
let all=[];
function toggle(g){document.getElementById('list-'+g).classList.toggle('open'); document.getElementById('fold-'+g).classList.toggle('open');}
function render(){
 let h='';
 Object.keys(MAP).forEach(g=>{
  let arr=all.filter(x=>MAP[g].includes(x.name));
  let now=arr.filter(x=>x.signal.includes('Now')).length;
  h+=`<div class="folder open" id="fold-${g}" onclick="toggle('${g}')"><b><i>▸</i> ${g} <span style="font-weight:400;color:#666;font-size:10px">${MAP[g].length}</span></b><span class="cnt">${now?now+' Buy/Sell Now':''}</span></div><div class="list open" id="list-${g}">`;
  arr.forEach(x=>{
   let sigC = x.signal.includes('Buy')?'buy':x.signal.includes('Sell')?'sell':'wait';
   h+=`<div class="row" onclick="let d=this.nextElementSibling;d.classList.toggle('open')"><div class="left"><div class="sym">${x.name} <span style="font-weight:400;color:#666;font-size:11px">${NAMES[x.name]||''}</span></div><div class="meta">Power ${x.power}% • Fuel ${x.fuel}% • ${x.reason}</div></div><div class="right"><div class="pr">${Number(x.price).toFixed(x.name.includes('USD') && x.price<5?4:2)}</div><div class="trend ${sigC}">${x.signal}</div></div></div><div class="det"><div class="l"><b>Trend:</b> ${x.trend} &nbsp; <b>Power:</b> ${x.power}% &nbsp; <b>Fuel:</b> ${x.fuel}% &nbsp; <b>Flat:</b> ${x.dist.toFixed(2)}%<br><b>Signal:</b> ${x.signal} — ${x.reason}<br>Rule: 200SMA + 21EMA + 21BB + RSI21</div><div class="box"><div><span>STOP LOSS</span><b>${x.sl.toFixed(2)}</b></div><div><span>TAKE PROFIT</span><b>${x.tp.toFixed(2)}</b></div><div><span>MIDDLE</span><b>${x.mid.toFixed(2)}</b></div></div></div>`;
  });
  h+=`</div>`;
 });
 document.getElementById('con').innerHTML=h;
}
async function load(){
 try{
  let r=await fetch('/api/signals'); let d=await r.json(); all=d.signals;
  document.getElementById('dot').className='dot '+(d.mt5?'on':'');
  document.getElementById('st').innerText=d.mt5?'LIVE':'SIM';
  document.getElementById('clk').innerText=new Date().toLocaleTimeString();
  render();
 }catch(e){}
}
setInterval(load,3000); load();
</script></body></html>
""") 
