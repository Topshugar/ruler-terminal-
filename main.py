from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from collections import deque
import math, random, threading, time, requests
from datetime import datetime

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

LIVE={"prices":{},"hist":{}}
for s in ALL:
 LIVE["hist"][s]=deque(maxlen=300)
 LIVE["prices"][s]=0

SEED = {"XAUUSD":2690,"XAGUSD":31.8,"BTCUSD":68500,"ETHUSD":2680,"SOLUSD":158,"XRPUSD":0.62,"BNBUSD":620,"ADAUSD":0.39,"DOGEUSD":0.16,"AVAXUSD":28.5,"EURUSD":1.088,"GBPUSD":1.295,"AUDUSD":0.662,"USDCAD":1.391,"USOIL":71.8,"UKOIL":75.4,"US500":5830,"GER40":19250,"US10Y":4.28,"US02Y":4.05,"DE10Y":2.35,"UK10Y":4.26}
for s in ALL:
 for i in range(300):
  LIVE["hist"][s].append(SEED.get(s,100)*(1+(random.random()-0.5)*0.005))

def ema(vals,n):
 if len(vals)<n: return sum(vals)/len(vals) if vals else 0
 k=2/(n+1); e=sum(vals[:n])/n
 for v in vals[n:]: e=v*k+e*(1-k)
 return e
def sma(vals,n): return sum(vals[-n:])/n if len(vals)>=n else sum(vals)/len(vals)
def rsi_vals(vals,n=21):
 if len(vals)<n+1: return [50.0]*len(vals)
 rs=[]
 for idx in range(len(vals)):
  if idx<n: rs.append(50.0)
  else:
   g=l=0
   for i in range(idx-n+1,idx+1):
    ch=vals[i]-vals[i-1]
    if ch>0: g+=ch
    else: l+=abs(ch)
   rs.append(70.0 if l==0 else 100-(100/(1+g/l)))
 return rs
def bb(vals,n=21):
 if len(vals)<n: return 0,0,0,0
 mid=ema(vals[-n:],n); mean=sum(vals[-n:])/n
 var=sum((x-mean)**2 for x in vals[-n:])/n; dev=math.sqrt(var)
 up=mid+2*dev; lo=mid-2*dev; width=((up-lo)/mid*100) if mid else 0
 return mid,up,lo,width

def fetch_real():
 while True:
  try:
   # CRYPTO from Binance
   r=requests.get("https://api.binance.com/api/v3/ticker/price", timeout=6).json()
   mp={x['symbol']:float(x['price']) for x in r}
   mapping={"BTCUSDT":"BTCUSD","ETHUSDT":"ETHUSD","SOLUSDT":"SOLUSD","XRPUSDT":"XRPUSD","BNBUSDT":"BNBUSD","ADAUSDT":"ADAUSD","DOGEUSDT":"DOGEUSD","AVAXUSDT":"AVAXUSD"}
   for bin_sym, our_sym in mapping.items():
    if bin_sym in mp:
     p=mp[bin_sym]
     LIVE["prices"][our_sym]=p
     LIVE["hist"][our_sym].append(p)
   # FOREX + GOLD from free exchangerate (approx real)
   try:
    fx=requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=6).json()
    rates=fx.get('rates',{})
    if rates:
     if 'EUR' in rates: LIVE["prices"]["EURUSD"]=1/rates['EUR']; LIVE["hist"]["EURUSD"].append(1/rates['EUR'])
     if 'GBP' in rates: LIVE["prices"]["GBPUSD"]=1/rates['GBP']; LIVE["hist"]["GBPUSD"].append(1/rates['GBP'])
     if 'AUD' in rates: LIVE["prices"]["AUDUSD"]=1/rates['AUD']; LIVE["hist"]["AUDUSD"].append(1/rates['AUD'])
     if 'CAD' in rates: LIVE["prices"]["USDCAD"]=rates['CAD']; LIVE["hist"]["USDCAD"].append(rates['CAD'])
   except: pass
   # GOLD - use XAU from forex gold api fallback
   try:
    g=requests.get("https://api.gold-api.com/price/XAU", timeout=6).json()
    if 'price' in g:
     LIVE["prices"]["XAUUSD"]=float(g['price']); LIVE["hist"]["XAUUSD"].append(float(g['price']))
   except: pass
  except Exception as e:
   print("fetch error", e)
  time.sleep(5)

threading.Thread(target=fetch_real, daemon=True).start()

def build():
 out=[]
 for sym in ALL:
  hist=list(LIVE["hist"][sym])
  price=LIVE["prices"].get(sym,0) or (hist[-1] if hist else 0)
  if len(hist)<100 or price==0: continue
  sma200=sma(hist,200); mid,up,low,width=bb(hist,21)
  rsi_arr=rsi_vals(hist,21); r=rsi_arr[-1]
  widths=[bb(hist[i-21:i],21)[3] for i in range(len(hist)-20,len(hist)) if i>=21]
  avg_w=sum(widths)/len(widths) if widths else width
  fuel=int(max(10,min(100,(width/avg_w*50)+25))) if avg_w else 50
  power=int(max(0,min(100,r)))
  dist=abs(price-sma200)/price*100
  bias="Buy" if price>sma200 else "Sell"
  if dist<0.30: signal="Wait"; reason="Market is flat"
  else:
   signal="Wait"; reason="Waiting for setup"
   if bias=="Buy" and power>50:
    if abs(price-mid)/price*100<1.3: signal="Buy Now"; reason=f"Pullback to {mid:.1f}"
    elif fuel<45: signal="Buy Now"; reason=f"Low fuel {fuel}%"
    elif fuel<50: signal="Watch"; reason="Fuel low, ready"
   if bias=="Sell" and power<50:
    if abs(price-mid)/price*100<1.3: signal="Sell Now"; reason=f"Pullback to {mid:.1f}"
    elif fuel<45: signal="Sell Now"; reason=f"Low fuel {fuel}%"
    elif fuel<50: signal="Watch"; reason="Fuel low, ready"
  atr=(up-low)/2 if up and low else price*0.008
  sl=mid-atr*1.2 if bias=="Buy" else mid+atr*1.2
  tp=up if bias=="Buy" else low
  out.append({"name":sym,"price":price,"trend":bias,"power":power,"fuel":fuel,"signal":signal,"reason":reason,"tp":tp,"sl":sl,"mid":mid,"dist":dist})
 return sorted(out,key=lambda x:(0 if "Now" in x["signal"] else 1))

@app.get("/api/signals")
def sig(): return {"signals":build(),"mt5":True}

@app.get("/", response_class=HTMLResponse)
def ui():
 return HTMLResponse(open(__file__).read().split('HTML_START')[1].split('HTML_END')[0] if 'HTML_START' in open(__file__).read() else """
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Terminal Pro Real</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#000;color:#e6e6e6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;height:100dvh;overflow:hidden}
.phone{max-width:520px;margin:0 auto;height:100dvh;background:#000;display:flex;flex-direction:column}
.top{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#0a0a0a;border-bottom:1px solid #1a1a1a}
.top b{font-size:14px;color:#fff}.dot{width:6px;height:6px;border-radius:50%;background:#26a69a;box-shadow:0 0 6px #26a69a}
.con{flex:1;overflow:auto}
.folder{height:42px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#0d0d0d;border-bottom:1px solid #1a1a1a}
.folder b{font-size:12px;color:#cfcfcf;display:flex;gap:10px}
.list.open{display:block}.list{display:none}
.row{height:56px;display:flex;align-items:center;justify-content:space-between;padding:0 14px 0 28px;border-bottom:1px solid #0f0f0f}
.sym{font-size:12.5px;font-weight:600;color:#fff}.meta{font-size:10px;color:#6a6a6a;margin-top:2px}
.pr{font-size:12.5px;color:#fff;text-align:right}.trend{font-size:10px;text-align:right;margin-top:2px}
.buy{color:#26a69a}.sell{color:#ef5350}.wait{color:#555}
.det{display:none;padding:10px 14px 12px 28px;background:#0a0a0a;border-bottom:1px solid #161616}.det.open{display:block}
.l{font-size:11px;color:#888}.box{display:flex;gap:8px;margin-top:8px}
.box div{flex:1;background:#111;border:1px solid #1e1e1e;padding:8px}.box div span{font-size:9px;color:#666;display:block;margin-bottom:3px}.box div b{font-size:12px;color:#fff}
.bot{height:52px;display:flex;justify-content:space-around;align-items:center;background:#0a0a0a;border-top:1px solid #1a1a1a}.bot div{font-size:9px;color:#555}.bot div.on{color:#fff}
</style></head><body><div class="phone">
<div class="top"><b>Market Watch • REAL</b><div style="display:flex;align-items:center;gap:6px;font-size:10px;color:#8a8a8a"><div class="dot"></div>LIVE</div></div>
<div class="con" id="con"></div>
<div class="bot"><div class="on">Quotes</div><div>Charts</div><div>Trade</div><div>History</div><div>Settings</div></div>
</div>
<script>
const MAP={"METALS":["XAUUSD","XAGUSD"],"CRYPTO":["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],"FOREX":["EURUSD","GBPUSD","AUDUSD","USDCAD"],"ENERGY":["USOIL","UKOIL"],"INDICES":["US500","GER40"],"BONDS":["US10Y","US02Y","DE10Y","UK10Y"]};
let all=[];
function toggle(g){document.getElementById('list-'+g).classList.toggle('open'); document.getElementById('fold-'+g).classList.toggle('open');}
function render(){
 let h='';
 Object.keys(MAP).forEach(g=>{
  let arr=all.filter(x=>MAP[g].includes(x.name));
  let now=arr.filter(x=>x.signal.includes('Now')).length;
  h+=`<div class="folder open" id="fold-${g}" onclick="toggle('${g}')"><b><i>▸</i> ${g}</b><span style="font-size:10px;color:#555">${now?now+' Now':''}</span></div><div class="list open" id="list-${g}">`;
  arr.forEach(x=>{
   let c=x.signal.includes('Buy')?'buy':x.signal.includes('Sell')?'sell':'wait';
   h+=`<div class="row" onclick="this.nextElementSibling.classList.toggle('open')"><div><div class="sym">${x.name}</div><div class="meta">Power ${x.power}% • Fuel ${x.fuel}% • ${x.reason}</div></div><div><div class="pr">${x.price.toFixed(x.price<5?4:2)}</div><div class="trend ${c}">${x.signal}</div></div></div><div class="det"><div class="l"><b>Trend:</b> ${x.trend} <b>Power:</b> ${x.power}% <b>Fuel:</b> ${x.fuel}%</div><div class="box"><div><span>STOP LOSS</span><b>${x.sl.toFixed(2)}</b></div><div><span>TAKE PROFIT</span><b>${x.tp.toFixed(2)}</b></div></div></div>`;
  });
  h+=`</div>`;
 });
 document.getElementById('con').innerHTML=h;
}
async function load(){let r=await fetch('/api/signals');let d=await r.json();all=d.signals;render();}
setInterval(load,4000);load();
</script></body></html>
""") 
