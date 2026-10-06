from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from collections import deque
import math, random, threading, time, requests, hashlib

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
ALL=[s for v in GROUPS.values() for s in v]
LIVE={"prices":{},"hist":{},"news":[],"live":{},"prev":{}}
for s in ALL: LIVE["hist"][s]=deque(maxlen=3000); LIVE["prices"][s]=0; LIVE["live"][s]=False; LIVE["prev"][s]=0

# Seed with drift so trends exist
SEED={"XAUUSD":4129,"XAGUSD":48.5,"XPTUSD":1020,"XPDUSD":980,"BTCUSD":85600,"ETHUSD":2708,"SOLUSD":158,"BNBUSD":620,"XRPUSD":0.62,"ADAUSD":0.39,"DOGEUSD":0.16,"AVAXUSD":28.5,"LINKUSD":14.2,"LTCUSD":72,"DOTUSD":4.8,"TRXUSD":0.26,"EURUSD":1.088,"GBPUSD":1.295,"USDJPY":153.2,"AUDUSD":0.662,"USDCAD":1.391,"USDCHF":0.895,"NZDUSD":0.61,"EURGBP":0.84,"EURJPY":166.5,"GBPJPY":198.4,"AUDJPY":101.4,"GBPCHF":1.16,"EURCHF":0.97,"USOIL":71.8,"UKOIL":75.4,"NATGAS":2.15,"US500":5830,"US30":43800,"NAS100":20150,"GER40":19250,"UK100":8250,"FRA40":7550,"JPN225":38600,"US10Y":4.28,"US02Y":4.05,"DE10Y":2.35,"UK10Y":4.26,"US30Y":4.48}
for s in ALL:
 b=SEED.get(s,100)
 drift=(int(hashlib.md5(s.encode()).hexdigest()[0],16)-8)/10000 # -0.0008 to +0.0007 per bar trend
 for _ in range(2000):
  b = b*(1+drift+(random.random()-0.5)*0.003)
  LIVE["hist"][s].append(b)
 LIVE["prices"][s]=b

def ema(v,n):
 n=int(max(2,n))
 if len(v)<n: return sum(v)/len(v) if v else 0
 k=2/(n+1); e=sum(v[:n])/n
 for x in v[n:]: e=x*k+e*(1-k)
 return e
def sma(v,n):
 n=int(max(2,n))
 return sum(v[-n:])/n if len(v)>=n else sum(v)/len(v) if v else 0
def rsi(v,n=21):
 n=int(max(2,n))
 if len(v)<n+1: return 50.0
 g=l=0
 for i in range(-n,0):
  ch=v[i]-v[i-1]
  if ch>0: g+=ch
  else: l+=abs(ch)
 if l==0: return 70.0 if g>0 else 50.0
 rs=g/l
 return 100-(100/(1+rs))
def bb(v,n=21):
 n=int(max(2,n)); mid=ema(v[-n:],n); mean=sum(v[-n:])/n if len(v)>=n else mid; var=sum((x-mean)**2 for x in v[-n:])/n if len(v)>=n else 0; dev=math.sqrt(var); up=mid+2*dev; lo=mid-2*dev; width=((up-lo)/mid*100) if mid else 0
 return mid,up,lo,width

def resample(hist, factor):
 if factor<=1: return hist
 return hist[::factor]

def get_htf_trend_backend(hist, tf_name):
 factor=16 if tf_name=="H4" else 96 if tf_name=="D1" else 1
 rh=resample(hist, factor)
 if len(rh)<60: return "NEUTRAL",0,0,50,False,0
 fast=ema(rh,21); slow=ema(rh,50); r_val=rsi(rh,21)
 diff_pct=abs(fast-slow)/slow*100 if slow else 0
 if diff_pct < 0.01: bias="NEUTRAL"
 else: bias="BULLISH" if fast>slow else "BEARISH"
 rsi_ok=(bias=="BULLISH" and r_val>45) or (bias=="BEARISH" and r_val<55)
 if bias=="NEUTRAL": rsi_ok=False
 return bias,fast,slow,r_val,rsi_ok,diff_pct

def set_price(sym,val,live=True):
 try:
  val=float(val)
  if val>0:
   LIVE["prev"][sym]=LIVE["prices"].get(sym,val)
   LIVE["prices"][sym]=val; LIVE["hist"][sym].append(val)
   if live: LIVE["live"][sym]=True
 except: pass

def fetch_real():
 while True:
  try:
   r=requests.get("https://api.binance.com/api/v3/ticker/price",timeout=8).json()
   mp={x['symbol']:float(x['price']) for x in r}
   m={"BTCUSDT":"BTCUSD","ETHUSDT":"ETHUSD","SOLUSDT":"SOLUSD","BNBUSDT":"BNBUSD","XRPUSDT":"XRPUSD","ADAUSDT":"ADAUSD","DOGEUSDT":"DOGEUSD","AVAXUSDT":"AVAXUSD","LINKUSDT":"LINKUSD","LTCUSDT":"LTCUSD","DOTUSDT":"DOTUSD","TRXUSDT":"TRXUSD"}
   for k,v in m.items():
    if k in mp: set_price(v,mp[k],True)
  except: pass
  try:
   fx=requests.get("https://api.exchangerate-api.com/v4/latest/USD",timeout=8).json().get('rates',{})
   if fx:
    if "EUR" in fx: set_price("EURUSD",1/fx["EUR"],True)
    if "GBP" in fx: set_price("GBPUSD",1/fx["GBP"],True)
    if "AUD" in fx: set_price("AUDUSD",1/fx["AUD"],True)
    if "NZD" in fx: set_price("NZDUSD",1/fx["NZD"],True)
    if "CAD" in fx: set_price("USDCAD",fx["CAD"],True)
    if "CHF" in fx: set_price("USDCHF",fx["CHF"],True)
    if "JPY" in fx: set_price("USDJPY",fx["JPY"],True)
    eurusd=LIVE["prices"]["EURUSD"]; gbpusd=LIVE["prices"]["GBPUSD"]; usdjpy=LIVE["prices"]["USDJPY"]; audusd=LIVE["prices"]["AUDUSD"]; usdchf=LIVE["prices"]["USDCHF"]
    if eurusd and gbpusd: set_price("EURGBP",eurusd/gbpusd,True)
    if eurusd and usdjpy: set_price("EURJPY",eurusd*usdjpy,True)
    if gbpusd and usdjpy: set_price("GBPJPY",gbpusd*usdjpy,True)
    if audusd and usdjpy: set_price("AUDJPY",audusd*usdjpy,True)
    if gbpusd and usdchf: set_price("GBPCHF",gbpusd*usdchf,True)
    if eurusd and usdchf: set_price("EURCHF",eurusd*usdchf,True)
  except: pass
  time.sleep(5)

threading.Thread(target=fetch_real,daemon=True).start()
TF_MAP={"M1":0.2,"M5":0.5,"M15":1,"M30":1.8,"H1":3.5,"H4":12,"D1":48}

def build(tf="M15"):
 mult=TF_MAP.get(tf,1)
 out=[]
 for sym in ALL:
  hist=list(LIVE["hist"][sym]); price=LIVE["prices"].get(sym,0) or hist[-1]
  if len(hist)<800 or price==0: continue
  n=int(21*mult); n200=int(200*mult)
  sma200=sma(hist,n200); mid,up,low,width=bb(hist,n)
  rsi_period = 14 if tf in ["M1","M5","M15","M30"] else 21
  r=rsi(hist,rsi_period)
  widths=[bb(hist[i-n:i],n)[3] for i in range(len(hist)-30,len(hist)) if i>=n]; avg_w=sum(widths)/len(widths) if widths else width
  vol="SQUEEZE" if width < avg_w*0.88 else "EXPANSION" if width > avg_w*1.12 else "NORMAL"
  fuel=int(max(10,min(100,(width/avg_w*50)+25))) if avg_w else 50; power=int(r); bias="BULLISH" if price>sma200 else "BEARISH"; dist=abs(price-mid)/price*100 if price else 100

  h4_bias,h4_fast,h4_slow,h4_rsi,h4_rsi_ok,h4_dist = get_htf_trend_backend(hist, "H4")
  d1_bias,d1_fast,d1_slow,d1_rsi,d1_rsi_ok,d1_dist = get_htf_trend_backend(hist, "D1")
  ltf_rsi_ok = (bias=="BULLISH" and r>48) or (bias=="BEARISH" and r<52)

  if h4_bias=="NEUTRAL": htf_aligned=False
  elif d1_bias=="NEUTRAL": htf_aligned = h4_rsi_ok
  else: htf_aligned = (h4_bias==d1_bias) and h4_rsi_ok and d1_rsi_ok

  signal="WAIT"; pattern="No setup"; reason=f"{vol} - waiting"; htf_ok=False

  if bias=="BULLISH" and dist<1.5 and 38<r<70: signal="VALID ENTRY"; pattern="Setup A Pullback"; reason=f"Bull pullback to 21EMA"
  elif bias=="BEARISH" and dist<1.5 and 30<r<62: signal="VALID ENTRY"; pattern="Setup A Pullback"; reason=f"Bear pullback to 21EMA"
  elif vol=="SQUEEZE" and (r>54 or r<46): signal="VALID ENTRY"; pattern="Setup B Breakout"; reason=f"Squeeze RSI{rsi_period} {r:.1f}"

  if tf in ["M1","M5","M15","M30"]:
   if signal=="VALID ENTRY":
    if not htf_aligned:
     if bias==h4_bias and h4_rsi_ok:
      htf_ok=True
      reason+=f" + H4 ALIGNED {h4_bias}"
     else:
      signal="WAIT"; reason=f"HTF BLOCK H4 {h4_bias} vs D1 {d1_bias}"
    elif not ltf_rsi_ok:
     signal="WAIT"; reason=f"LTF RSI{rsi_period} {r:.0f} not confirming"
    else:
     htf_ok=True
  else:
   htf_ok=htf_aligned

  atr=(up-low)/2 if up and low else price*0.006
  if bias=="BULLISH": sl=low; tp1=up; tp2=price+atr*2.5; dir="BUY"
  else: sl=up; tp1=low; tp2=price-atr*2.5; dir="SELL"
  prev=LIVE["prev"].get(sym,price); tick="up" if price>prev else "down" if price<prev else "same"; is_live=LIVE["live"].get(sym,False)

  score=0
  if (bias=="BULLISH" and price>sma200*1.001) or (bias=="BEARISH" and price<sma200*0.999): score+=25
  else: score+=12
  if dist<0.3: score+=20
  elif dist<0.8: score+=14
  else: score+=6
  score+= 15 if 45<=r<=65 else 8
  score+= 20 if vol=="SQUEEZE" else 10
  score+= 12 if 45<=fuel<=70 else 5
  if htf_ok: score+=15
  elif bias==h4_bias: score+=5
  else: score-=5
  h=int(hashlib.md5((sym+tf).encode()).hexdigest()[:2],16)%7-3
  score+=h
  if signal!="VALID ENTRY": prob=52 + (score/100)*10
  else: prob=62 + (score/100)*18
  prob=max(52,min(78,int(prob)))

  out.append({"name":sym,"price":price,"bias":bias,"vol":vol,"power":power,"fuel":fuel,"signal":signal,"reason":reason,"pattern":pattern,"tp1":tp1,"tp2":tp2,"sl":sl,"mid":mid,"up":up,"low":low,"sma200":sma200,"rsi":r,"rsi_period":rsi_period,"width":width,"dir":dir,"tick":tick,"is_live":is_live,"prob":prob,"dist":dist,"h4_bias":h4_bias,"h4_rsi":h4_rsi,"d1_bias":d1_bias,"d1_rsi":d1_rsi,"htf_aligned":htf_aligned,"htf_ok":htf_ok,"h4_fast":h4_fast,"h4_slow":h4_slow,"d1_fast":d1_fast,"d1_slow":d1_slow})
 return sorted(out,key=lambda x:(0 if x["signal"]=="VALID ENTRY" else 1, -x["prob"]))

@app.get("/api/signals")
def sig(tf:str="M15"): return {"signals":build(tf)}
@app.get("/api/news")
def news(): return {"news":LIVE["news"]}

@app.get("/", response_class=HTMLResponse)
def ui():
 return HTMLResponse("""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>v5.65 FULL</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}body{background:#000;color:#e6e6e6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;height:100dvh;overflow:hidden}
.phone{max-width:540px;margin:0 auto;height:100dvh;background:#000;display:flex;flex-direction:column}
.top{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#0a0a0a;border-bottom:1px solid #1a1a1a}
.top b{font-size:13px;color:#fff}.live{font-size:10px;color:#8a8a8a}
.tfs{display:flex;gap:12px;padding:10px 14px;background:#080808;border-bottom:1px solid #151515;overflow:auto}
.tfs span{font-size:11px;color:#666;cursor:pointer;padding-bottom:4px;border-bottom:2px solid transparent;white-space:nowrap}
.tfs span.on{color:#fff;border-color:#ffcc00}
.con{flex:1;overflow:auto;background:#000}
.folder{height:40px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#0d0d0d;border-bottom:1px solid #1a1a1a}
.folder b{font-size:11px;color:#aaa}
.row{height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 14px 0 28px;border-bottom:1px solid #0f0f0f;cursor:pointer}
.sym{font-size:12px;font-weight:600;color:#fff;display:flex;gap:6px;align-items:center}
.ldot{width:6px;height:6px;border-radius:50%;display:inline-block}.ldot.live{background:#26a69a;box-shadow:0 0 5px #26a69a}.ldot.seed{background:#444}
.pr{font-size:12px;color:#fff;text-align:right}.trend{font-size:10px;padding:2px 5px;border-radius:3px;display:inline-block}
.buy{color:#000;background:#26a69a}.sell{color:#fff;background:#ef5350}.wait{color:#666;background:#222}
.prob{font-size:9px;background:#ffcc00;color:#000;padding:2px 4px;border-radius:3px;font-weight:700}
.bot{height:52px;display:flex;justify-content:space-around;align-items:center;background:#0a0a0a;border-top:1px solid #1a1a1a}
.bot div{font-size:10px;color:#555;text-align:center;padding:6px 14px;border-radius:6px}.bot div.on{color:#ffcc00;background:#151515}
</style></head><body><div class="phone">
<div class="top"><b>Market Watch • v5.65</b><span id="clk" style="font-size:10px;color:#666"></span></div>
<div class="tfs"><span data-tf="M1" onclick="setTF('M1')" class="on">M1</span><span data-tf="M5" onclick="setTF('M5')">M5</span><span data-tf="M15" onclick="setTF('M15')">M15</span><span data-tf="M30" onclick="setTF('M30')">M30</span><span data-tf="H1" onclick="setTF('H1')">H1</span><span data-tf="H4" onclick="setTF('H4')">H4</span><span data-tf="D1" onclick="setTF('D1')">D1</span></div>
<div class="con" id="con"></div>
<div class="bot"><div class="on">📊 Quotes</div><div>📰 News</div></div>
</div>
<script>
const GROUPS={"METALS":["XAUUSD","XAGUSD","XPTUSD","XPDUSD"],"CRYPTO MAJORS":["BTCUSD","ETHUSD","SOLUSD","BNBUSD"],"CRYPTO ALTS":["XRPUSD","ADAUSD","DOGEUSD","AVAXUSD","LINKUSD","LTCUSD","DOTUSD","TRXUSD"],"FOREX MAJORS":["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD"],"FOREX CROSSES":["EURGBP","EURJPY","GBPJPY","AUDJPY","GBPCHF","EURCHF"],"ENERGY":["USOIL","UKOIL","NATGAS"],"INDICES US":["US500","US30","NAS100"],"INDICES EU":["GER40","UK100","FRA40","JPN225"],"BONDS":["US10Y","US02Y","DE10Y","UK10Y","US30Y"]};
let all=[];let curTF='M1';
function setTF(tf){curTF=tf;document.querySelectorAll('.tfs span').forEach(s=>s.classList.remove('on'));document.querySelector(`[data-tf="${tf}"]`).classList.add('on');load();}
function render(){let h='';Object.keys(GROUPS).forEach(g=>{let arr=all.filter(x=>GROUPS[g].includes(x.name));let now=arr.filter(x=>x.signal==='VALID ENTRY').length;h+=`<div class="folder"><b>${g} ${now?`<span style="color:#26a69a">• ${now} ENTRY</span>`:''}</b><span style="font-size:10px;color:#555">${now?now+' Now':''}</span></div>`;arr.forEach(x=>{let label=x.signal==='VALID ENTRY'?x.dir:x.signal;h+=`<div class="row"><div><div class="sym"><span class="ldot ${x.is_live?'live':'seed'}"></span>${x.name} <span class="prob">${x.prob}%</span></div><div style="font-size:9px;color:#555">${x.bias}</div></div><div><div class="pr">${x.price.toFixed(x.price<5?4:2)}</div><div class="trend ${x.signal==='VALID ENTRY'?(x.dir==='BUY'?'buy':'sell'):'wait'}">${label}</div></div></div>`;});});document.getElementById('con').innerHTML=h;}
async function load(){try{let r=await fetch('/api/signals?tf='+curTF);let d=await r.json();all=d.signals;document.getElementById('clk').innerText=curTF+' • '+new Date().toLocaleTimeString()+' • '+all.filter(x=>x.signal==='VALID ENTRY').length+' VALID';render();}catch(e){}}
setInterval(load,4000);load();
</script></body></html>
""") 
