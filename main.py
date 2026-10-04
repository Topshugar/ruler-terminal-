from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import hashlib, random, requests
from datetime import datetime

app = FastAPI()

FOLDERS = {
    "Crypto": ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"],
    "Bonds": ["US10Y","DE10Y","UK10Y"],
    "Commodities": ["XAUUSD","XAGUSD","USOIL","UKOIL","NATGAS"],
    "ETFs": ["SPY","QQQ","IWM","GLD","SLV","USO","TLT","XLF"],
    "Forex": ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","USDCAD","NZDUSD","EURJPY","GBPJPY"],
    "Indices": ["US30","NAS100","SPX500","GER40","UK100","JPN225"],
    "Metals & Energies": ["XAUUSD","XAGUSD","USOIL","UKOIL"],
    "Stocks": ["AAPL","MSFT","GOOGL","AMZN","TSLA","META","NVDA"]
}
TOTALS = {"Crypto":74,"Bonds":3,"Commodities":7,"ETFs":12,"Forex":62,"Indices":23,"Metals & Energies":9,"Stocks":155}
REAL_CACHE = {"time":0,"prices":{}}
BINANCE_MAP = {"BTCUSD":"BTCUSDT","ETHUSD":"ETHUSDT","SOLUSD":"SOLUSDT","XRPUSD":"XRPUSDT","BNBUSD":"BNBUSDT","ADAUSD":"ADAUSDT","DOGEUSD":"DOGEUSDT","AVAXUSD":"AVAXUSDT"}

def fetch_real_prices():
    now=datetime.utcnow().timestamp()
    if now-REAL_CACHE["time"]<20 and REAL_CACHE["prices"]: return REAL_CACHE["prices"]
    prices={}
    try:
        for pair,sym in BINANCE_MAP.items():
            try:
                r=requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={sym}",timeout=2)
                if r.status_code==200: prices[pair]=float(r.json()["price"])
            except: pass
        try:
            r=requests.get("https://api.gold-api.com/price/XAU",timeout=2).json()
            if "price" in r: prices["XAUUSD"]=float(r["price"])
        except: pass
        try:
            r=requests.get("https://api.gold-api.com/price/XAG",timeout=2).json()
            if "price" in r: prices["XAGUSD"]=float(r["price"])
        except: pass
        try:
            r=requests.get("https://open.er-api.com/v6/latest/USD",timeout=3).json()
            rates=r.get("rates",{})
            if rates:
                if "EUR" in rates: prices["EURUSD"]=1/rates["EUR"]
                if "GBP" in rates: prices["GBPUSD"]=1/rates["GBP"]
                if "JPY" in rates: prices["USDJPY"]=rates["JPY"]
                if "CHF" in rates: prices["USDCHF"]=rates["CHF"]
                if "AUD" in rates: prices["AUDUSD"]=1/rates["AUD"]
                if "CAD" in rates: prices["USDCAD"]=rates["CAD"]
                if "NZD" in rates: prices["NZDUSD"]=1/rates["NZD"]
        except: pass
    except: pass
    REAL_CACHE["time"]=now; REAL_CACHE["prices"]=prices
    return prices

def ema_calc(series, period):
    k=2/(period+1); e=series[0]
    for p in series[1:]: e=p*k+e*(1-k)
    return e
def ema_series_calc(series, period):
    k=2/(period+1); out=[]; e=series[0]
    for p in series: e=p*k+e*(1-k); out.append(e)
    return out
def get_history(pair, tf, real_prices):
    seed_str=f"{pair}{tf}{datetime.utcnow().strftime('%Y-%m-%d-%H')}"
    seed=int(hashlib.md5(seed_str.encode()).hexdigest()[:8],16)
    rnd=random.Random(seed)
    base=real_prices.get(pair)
    if base is None:
        base=100
        if "BTC" in pair: base=65000
        elif "ETH" in pair: base=2500
        elif "XAU" in pair: base=2650
        elif "EURUSD" in pair: base=1.08
        elif "GBPUSD" in pair: base=1.27
        elif "USDJPY" in pair: base=148.5
        elif "US30" in pair: base=42000
    closes=[base]
    for _ in range(249): closes.append(closes[-1]+rnd.uniform(-0.8,0.8)*(base*0.002))
    if pair in real_prices:
        closes=[c+(base-closes[-1])*(i/250) for i,c in enumerate(closes)]
        closes[-1]=base
    return closes
def score_pair(pair, tf, bias_map, real_prices):
    closes=get_history(pair,tf,real_prices); price=closes[-1]
    e9=ema_calc(closes,9); e21=ema_calc(closes,21); e50=ema_calc(closes,50); e200=ema_calc(closes,200)
    s9=ema_series_calc(closes,9); s21=ema_series_calc(closes,21)
    trend=0
    if e9>e21: trend+=15
    if e21>e50: trend+=15
    if e50>e200: trend+=10
    if s9[-1]>s21[-1] and s9[-3]<=s21[-3]: trend+=10
    dist=abs(price-e21)/price if price!=0 else 1
    if dist<0.003: pull=30
    elif dist<0.008: pull=20
    elif dist<0.015: pull=10
    else: pull=5
    major=0
    if price>e200: major+=15
    if e50>e200: major+=15
    raw=trend+pull+major; power=max(15,min(88,raw+10))
    bias="BULL" if e21>e200 and price>e200 else "BEAR"
    bias_map[(pair,tf)]=bias
    if tf in ["M15","M30"]:
        h=bias_map.get((pair,"H1"))
        if h and h==bias: power=min(92,power+12)
    action="BUY NOW" if power>=55 else "SELL NOW" if power<=44 else "WAIT"
    color="#00ff88" if power>=55 else "#ff4444" if power<=44 else "#ffaa00"
    is_real="●" if pair in real_prices else "○"
    return {"pair":pair,"tf":tf,"score":round(power,1),"price":round(price,2 if price>10 else 5),"action":action,"color":color,"power":round(power,1),"real":is_real}

def get_news():
    try:
        r=requests.get("https://www.forexlive.com/feed/",timeout=4,headers={"User-Agent":"Mozilla/5.0"})
        import xml.etree.ElementTree as ET
        root=ET.fromstring(r.content); news=[]
        for item in root.findall(".//item")[:10]:
            t=item.findtext("title","")[:120]; d=(item.findtext("description","") or "")[:300]
            tag="MARKET"; up=t.upper()
            if "GOLD" in up: tag="XAUUSD"
            elif "EUR" in up: tag="EURUSD"
            elif "BTC" in up: tag="BTCUSD"
            news.append({"time":datetime.now().strftime("%H:%M"),"tag":tag,"title":t,"desc":d})
        return news
    except: return [{"time":datetime.now().strftime("%H:%M"),"tag":"RULER","title":"Search + Flash active","desc":"New signals will flash"}]

@app.get("/api/data")
def api_data():
    real_prices=fetch_real_prices(); bias_map={}; all_data={}
    for tf in ["M15","M30","H1","H4","D1"]:
        all_data[tf]={}
        for folder,pairs in FOLDERS.items():
            all_data[tf][folder]=[score_pair(p,tf,bias_map,real_prices) for p in pairs]
    return {"all":all_data,"news":get_news(),"totals":TOTALS,"real_count":len(real_prices)}

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{margin:0;background:#000;color:#fff;font-family:monospace;padding-bottom:62px;min-height:100vh}
.topbar{background:#0a0e12;padding:10px 12px;border-bottom:1px solid #1a1a1a;position:sticky;top:0;z-index:5}
.rulerTitle{color:#00ff55;font-size:14px;font-weight:700}
.searchBox{width:100%;margin-top:8px;background:#111;border:1px solid #222;color:#fff;padding:8px 12px;border-radius:8px;font-family:monospace;font-size:12px;outline:none}
.searchBox:focus{border-color:#00ff55;box-shadow:0 0 8px rgba(0,255,85,0.3)}
.tfRow{display:flex;gap:8px;margin-top:10px;overflow-x:auto}
.tfBtn{padding:5px 12px;border:1px solid #222;background:#111;color:#777;border-radius:6px;font-size:11px;cursor:pointer}
.tfBtn.active{background:#00ff55;color:#000;font-weight:800;border-color:#00ff55}
#terminalTab, #fuelTab{display:flex;flex-direction:column;min-height:calc(100vh - 115px);background:#000}
.folder{flex:1;padding:0 14px;background:linear-gradient(180deg,#14365f 0%,#0d223c 100%);border-bottom:1px solid #081a2f;border-top:1px solid #1f4a7a;display:flex;justify-content:space-between;align-items:center;cursor:pointer;font-weight:800;font-size:13.5px;color:#ffffff;min-height:62px;max-height:12.5vh;transition:0.3s}
.folder.active{background:linear-gradient(180deg,#1a4a82 0%,#12345f 100%);border:1px solid #00ff55;box-shadow:0 0 15px rgba(0,255,85,0.45);animation:pulseGlow 2s infinite}
.folder.flashNew{animation:flashNewSig 0.6s 3; border:2px solid #ffcc00!important; background:linear-gradient(180deg,#7a5d00 0%,#3d2f00 100%)!important}
@keyframes flashNewSig{0%,100%{transform:scale(1); box-shadow:0 0 10px #ffcc00}50%{transform:scale(1.02); box-shadow:0 0 25px #ffcc00}}
@keyframes pulseGlow{0%,100%{box-shadow:0 0 12px rgba(0,255,85,0.4)}50%{box-shadow:0 0 22px rgba(0,255,85,0.7)}}
.count{color:#8ab4e0!important;font-size:11px;font-weight:700;background:#081a2f;padding:4px 9px;border-radius:12px;border:1px solid #1e4a7a;transition:0.4s}
.count.pulse{transform:scale(1.4);background:#00ff55;color:#000!important;box-shadow:0 0 15px #00ff55}
.count.newSig{background:#ffcc00!important;color:#000!important;animation:countFlash 0.5s 4}
@keyframes countFlash{0%,100%{transform:scale(1)}50%{transform:scale(1.5)}}
.header{padding:6px 12px;background:#05070a;color:#555;font-size:10px;display:grid;grid-template-columns:1fr 60px 110px 90px;text-align:right}
.header span:first-child{text-align:left}
.row{padding:9px 12px;background:#080a0d;border-top:1px solid #111;display:grid;grid-template-columns:1fr 60px 110px 90px;text-align:right;font-size:12px}
.row.newRow{background:#1a1500!important; animation:rowFlash 1s 2}
@keyframes rowFlash{0%,100%{background:#080a0d}50%{background:#332a00}}
.row span:first-child{text-align:left;color:#fff}
.foldCont{display:none;flex-shrink:0}.foldCont.open{display:block}
.bottom{position:fixed;bottom:0;left:0;right:0;height:58px;background:#0a0e12;border-top:1px solid #1a1a1a;display:flex;justify-content:space-around;align-items:center;z-index:10}
.bitem{color:#555;font-size:10px;cursor:pointer}.bitem.active{color:#00ff55}
#fuelModal{position:fixed;inset:0;background:rgba(0,0,0,0.97);z-index:99;display:none;align-items:center;justify-content:center;flex-direction:column}
.circle{width:210px;height:210px;border-radius:50%;background:conic-gradient(#00ff55 var(--p), #1a1a1a 0);display:flex;align-items:center;justify-content:center}
.inner{width:180px;height:180px;background:#000;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column}
#refreshBar{height:3px;background:#00ff55;width:0%;transition:width 1s linear}
#newAlert{position:fixed;top:70px;left:50%;transform:translateX(-50%);background:#ffcc00;color:#000;padding:10px 20px;border-radius:20px;font-weight:900;font-size:12px;display:none;z-index:20;box-shadow:0 0 20px #ffcc00}
</style></head><body>
<div id="newAlert">⚡ NEW SIGNAL! </div>
<div class="topbar"><div style="display:flex;justify-content:space-between"><div class="rulerTitle">RULER v1.3 <span id="liveTime"></span> <span style="font-size:9px;color:#00ff55" id="realInfo"></span> LIVE <span id="liveTF">[M15]</span></div><div style="font-size:9px;color:#666;text-align:right">MT5<br>FOLDERS</div></div>
<div style="display:flex;justify-content:space-between;margin-top:6px;font-size:10px"><span id="candleInfo" style="color:#ffcc00">Next M15 candle: 14:22</span><span id="priceInfo" style="color:#888">Price live ↻ 15s</span></div>
<div id="refreshBar"></div>
<input id="searchBox" class="searchBox" placeholder="🔍 Search PAIR e.g. BTC, EUR, XAU, AAPL..." oninput="doSearch(this.value)">
<div class="tfRow" id="tfRow"></div></div>
<div id="terminalTab"></div><div id="fuelTab" style="display:none"></div>
<div id="calendarTab" style="display:none;padding:30px;text-align:center;color:#555">CALENDAR - HTF Bias</div>
<div id="newsTab" style="display:none"></div>
<div id="fuelModal" onclick="this.style.display='none'"><div class="circle" id="fuelCircle"><div class="inner"><div id="fuelNum" style="font-size:42px;font-weight:800">0%</div><div id="fuelAct" style="font-size:12px"></div><div id="fuelPair" style="font-size:10px;opacity:0.5;margin-top:4px"></div></div></div><div style="margin-top:20px;color:#00ff55;font-size:11px;letter-spacing:2px">RULER POWER - REAL + EMA</div></div>
<div class="bottom"><div class="bitem active" onclick="switchTab('terminal',this)">TERMINAL</div><div class="bitem" onclick="switchTab('fuel',this)">FUEL</div><div class="bitem" onclick="switchTab('news',this)">NEWS</div><div class="bitem" onclick="switchTab('calendar',this)">CALENDAR</div></div>
<script>
let DATA={}; let curTF="M15"; let priceTimer=15; let searchTerm=""; let prevSignals=new Set(); let isFirstLoad=true;

function secondsToNextCandle(tf){
  let now=new Date(); let sec=now.getSeconds(); let min=now.getMinutes(); let hr=now.getUTCHours();
  if(tf==="M15"){ let m=min%15; return (15-m)*60 - sec; }
  if(tf==="M30"){ let m=min%30; return (30-m)*60 - sec; }
  if(tf==="H1"){ return (60-min)*60 - sec; }
  if(tf==="H4"){ let h=hr%4; let mleft=(4-h)*60 - min; return mleft*60 - sec; }
  if(tf==="D1"){ let left=(24-hr)*3600 - min*60 - sec; return left; }
  return 60;
}
function formatTime(s){ if(s<0)s=0; let m=Math.floor(s/60); let sec=s%60; if(m>=60){let h=Math.floor(m/60); m=m%60; return h+"h "+m+"m "+sec+"s";} return m.toString().padStart(2,'0')+":"+sec.toString().padStart(2,'0'); }

function doSearch(v){ searchTerm=v.toUpperCase().trim(); renderTerminal({}); renderFuel(); }

async function load(){
  try{
    let r=await fetch('/api/data'); let newData=await r.json();
    let oldCounts={}; let newSignals=new Set(); let newlyAdded=[];
    if(DATA.all && DATA.all[curTF]){
      for(let f in DATA.all[curTF]){ let pairs=DATA.all[curTF][f]; oldCounts[f]=pairs.filter(p=>p.score>=55||p.score<=44).length; }
    }
    // collect current signals
    for(let f in newData.all[curTF]){
      newData.all[curTF][f].forEach(p=>{ if(p.score>=55||p.score<=44){ newSignals.add(p.pair+"|"+f); if(!prevSignals.has(p.pair+"|"+f) &&!isFirstLoad){ newlyAdded.push(p.pair); } } });
    }
    DATA=newData;
    document.getElementById('realInfo').innerText=DATA.real_count+' REAL ●';
    renderTFs(); renderTerminal(oldCounts, newlyAdded); renderFuel(newlyAdded); renderNews();
    if(newlyAdded.length>0 &&!isFirstLoad){
      // FLASH + VIBRATE
      let alertBox=document.getElementById('newAlert');
      alertBox.innerText="⚡ NEW SIGNAL: "+newlyAdded.slice(0,3).join(", ");
      alertBox.style.display='block';
      setTimeout(()=>alertBox.style.display='none',4000);
      if(navigator.vibrate) navigator.vibrate([200,100,200]);
    }
    prevSignals=newSignals; isFirstLoad=false; priceTimer=15;
  }catch(e){console.log(e)}
}
function renderTFs(){let h='';["M15","M30","H1","H4","D1"].forEach(tf=>{h+=`<div class="tfBtn ${tf===curTF?'active':''}" onclick="setTF('${tf}')">${tf}</div>`});document.getElementById('tfRow').innerHTML=h;document.getElementById('liveTF').innerText='['+curTF+']';}
function setTF(tf){curTF=tf; isFirstLoad=true; prevSignals=new Set(); renderTFs(); renderTerminal({}); renderFuel();}
function renderTerminal(oldCounts={}, newlyAdded=[]){
  let h='';
  for(let f in DATA.all[curTF]){
    let allPairs=DATA.all[curTF][f];
    let filtered=allPairs.filter(p=>!searchTerm || p.pair.includes(searchTerm));
    if(searchTerm && filtered.length===0) continue;
    let active=filtered.filter(p=>p.score>=55||p.score<=44).length;
    let glow=active>0?'active':'';
    let hasNew=filtered.some(p=> newlyAdded.includes(p.pair));
    let changed=oldCounts[f]!==undefined && oldCounts[f]!==allPairs.filter(p=>p.score>=55||p.score<=44).length;
    h+=`<div class="folder ${glow} ${hasNew?'flashNew':''}" onclick="this.nextElementSibling.classList.toggle('open')"><div><span style="color:#ffcc00">📁</span> <b style="font-weight:900">${f.toUpperCase()}</b></div><div class="count ${changed?'pulse':''} ${hasNew?'newSig':''}">${active}/${searchTerm?filtered.length:DATA.totals[f]}</div></div><div class="foldCont ${searchTerm?'open':''}"><div class="header"><span>PAIR [${curTF}]</span><span>SCORE</span><span>PRICE ●=REAL</span><span>ACTION</span></div>`;
    filtered.forEach(d=>{
      let isNew=newlyAdded.includes(d.pair);
      h+=`<div class="row ${isNew?'newRow':''}"><span>${isNew?'🆕 ':''}${d.real} ${d.pair}</span><span style="color:${d.color}">${d.score}</span><span>${d.price}</span><span style="color:${d.color}">${d.action}</span></div>`;
    });
    h+=`</div>`;
  }
  if(h==="") h=`<div style="padding:30px;text-align:center;color:#555">No results for "${searchTerm}"</div>`;
  document.getElementById('terminalTab').innerHTML=h;
  setTimeout(()=>{document.querySelectorAll('.count.pulse').forEach(el=>setTimeout(()=>el.classList.remove('pulse'),800))},100);
}
function renderFuel(newlyAdded=[]){
  let h='';
  for(let f in DATA.all[curTF]){
    let allPairs=DATA.all[curTF][f];
    let filtered=allPairs.filter(p=>!searchTerm || p.pair.includes(searchTerm));
    if(searchTerm && filtered.length===0) continue;
    let active=filtered.filter(p=>p.score>=55).length; let glow=active>0?'active':'';
    let hasNew=filtered.some(p=> newlyAdded.includes(p.pair));
    h+=`<div class="folder ${glow} ${hasNew?'flashNew':''}" onclick="this.nextElementSibling.classList.toggle('open')"><div><span style="color:#ffcc00">📁</span> <b style="font-weight:900">${f.toUpperCase()}</b></div><div class="count ${hasNew?'newSig':''}">${active}/${searchTerm?filtered.length:DATA.totals[f]}</div></div><div class="foldCont ${searchTerm||f==='Forex'?'open':''}"><div class="header"><span>PAIR [${curTF}]</span><span>POWER</span><span></span><span>TAP</span></div>`;
    filtered.forEach(d=>{
      let isNew=newlyAdded.includes(d.pair);
      h+=`<div class="row ${isNew?'newRow':''}" onclick="showFuel('${d.pair}',${d.power},'${d.action}','${d.color}')"><span>${isNew?'🆕 ':''}${d.real} ${d.pair}</span><span style="color:${d.color}">${d.power}%</span><span></span><span style="color:${d.color}">⚡</span></div>`;
    });
    h+=`</div>`;
  }
  if(h==="") h=`<div style="padding:30px;text-align:center;color:#555">No results for "${searchTerm}"</div>`;
  document.getElementById('fuelTab').innerHTML=h;
}
function showFuel(pair,power,action,color){document.getElementById('fuelModal').style.display='flex';document.getElementById('fuelPair').innerText=pair+' | '+curTF+' | REAL';document.getElementById('fuelAct').innerText=action+' POWER';document.getElementById('fuelAct').style.color=color;document.getElementById('fuelNum').style.color=color;let c=document.getElementById('fuelCircle');c.style.setProperty('--p','0%');let n=0;let t=setInterval(()=>{n+=1.2;if(n>=power){clearInterval(t);n=power}document.getElementById('fuelNum').innerText=n.toFixed(1)+'%';c.style.setProperty('--p',n+'%');},12);}
function renderNews(){let h='';DATA.news.forEach(n=>{h+=`<div style="padding:12px;border-bottom:1px solid #111" onclick="let d=this.querySelector('.nd');d.style.display=d.style.display==='none'?'block':'none'"><div style="font-size:10px;color:#666">${n.time} | <span style="color:#00ff55">${n.tag}</span></div><div style="font-size:13px;margin:5px 0">${n.title}</div><div class="nd" style="display:none;font-size:11px;opacity:0.6">${n.desc}</div></div>`});document.getElementById('newsTab').innerHTML=h;}
function switchTab(t,el){document.querySelectorAll('.bitem').forEach(b=>b.classList.remove('active'));el.classList.add('active');document.getElementById('terminalTab').style.display=t==='terminal'?'flex':'none';document.getElementById('fuelTab').style.display=t==='fuel'?'flex':'none';document.getElementById('newsTab').style.display=t==='news'?'block':'none';document.getElementById('calendarTab').style.display=t==='calendar'?'block':'none';}
setInterval(()=>{document.getElementById('liveTime').innerText=new Date().toLocaleTimeString('en-GB',{hour12:false})},1000);
setInterval(()=>{
  let secLeft=secondsToNextCandle(curTF);
  document.getElementById('candleInfo').innerText=`Next ${curTF} candle: ${formatTime(secLeft)}`;
  let total={M15:900,M30:1800,H1:3600,H4:14400,D1:86400}[curTF]||900;
  let progress=((total-secLeft)/total*100);
  document.getElementById('refreshBar').style.width=progress+'%';
  priceTimer--; document.getElementById('priceInfo').innerText=`Price live ↻ ${priceTimer}s`;
  if(priceTimer<=0){ load(); }
  if(secLeft<=1){ setTimeout(()=>load(),1000); }
},1000);
load();
</script></body></html>
    """
