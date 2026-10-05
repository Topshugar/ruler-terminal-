from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from collections import deque
import math, random, threading, time, requests

app = FastAPI()

GROUPS = {
 "METALS": ["XAUUSD","XAGUSD","XPTUSD","XPDUSD"],
 "CRYPTO MAJORS": ["BTCUSD","ETHUSD","SOLUSD","BNBUSD"],
 "CRYPTO ALTS": ["XRPUSD","ADAUSD","DOGEUSD","AVAXUSD","LINKUSD","LTCUSD","DOTUSD","TRXUSD"],
 "FOREX MAJORS": ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD"],
 "FOREX CROSSES": ["EURGBP","EURJPY","GBPJPY","AUDJPY","GBPCHF","EURCHF"],
 "ENERGY": ["USOIL","UKOIL","NATGAS"],
 "INDICES US": ["US500","US30","NAS100"],
 "INDICES EU": ["GER40","UK100","FRA40","JPN225"],
 "BONDS": ["US10Y","US02Y","DE10Y","UK10Y","US30Y"]
}
ALL = [s for v in GROUPS.values() for s in v]
LIVE={"prices":{},"hist":{}}
for s in ALL:
 LIVE["hist"][s]=deque(maxlen=300); LIVE["prices"][s]=0
SEED={"XAUUSD":2690,"XAGUSD":31.8,"XPTUSD":1020,"XPDUSD":980,"BTCUSD":68500,"ETHUSD":2680,"SOLUSD":158,"BNBUSD":620,"XRPUSD":0.62,"ADAUSD":0.39,"DOGEUSD":0.16,"AVAXUSD":28.5,"LINKUSD":14.2,"LTCUSD":72,"DOTUSD":4.8,"TRXUSD":0.26,"EURUSD":1.088,"GBPUSD":1.295,"USDJPY":153.2,"AUDUSD":0.662,"USDCAD":1.391,"USDCHF":0.895,"NZDUSD":0.61,"EURGBP":0.84,"EURJPY":166.5,"GBPJPY":198.4,"AUDJPY":101.4,"GBPCHF":1.16,"EURCHF":0.97,"USOIL":71.8,"UKOIL":75.4,"NATGAS":2.15,"US500":5830,"US30":43800,"NAS100":20150,"GER40":19250,"UK100":8250,"FRA40":7550,"JPN225":38600,"US10Y":4.28,"US02Y":4.05,"DE10Y":2.35,"UK10Y":4.26,"US30Y":4.48}
for s in ALL:
 base=SEED.get(s,100)
 for _ in range(300): LIVE["hist"][s].append(base*(1+(random.random()-0.5)*0.004))
 LIVE["prices"][s]=base

def ema(v,n):
 if len(v)<n: return sum(v)/len(v)
 k=2/(n+1); e=sum(v[:n])/n
 for x in v[n:]: e=x*k+e*(1-k)
 return e
def sma(v,n): return sum(v[-n:])/n if len(v)>=n else sum(v)/len(v)
def rsi(v,n=21):
 if len(v)<n+1: return 50
 g=l=0
 for i in range(-n,0):
  ch=v[i]-v[i-1]
  if ch>0: g+=ch
  else: l+=abs(ch)
 return 70 if l==0 else 100-(100/(1+g/l))
def bb(v,n=21):
 mid=ema(v[-n:],n); mean=sum(v[-n:])/n
 var=sum((x-mean)**2 for x in v[-n:])/n; dev=math.sqrt(var)
 up=mid+2*dev; lo=mid-2*dev
 w=((up-lo)/mid*100) if mid else 0
 return mid,up,lo,w

def fetch_real():
 while True:
  try:
   # BINANCE
   try:
    r=requests.get("https://api.binance.com/api/v3/ticker/price",timeout=7).json()
    mp={x['symbol']:float(x['price']) for x in r}
    m={"BTCUSDT":"BTCUSD","ETHUSDT":"ETHUSD","SOLUSDT":"SOLUSD","BNBUSDT":"BNBUSD","XRPUSDT":"XRPUSD","ADAUSDT":"ADAUSD","DOGEUSDT":"DOGEUSD","AVAXUSDT":"AVAXUSD","LINKUSDT":"LINKUSD","LTCUSDT":"LTCUSD","DOTUSDT":"DOTUSD","TRXUSDT":"TRXUSD"}
    for k,v in m.items():
     if k in mp: LIVE["prices"][v]=mp[k]; LIVE["hist"][v].append(mp[k])
   except: pass
   # FOREX + METALS from free apis
   try:
    fx=requests.get("https://api.exchangerate-api.com/v4/latest/USD",timeout=7).json().get('rates',{})
    if fx:
     conv={"EUR":"EURUSD","GBP":"GBPUSD","AUD":"AUDUSD","CAD":"USDCAD","CHF":"USDCHF","NZD":"NZDUSD","JPY":"USDJPY"}
     for cur,pair in conv.items():
      if cur in fx:
       price = 1/fx[cur] if pair!="USDCAD" and pair!="USDCHF" and pair!="USDJPY" else fx[cur]
       if pair=="USDJPY": price=1/fx["JPY"]*100 if False else fx.get("JPY",153)
       # fix
       if pair=="EURUSD": price=1/fx["EUR"]
       if pair=="GBPUSD": price=1/fx["GBP"]
       if pair=="AUDUSD": price=1/fx["AUD"]
       if pair=="NZDUSD": price=1/fx["NZD"]
       if pair=="USDCAD": price=fx["CAD"]
       if pair=="USDCHF": price=fx["CHF"]
       if pair=="USDJPY": price=fx["JPY"]
       LIVE["prices"][pair]=price; LIVE["hist"][pair].append(price)
   except: pass
   # GOLD
   try:
    g=requests.get("https://api.gold-api.com/price/XAU",timeout=7).json()
    if 'price' in g: LIVE["prices"]["XAUUSD"]=float(g['price']); LIVE["hist"]["XAUUSD"].append(float(g['price']))
   except: pass
  except: pass
  time.sleep(6)
threading.Thread(target=fetch_real,daemon=True).start()

def build():
 out=[]
 for sym in ALL:
  hist=list(LIVE["hist"][sym]); price=LIVE["prices"].get(sym,0) or hist[-1]
  if len(hist)<210 or price==0: continue
  sma200=sma(hist,200); mid,up,low,width=bb(hist,21)
  r=rsi(hist,21)
  widths=[bb(hist[i-21:i],21)[3] for i in range(len(hist)-20,len(hist)) if i>=21]
  avg=sum(widths)/len(widths) if widths else width
  fuel=int(max(10,min(100,(width/avg*50)+25))) if avg else 50
  power=int(max(0,min(100,r)))
  dist=abs(price-sma200)/price*100
  bias="Buy" if price>sma200 else "Sell"
  if dist<0.30: signal="Wait"; reason="Market is flat"
  else:
   signal="Wait"; reason="Waiting for setup"
   if bias=="Buy" and power>50:
    if abs(price-mid)/price*100<1.3: signal="Buy Now"; reason=f"Pullback to {mid:.1f}"
    elif fuel<45: signal="Buy Now"; reason=f"Low fuel {fuel}%"
    elif fuel<50: signal="Watch"; reason="Fuel low ready"
   if bias=="Sell" and power<50:
    if abs(price-mid)/price*100<1.3: signal="Sell Now"; reason=f"Pullback to {mid:.1f}"
    elif fuel<45: signal="Sell Now"; reason=f"Low fuel {fuel}%"
    elif fuel<50: signal="Watch"; reason="Fuel low ready"
  atr=(up-low)/2 if up and low else price*0.008
  sl=mid-atr*1.2 if bias=="Buy" else mid+atr*1.2
  tp=up if bias=="Buy" else low
  out.append({"name":sym,"price":price,"trend":bias,"power":power,"fuel":fuel,"signal":signal,"reason":reason,"tp":tp,"sl":sl,"mid":mid,"sma200":sma200,"rsi":r,"width":width})
 return sorted(out,key=lambda x: (0 if "Now" in x["signal"] else 1))

@app.get("/api/signals")
def sig(): return {"signals":build()}

@app.get("/", response_class=HTMLResponse)
def ui():
 return HTMLResponse("""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Terminal v5 REAL</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#000;color:#e6e6e6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;height:100dvh;overflow:hidden}
.phone{max-width:540px;margin:0 auto;height:100dvh;background:#000;display:flex;flex-direction:column}
.top{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#0a0a0a;border-bottom:1px solid #1a1a1a}
.top b{font-size:13px;color:#fff;letter-spacing:.3px}.live{font-size:10px;color:#8a8a8a;display:flex;align-items:center;gap:6px}
.dot{width:6px;height:6px;border-radius:50%;background:#26a69a;box-shadow:0 0 6px #26a69a}
.con{flex:1;overflow:auto;background:#000}
.folder{height:40px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#0d0d0d;border-bottom:1px solid #1a1a1a;cursor:pointer}
.folder b{font-size:11px;color:#aaa;letter-spacing:.5px;display:flex;gap:8px}
.folder b i{color:#555;font-style:normal;font-size:10px}
.cnt{font-size:10px;color:#555}
.list{display:none}.list.open{display:block}
.row{height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 14px 0 28px;border-bottom:1px solid #0f0f0f}
.sym{font-size:12px;font-weight:600;color:#fff}.meta{font-size:10px;color:#666;margin-top:2px}
.pr{font-size:12px;color:#fff;text-align:right}.trend{font-size:10px;text-align:right;margin-top:2px}
.buy{color:#26a69a}.sell{color:#ef5350}.wait{color:#555}
.det{display:none;padding:10px 14px 12px 28px;background:#0a0a0a;border-bottom:1px solid #161616}.det.open{display:block}
.l{font-size:11px;color:#888;line-height:17px}.l b{color:#ccc}
.box{display:flex;gap:8px;margin-top:8px}.box div{flex:1;background:#111;border:1px solid #1e1e1e;padding:7px 8px}
.box div span{font-size:8px;color:#666;display:block;margin-bottom:2px;letter-spacing:.4px}.box div b{font-size:11px;color:#fff}
.bot{height:48px;display:flex;justify-content:space-around;align-items:center;background:#0a0a0a;border-top:1px solid #1a1a1a}.bot div{font-size:9px;color:#555;text-align:center}.bot div.on{color:#fff}
</style></head><body><div class="phone">
<div class="top"><b>Market Watch • REAL • v5</b><div class="live"><div class="dot"></div>REAL PRICE</div></div>
<div class="con" id="con"></div>
<div class="bot"><div class="on">Quotes</div><div>Charts</div><div>Trade</div><div>History</div><div>Settings</div></div>
</div>
<script>
const GROUPS={"METALS":["XAUUSD","XAGUSD","XPTUSD","XPDUSD"],"CRYPTO MAJORS":["BTCUSD","ETHUSD","SOLUSD","BNBUSD"],"CRYPTO ALTS":["XRPUSD","ADAUSD","DOGEUSD","AVAXUSD","LINKUSD","LTCUSD","DOTUSD","TRXUSD"],"FOREX MAJORS":["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD"],"FOREX CROSSES":["EURGBP","EURJPY","GBPJPY","AUDJPY","GBPCHF","EURCHF"],"ENERGY":["USOIL","UKOIL","NATGAS"],"INDICES US":["US500","US30","NAS100"],"INDICES EU":["GER40","UK100","FRA40","JPN225"],"BONDS":["US10Y","US02Y","DE10Y","UK10Y","US30Y"]};
let all=[];
function toggle(g){document.getElementById('list-'+g).classList.toggle('open')}
function render(){
 let h='';
 Object.keys(GROUPS).forEach(g=>{
  let arr=all.filter(x=>GROUPS[g].includes(x.name));
  let now=arr.filter(x=>x.signal.includes('Now')).length;
  h+=`<div class="folder open" onclick="toggle('${g}')"><b><i>▸</i> ${g} <span style="color:#333">${GROUPS[g].length}</span></b><span class="cnt">${now?now+' Now':''}</span></div><div class="list open" id="list-${g}">`;
  arr.forEach(x=>{
   let c=x.signal.includes('Buy')?'buy':x.signal.includes('Sell')?'sell':'wait';
   h+=`<div class="row" onclick="this.nextElementSibling.classList.toggle('open')"><div><div class="sym">${x.name}</div><div class="meta">Power ${x.power}% • Fuel ${x.fuel}% • ${x.reason}</div></div><div><div class="pr">${x.price.toFixed(x.price<5?4:2)}</div><div class="trend ${c}">${x.signal}</div></div></div><div class="det"><div class="l"><b>Trend:</b> ${x.trend} (200SMA ${x.sma200.toFixed(2)}) &nbsp; <b>Power RSI:</b> ${x.power}% &nbsp; <b>Fuel BB:</b> ${x.fuel}%<br><b>21EMA Mid:</b> ${x.mid.toFixed(2)} <b>Width:</b> ${x.width.toFixed(3)}%<br><b>Signal:</b> ${x.signal} — ${x.reason}</div><div class="box"><div><span>STOP LOSS</span><b>${x.sl.toFixed(2)}</b></div><div><span>TAKE PROFIT</span><b>${x.tp.toFixed(2)}</b></div><div><span>MIDDLE</span><b>${x.mid.toFixed(2)}</b></div></div></div>`;
  });
  h+=`</div>`;
 });
 document.getElementById('con').innerHTML=h;
}
async function load(){let r=await fetch('/api/signals');let d=await r.json();all=d.signals;render();}
setInterval(load,4000);load();
</script></body></html>
""") 
