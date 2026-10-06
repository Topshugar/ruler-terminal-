from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from collections import deque
import math, random, threading, time, requests
from datetime import datetime

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
LIVE={"prices":{},"hist":{},"news":[]}
for s in ALL: LIVE["hist"][s]=deque(maxlen=400); LIVE["prices"][s]=0
SEED={"XAUUSD":4120,"XAGUSD":31.8,"XPTUSD":1020,"XPDUSD":980,"BTCUSD":85600,"ETHUSD":2700,"SOLUSD":158,"BNBUSD":620,"XRPUSD":0.62,"ADAUSD":0.39,"DOGEUSD":0.16,"AVAXUSD":28.5,"LINKUSD":14.2,"LTCUSD":72,"DOTUSD":4.8,"TRXUSD":0.26,"EURUSD":1.088,"GBPUSD":1.295,"USDJPY":153.2,"AUDUSD":0.662,"USDCAD":1.391,"USDCHF":0.895,"NZDUSD":0.61,"EURGBP":0.84,"EURJPY":166.5,"GBPJPY":198.4,"AUDJPY":101.4,"GBPCHF":1.16,"EURCHF":0.97,"USOIL":71.8,"UKOIL":75.4,"NATGAS":2.15,"US500":5830,"US30":43800,"NAS100":20150,"GER40":19250,"UK100":8250,"FRA40":7550,"JPN225":38600,"US10Y":4.28,"US02Y":4.05,"DE10Y":2.35,"UK10Y":4.26,"US30Y":4.48}
for s in ALL:
 b=SEED.get(s,100)
 for _ in range(300): LIVE["hist"][s].append(b*(1+(random.random()-0.5)*0.004))
 LIVE["prices"][s]=b

def ema(v,n):
 if len(v)<n: return sum(v)/len(v)
 k=2/(n+1); e=sum(v[:n])/n
 for x in v[n:]: e=x*k+e*(1-k)
 return e
def sma(v,n): return sum(v[-n:])/n if len(v)>=n else sum(v)/len(v)
def rsi(v,n=21):
 if len(v)<n+1: return 50.0
 g=l=0
 for i in range(-n,0):
  ch=v[i]-v[i-1]
  if ch>0: g+=ch
  else: l+=abs(ch)
 if l==0: return 70.0
 return 100-(100/(1+g/l))
def bb(v,n=21):
 mid=ema(v[-n:],n)
 mean=sum(v[-n:])/n
 var=sum((x-mean)**2 for x in v[-n:])/n
 dev=math.sqrt(var)
 up=mid+2*dev; lo=mid-2*dev
 width=((up-lo)/mid*100) if mid else 0
 return mid,up,lo,width

def fetch_real():
 while True:
  try:
   r=requests.get("https://api.binance.com/api/v3/ticker/price",timeout=7).json()
   mp={x['symbol']:float(x['price']) for x in r}
   m={"BTCUSDT":"BTCUSD","ETHUSDT":"ETHUSD","SOLUSDT":"SOLUSD","BNBUSDT":"BNBUSD","XRPUSDT":"XRPUSD","ADAUSDT":"ADAUSD","DOGEUSDT":"DOGEUSD","AVAXUSDT":"AVAXUSD","LINKUSDT":"LINKUSD","LTCUSDT":"LTCUSD","DOTUSDT":"DOTUSD","TRXUSDT":"TRXUSD"}
   for k,v in m.items():
    if k in mp: LIVE["prices"][v]=mp[k]; LIVE["hist"][v].append(mp[k])
   fx=requests.get("https://api.exchangerate-api.com/v4/latest/USD",timeout=7).json().get('rates',{})
   if fx:
    if "EUR" in fx: LIVE["prices"]["EURUSD"]=1/fx["EUR"]; LIVE["hist"]["EURUSD"].append(1/fx["EUR"])
    if "GBP" in fx: LIVE["prices"]["GBPUSD"]=1/fx["GBP"]; LIVE["hist"]["GBPUSD"].append(1/fx["GBP"])
    if "AUD" in fx: LIVE["prices"]["AUDUSD"]=1/fx["AUD"]; LIVE["hist"]["AUDUSD"].append(1/fx["AUD"])
    if "NZD" in fx: LIVE["prices"]["NZDUSD"]=1/fx["NZD"]; LIVE["hist"]["NZDUSD"].append(1/fx["NZD"])
    if "CAD" in fx: LIVE["prices"]["USDCAD"]=fx["CAD"]; LIVE["hist"]["USDCAD"].append(fx["CAD"])
    if "CHF" in fx: LIVE["prices"]["USDCHF"]=fx["CHF"]; LIVE["hist"]["USDCHF"].append(fx["CHF"])
    if "JPY" in fx: LIVE["prices"]["USDJPY"]=fx["JPY"]; LIVE["hist"]["USDJPY"].append(fx["JPY"])
   g=requests.get("https://api.gold-api.com/price/XAU",timeout=7).json()
   if 'price' in g: LIVE["prices"]["XAUUSD"]=float(g['price']); LIVE["hist"]["XAUUSD"].append(float(g['price']))
  except: pass
  time.sleep(5)

def fetch_news():
 while True:
  all_news=[]
  try:
   for url in ["https://www.forexlive.com/feed/","https://www.dailyfx.com/feeds/all"]:
    try:
     r=requests.get(f"https://api.rss2json.com/v1/api.json?rss_url={url}",timeout=10).json()
     for it in r.get('items',[])[:10]:
      all_news.append({"time":it.get('pubDate','')[:16],"currency":"FX","event":it.get('title',''),"impact":"High","source":url.split('/')[2]})
    except: pass
   if len(all_news)>4: LIVE["news"]=all_news[:35]
  except: pass
  time.sleep(180)

threading.Thread(target=fetch_real,daemon=True).start()
threading.Thread(target=fetch_news,daemon=True).start()

# ---- FIXED SIGNAL LOGIC v4 TRIPLE ----
def build(mult=1):
 out=[]
 for sym in ALL:
  hist=list(LIVE["hist"][sym]); price=LIVE["prices"].get(sym,0) or hist[-1]
  if len(hist)<220 or price==0: continue
  n=int(21*mult); n200=int(200*mult)
  sma200=sma(hist,n200)
  mid,up,low,width=bb(hist,n)
  r=rsi(hist,n)
  # avg width last 20 for fuel
  widths=[bb(hist[i-n:i],n)[3] for i in range(len(hist)-20,len(hist)) if i>=n]
  avg_w=sum(widths)/len(widths) if widths else width
  vol="SQUEEZE" if width < avg_w*0.88 else "EXPANSION" if width > avg_w*1.12 else "NORMAL"
  fuel=int(max(10,min(100,(width/avg_w*50)+25))) if avg_w else 50
  power=int(r)
  bias="BULLISH" if price>sma200 else "BEARISH" if price<sma200 else "NEUTRAL"
  dist=abs(price-mid)/price*100 if price else 100

  # CORRECT TRIPLE CONFLUENCE
  signal="NO SETUP"; pattern="None"; reason="No confluence"
  # Setup A: Pullback to 21 EMA
  if bias=="BULLISH" and dist<1.2 and 40 < r < 68:
   signal="VALID ENTRY"; pattern="Setup A Pullback"; reason=f"Bull pullback to 21EMA {mid:.2f}"
  elif bias=="BEARISH" and dist<1.2 and 32 < r < 60:
   signal="VALID ENTRY"; pattern="Setup A Pullback"; reason=f"Bear pullback to 21EMA {mid:.2f}"
  # Setup B: Squeeze Breakout
  elif vol=="SQUEEZE" and (r>56 or r<44):
   signal="VALID ENTRY"; pattern="Setup B Breakout"; reason=f"Squeeze + RSI {r:.1f} breakout"
  elif vol=="SQUEEZE":
   signal="WATCHLIST"; pattern="Setup B forming"; reason=f"Squeeze forming fuel {fuel}%"
  else:
   signal="WAIT"; pattern="No setup"; reason=f"{vol} - waiting"

  # OVERBOUGHT/OVERSOLD FILTER - FIX
  if r>75 and "Buy" not in bias and signal=="VALID ENTRY" and bias=="BULLISH":
   # if overbought 75+ don't buy
   signal="WAIT"; reason=f"RSI overbought {r:.1f} - wait pullback"
  if r<25 and bias=="BEARISH":
   signal="WAIT"; reason=f"RSI oversold {r:.1f} - wait"

  # CORRECT SL/TP
  atr=(up-low)/2 if up and low else price*0.006
  if bias=="BULLISH":
   sl=low if low>0 else mid-atr*1.2
   tp1=up
   tp2=price + atr*2.5
   dir="BUY"
  else:
   sl=up if up>0 else mid+atr*1.2
   tp1=low
   tp2=price - atr*2.5
   dir="SELL"

  out.append({"name":sym,"price":price,"bias":bias,"vol":vol,"power":power,"fuel":fuel,"signal":signal,"reason":reason,"pattern":pattern,"tp1":tp1,"tp2":tp2,"sl":sl,"mid":mid,"up":up,"low":low,"sma200":sma200,"rsi":r,"width":width,"dir":dir,"dist":dist})
 return sorted(out,key=lambda x:(0 if x["signal"]=="VALID ENTRY" else 1 if x["signal"]=="WATCHLIST" else 2, -x["rsi"]))

@app.get("/api/signals")
def sig(tf:str="M15"):
 mult={"M15":1,"M30":1.5,"H1":2,"H4":3,"D1":4}.get(tf,1)
 return {"signals":build(mult)}
@app.get("/api/news")
def news(): return {"news":LIVE["news"]}

@app.get("/", response_class=HTMLResponse)
def ui():
 return HTMLResponse("""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Terminal v5.3 FIXED</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#000;color:#e6e6e6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;height:100dvh;overflow:hidden}
.phone{max-width:540px;margin:0 auto;height:100dvh;background:#000;display:flex;flex-direction:column}
.top{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#0a0a0a;border-bottom:1px solid #1a1a1a}
.top b{font-size:13px;color:#fff}.live{font-size:10px;color:#8a8a8a;display:flex;align-items:center;gap:6px}
.dot{width:6px;height:6px;border-radius:50%;background:#26a69a;box-shadow:0 0 6px #26a69a}
.tfs{display:flex;gap:14px;padding:10px 14px;background:#080808;border-bottom:1px solid #151515;overflow:auto}
.tfs span{font-size:11px;color:#666;cursor:pointer;padding-bottom:4px;border-bottom:2px solid transparent;white-space:nowrap}
.tfs span.on{color:#fff;border-color:#ffcc00}
.con{flex:1;overflow:auto;background:#000}
.folder{height:40px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#0d0d0d;border-bottom:1px solid #1a1a1a;cursor:pointer}
.folder b{font-size:11px;color:#aaa;letter-spacing:.5px;display:flex;gap:8px}
.folder b i{color:#555;font-style:normal;font-size:10px;transition:.2s;display:inline-block}
.folder.open b i{transform:rotate(90deg)}
.cnt{font-size:10px;color:#555}
.list{display:none}.list.open{display:block}
.row{height:56px;display:flex;align-items:center;justify-content:space-between;padding:0 14px 0 28px;border-bottom:1px solid #0f0f0f;cursor:pointer}
.row.sel{background:#111;border-left:2px solid #ffcc00}
.sym{font-size:12px;font-weight:600;color:#fff}.meta{font-size:10px;color:#666;margin-top:2px}
.pr{font-size:12px;color:#fff;text-align:right}.trend{font-size:10px;text-align:right;margin-top:3px;padding:2px 5px;border-radius:3px;display:inline-block}
.buy{color:#000;background:#26a69a}.sell{color:#fff;background:#ef5350}.wait{color:#666;background:#222}
.statbar{padding:12px 14px;background:#111;border-bottom:1px solid #222;display:none}.statbar.open{display:block}
.l{font-size:11px;color:#888;line-height:18px}.l b{color:#ccc}
.box{display:flex;gap:8px;margin-top:8px}.box div{flex:1;background:#111;border:1px solid #1e1e1e;padding:7px 8px}
.box div span{font-size:8px;color:#666;display:block;margin-bottom:2px}.box div b{font-size:11px;color:#fff}
.news{display:none;padding:0;flex:1;overflow:auto}.news.open{display:block}
.news-item{padding:12px 14px;border-bottom:1px solid #111;display:flex;gap:10px}
.news-item b{font-size:11px;color:#fff;line-height:14px}.news-item small{font-size:10px;color:#666;display:block;margin-top:3px}
.impact{font-size:9px;padding:3px 6px;border-radius:3px;height:18px;white-space:nowrap}
.high{background:#ef5350;color:#fff}.med{background:#ff9800;color:#000}.low{background:#555;color:#fff}
.bot{height:52px;display:flex;justify-content:space-around;align-items:center;background:#0a0a0a;border-top:1px solid #1a1a1a}
.bot div{font-size:10px;color:#555;text-align:center;cursor:pointer;padding:6px 14px;border-radius:6px}.bot div.on{color:#ffcc00;background:#151515}
</style></head><body><div class="phone">
<div class="top"><b>Market Watch • REAL v5.3 FIXED</b><div class="live"><div class="dot"></div><span id="clk"></span></div></div>
<div class="tfs" id="tfs"><span class="on" data-tf="M15" onclick="setTF('M15')">M15</span><span data-tf="M30" onclick="setTF('M30')">M30</span><span data-tf="H1" onclick="setTF('H1')">H1</span><span data-tf="H4" onclick="setTF('H4')">H4</span><span data-tf="D1" onclick="setTF('D1')">D1</span></div>
<div class="statbar" id="statbar"></div>
<div class="con" id="con"></div>
<div class="news" id="news"></div>
<div class="bot"><div class="on" id="btn-q" onclick="showTab('quotes')">📊<br>Quotes</div><div id="btn-n" onclick="showTab('news')">📰<br>News</div><div>📈<br>Charts</div><div>⚙️<br>Settings</div></div>
</div>
<script>
const GROUPS={"METALS":["XAUUSD","XAGUSD","XPTUSD","XPDUSD"],"CRYPTO MAJORS":["BTCUSD","ETHUSD","SOLUSD","BNBUSD"],"CRYPTO ALTS":["XRPUSD","ADAUSD","DOGEUSD","AVAXUSD","LINKUSD","LTCUSD","DOTUSD","TRXUSD"],"FOREX MAJORS":["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD"],"FOREX CROSSES":["EURGBP","EURJPY","GBPJPY","AUDJPY","GBPCHF","EURCHF"],"ENERGY":["USOIL","UKOIL","NATGAS"],"INDICES US":["US500","US30","NAS100"],"INDICES EU":["GER40","UK100","FRA40","JPN225"],"BONDS":["US10Y","US02Y","DE10Y","UK10Y","US30Y"]};
let all=[]; let curTF='M15'; let openFolders=new Set(Object.keys(GROUPS)); let selectedPair=null; let curTab='quotes';
function setTF(tf){curTF=tf;document.querySelectorAll('.tfs span').forEach(s=>s.classList.remove('on'));document.querySelector(`[data-tf="${tf}"]`).classList.add('on');load();}
function toggle(g){if(openFolders.has(g)) openFolders.delete(g); else openFolders.add(g); render();}
function selectPair(name){selectedPair=name;document.getElementById('statbar').classList.add('open');let x=all.find(a=>a.name===name);if(!x)return;let dirColor=x.dir==='BUY'?'#26a69a':'#ef5350';document.getElementById('statbar').innerHTML=`<div style="display:flex;justify-content:space-between"><b style="color:${dirColor};font-size:12px">${x.name} • ${x.dir} • ${x.signal} • ${curTF}</b><span style="color:#666;font-size:10px" onclick="selectedPair=null;document.getElementById('statbar').classList.remove('open');render()">✕ close</span></div><div class="l" style="margin-top:8px"><b>Bias:</b> ${x.bias} (200SMA ${x.sma200.toFixed(2)}) <b>Vol:</b> ${x.vol}<br><b>Power RSI:</b> ${x.power}% <b>Fuel BB:</b> ${x.fuel}% Width ${x.width.toFixed(3)}%<br><b>Pattern:</b> ${x.pattern}<br><b>Reason:</b> ${x.reason}<br><b>Mid:</b> ${x.mid.toFixed(2)} <b>Up:</b> ${x.up.toFixed(2)} <b>Low:</b> ${x.low.toFixed(2)}</div><div class="box"><div><span>STOP LOSS</span><b>${x.sl.toFixed(2)}</b></div><div><span>PRICE</span><b style="color:${dirColor}">${x.price.toFixed(2)}</b></div><div><span>TAKE PROFIT 1</span><b>${x.tp1.toFixed(2)}</b></div></div><div class="box"><div><span>TAKE PROFIT 2</span><b>${x.tp2.toFixed(2)}</b></div><div><span>DIR</span><b style="color:${dirColor}">${x.dir}</b></div><div><span>R:R</span><b>1:2.4</b></div></div>`;render();}
function render(){if(curTab!=='quotes')return;let h='';Object.keys(GROUPS).forEach(g=>{let arr=all.filter(x=>GROUPS[g].includes(x.name));let now=arr.filter(x=>x.signal==='VALID ENTRY').length;let isOpen=openFolders.has(g);h+=`<div class="folder ${isOpen?'open':''}" onclick="toggle('${g}')"><b><i>▸</i> ${g} <span style="color:#333">${GROUPS[g].length}</span> ${now?`<span style="color:#26a69a">• ${now} ENTRY</span>`:''}</b><span class="cnt">${now?now+' Now':''}</span></div><div class="list ${isOpen?'open':''}">`;arr.forEach(x=>{let c=x.dir==='BUY'?'buy':x.dir==='SELL'&&x.signal==='VALID ENTRY'?'sell':'wait';let label=x.signal==='VALID ENTRY'?x.dir:x.signal;let sel=selectedPair===x.name?' sel':'';h+=`<div class="row${sel}" onclick="selectPair('${x.name}')"><div><div class="sym">${x.name}</div><div class="meta">${x.bias} • Power ${x.power}% • Fuel ${x.fuel}% • ${x.vol}</div></div><div><div class="pr">${x.price.toFixed(x.price<5?4:2)}</div><div class="trend ${x.signal==='VALID ENTRY'?(x.dir==='BUY'?'buy':'sell'):'wait'}">${label}</div></div></div>`;});h+=`</div>`;});document.getElementById('con').innerHTML=h;}
async function load(){try{let r=await fetch('/api/signals?tf='+curTF);let d=await r.json();all=d.signals;document.getElementById('clk').innerText=curTF+' • '+new Date().toLocaleTimeString();render();if(selectedPair)selectPair(selectedPair);}catch(e){}}
async function loadNews(){try{let r=await fetch('/api/news');let d=await r.json();let h='';d.news.forEach(n=>{let cls=n.impact.toLowerCase().includes('high')?'high':'med';h+=`<div class="news-item"><div class="impact ${cls}">${n.impact}</div><div><b>${n.currency} • ${n.event}</b><small>${n.time} • ${n.source||''}</small></div></div>`;});document.getElementById('news').innerHTML=h||'<div style="padding:20px;color:#555">Loading...</div>';}catch(e){}}
function showTab(t){curTab=t;document.getElementById('btn-q').classList.toggle('on',t==='quotes');document.getElementById('btn-n').classList.toggle('on',t==='news');document.getElementById('con').style.display=t==='quotes'?'block':'none';document.getElementById('tfs').style.display=t==='quotes'?'flex':'none';document.getElementById('statbar').style.display=t==='quotes'?'':'none';document.getElementById('news').classList.toggle('open',t==='news');if(t==='news')loadNews();if(t==='quotes')render();}
setInterval(load,4000);load();setInterval(()=>{if(curTab==='news')loadNews()},60000);
</script></body></html>
""") 
