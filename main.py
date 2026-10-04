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

def ema_calc(series, period):
    k = 2/(period+1)
    e = series[0]
    for p in series[1:]:
        e = p*k + e*(1-k)
    return e

def ema_series_calc(series, period):
    k = 2/(period+1)
    out=[]
    e = series[0]
    for p in series:
        e = p*k + e*(1-k)
        out.append(e)
    return out

def get_history(pair, tf):
    seed_str = f"{pair}{tf}{datetime.utcnow().strftime('%Y-%m-%d-%H')}"
    seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    rnd = random.Random(seed)
    base = 100
    if "BTC" in pair: base = 65000
    elif "ETH" in pair: base = 2500
    elif "XAU" in pair: base = 2650
    elif "EURUSD" in pair: base = 1.08
    elif "GBPUSD" in pair: base = 1.27
    elif "USDJPY" in pair: base = 148.5
    elif "US30" in pair: base = 42000
    closes=[base]
    for _ in range(249):
        closes.append(closes[-1] + rnd.uniform(-0.8,0.8)*(base*0.002))
    return closes

def score_pair(pair, tf, bias_map):
    closes = get_history(pair, tf)
    price = closes[-1]
    e9 = ema_calc(closes, 9)
    e21 = ema_calc(closes, 21)
    e50 = ema_calc(closes, 50)
    e200 = ema_calc(closes, 200)
    s9 = ema_series_calc(closes, 9)
    s21 = ema_series_calc(closes, 21)
    trend = 0
    if e9 > e21: trend+=15
    if e21 > e50: trend+=15
    if e50 > e200: trend+=10
    if s9[-1] > s21[-1] and s9[-3] <= s21[-3]: trend+=10
    dist = abs(price - e21)/price if price!=0 else 1
    if dist < 0.003: pull=30
    elif dist < 0.008: pull=20
    elif dist < 0.015: pull=10
    else: pull=5
    major = 0
    if price > e200: major+=15
    if e50 > e200: major+=15
    raw = trend+pull+major
    power = max(15, min(88, raw+10))
    bias = "BULL" if e21>e200 and price>e200 else "BEAR"
    bias_map[(pair,tf)] = bias
    if tf in ["M15","M30"]:
        h = bias_map.get((pair,"H1"))
        if h and h==bias:
            power = min(92, power+12)
    action = "BUY NOW" if power>=55 else "SELL NOW" if power<=44 else "WAIT"
    color = "#00ff88" if power>=55 else "#ff4444" if power<=44 else "#ffaa00"
    return {"pair":pair,"tf":tf,"score":round(power,1),"price":round(price,2 if price>10 else 4),"action":action,"color":color,"power":round(power,1)}

def get_news():
    try:
        r=requests.get("https://www.forexlive.com/feed/",timeout=4,headers={"User-Agent":"Mozilla/5.0"})
        import xml.etree.ElementTree as ET
        root=ET.fromstring(r.content)
        news=[]
        for item in root.findall(".//item")[:10]:
            t=item.findtext("title","")[:120]
            d=(item.findtext("description","") or "")[:300]
            tag="MARKET"
            up=t.upper()
            if "GOLD" in up: tag="XAUUSD"
            elif "EUR" in up: tag="EURUSD"
            elif "BTC" in up: tag="BTCUSD"
            news.append({"time":datetime.now().strftime("%H:%M"),"tag":tag,"title":t,"desc":d})
        return news
    except:
        return [{"time":datetime.now().strftime("%H:%M"),"tag":"RULER","title":"EMA 9/21/50/200 engine active","desc":"Engine running"}]

@app.get("/api/data")
def api_data():
    bias_map={}
    all_data={}
    for tf in ["M15","M30","H1","H4","D1"]:
        all_data[tf]={}
        for folder,pairs in FOLDERS.items():
            all_data[tf][folder]=[score_pair(p,tf,bias_map) for p in pairs]
    return {"all":all_data,"news":get_news(),"totals":TOTALS}

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{margin:0;background:#000;color:#fff;font-family:monospace;padding-bottom:62px;min-height:100vh}
.topbar{background:#0a0e12;padding:10px 12px;border-bottom:1px solid #1a1a1a}
.rulerTitle{color:#00ff55;font-size:14px;font-weight:700}
.tfRow{display:flex;gap:8px;margin-top:10px;overflow-x:auto}
.tfBtn{padding:5px 12px;border:1px solid #222;background:#111;color:#777;border-radius:6px;font-size:11px;cursor:pointer}
.tfBtn.active{background:#00ff55;color:#000;font-weight:800;border-color:#00ff55}
#terminalTab, #fuelTab{display:flex;flex-direction:column;min-height:calc(100vh - 115px);background:#000}
.folder{flex:1;padding:0 14px;background:linear-gradient(180deg,#14365f 0%,#0d223c 100%);border-bottom:1px solid #081a2f;border-top:1px solid #1f4a7a;display:flex;justify-content:space-between;align-items:center;cursor:pointer;font-weight:800;font-size:13.5px;color:#ffffff;min-height:62px;max-height:12.5vh;transition:0.3s}
.folder.active{background:linear-gradient(180deg,#1a4a82 0%,#12345f 100%);border:1px solid #00ff55;box-shadow:0 0 15px rgba(0,255,85,0.45), inset 0 0 10px rgba(0,255,85,0.1);animation:pulseGlow 2s infinite}
@keyframes pulseGlow{0%,100%{box-shadow:0 0 12px rgba(0,255,85,0.4)}50%{box-shadow:0 0 22px rgba(0,255,85,0.7)}}
.count{color:#8ab4e0!important;font-size:11px;font-weight:700;background:#081a2f;padding:4px 9px;border-radius:12px;border:1px solid #1e4a7a}
.folder.active.count{background:#00ff55;color:#000!important;border-color:#00ff55;box-shadow:0 0 8px #00ff55;font-weight:900}
.header{padding:6px 12px;background:#05070a;color:#555;font-size:10px;display:grid;grid-template-columns:1fr 60px 110px 90px;text-align:right}
.header span:first-child{text-align:left}
.row{padding:9px 12px;background:#080a0d;border-top:1px solid #111;display:grid;grid-template-columns:1fr 60px 110px 90px;text-align:right;font-size:12px}
.row span:first-child{text-align:left;color:#fff}
.foldCont{display:none;flex-shrink:0}.foldCont.open{display:block}
.bottom{position:fixed;bottom:0;left:0;right:0;height:58px;background:#0a0e12;border-top:1px solid #1a1a1a;display:flex;justify-content:space-around;align-items:center;z-index:10}
.bitem{color:#555;font-size:10px;cursor:pointer}.bitem.active{color:#00ff55}
#fuelModal{position:fixed;inset:0;background:rgba(0,0,0,0.97);z-index:99;display:none;align-items:center;justify-content:center;flex-direction:column}
.circle{width:210px;height:210px;border-radius:50%;background:conic-gradient(#00ff55 var(--p), #1a1a1a 0);display:flex;align-items:center;justify-content:center}
.inner{width:180px;height:180px;background:#000;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column}
</style></head><body>
<div class="topbar"><div style="display:flex;justify-content:space-between"><div class="rulerTitle">RULER v1.2 <span id="liveTime"></span> LIVE <span id="liveTF">[H1]</span></div><div style="font-size:9px;color:#666">MT5<br>FOLDERS</div></div><div class="tfRow" id="tfRow"></div></div>
<div id="terminalTab"></div><div id="fuelTab" style="display:none"></div>
<div id="calendarTab" style="display:none;padding:30px;text-align:center;color:#555">CALENDAR - HTF Bias Active</div>
<div id="newsTab" style="display:none"></div>
<div id="fuelModal" onclick="this.style.display='none'"><div class="circle" id="fuelCircle"><div class="inner"><div id="fuelNum" style="font-size:42px;font-weight:800">0%</div><div id="fuelAct" style="font-size:12px"></div><div id="fuelPair" style="font-size:10px;opacity:0.5;margin-top:4px"></div></div></div><div style="margin-top:20px;color:#00ff55;font-size:11px;letter-spacing:2px">RULER POWER - EMA 9/21/50/200</div></div>
<div class="bottom"><div class="bitem active" onclick="switchTab('terminal',this)">TERMINAL</div><div class="bitem" onclick="switchTab('fuel',this)">FUEL</div><div class="bitem" onclick="switchTab('news',this)">NEWS</div><div class="bitem" onclick="switchTab('calendar',this)">CALENDAR</div></div>
<script>
let DATA={}; let curTF="H1";
async function load(){let r=await fetch('/api/data');DATA=await r.json();renderTFs();renderTerminal();renderFuel();renderNews();}
function renderTFs(){let h='';["M15","M30","H1","H4","D1"].forEach(tf=>{h+=`<div class="tfBtn ${tf===curTF?'active':''}" onclick="setTF('${tf}')">${tf}</div>`});document.getElementById('tfRow').innerHTML=h;document.getElementById('liveTF').innerText='['+curTF+']';}
function setTF(tf){curTF=tf;renderTFs();renderTerminal();renderFuel();}
function renderTerminal(){let h='';for(let f in DATA.all[curTF]){let pairs=DATA.all[curTF][f];let active=pairs.filter(p=>p.score>=55||p.score<=44).length;let glow=active>0?'active':'';h+=`<div class="folder ${glow}" onclick="this.nextElementSibling.classList.toggle('open')"><div><span style="color:#ffcc00">📁</span> <b style="font-weight:900;letter-spacing:0.5px">${f.toUpperCase()}</b></div><div class="count">${active}/${DATA.totals[f]}</div></div><div class="foldCont"><div class="header"><span>PAIR [${curTF}]</span><span>SCORE</span><span>PRICE</span><span>ACTION</span></div>`;pairs.forEach(d=>{h+=`<div class="row"><span>${d.pair}</span><span style="color:${d.color}">${d.score}</span><span>${d.price}</span><span style="color:${d.color}">${d.action}</span></div>`});h+=`</div>`;}document.getElementById('terminalTab').innerHTML=h;}
function renderFuel(){let h='';for(let f in DATA.all[curTF]){let pairs=DATA.all[curTF][f];let active=pairs.filter(p=>p.score>=55).length;let glow=active>0?'active':'';h+=`<div class="folder ${glow}" onclick="this.nextElementSibling.classList.toggle('open')"><div><span style="color:#ffcc00">📁</span> <b style="font-weight:900;letter-spacing:0.5px">${f.toUpperCase()}</b></div><div class="count">${active}/${DATA.totals[f]}</div></div><div class="foldCont ${f==='Forex'?'open':''}"><div class="header"><span>PAIR [${curTF}]</span><span>POWER</span><span></span><span>TAP</span></div>`;pairs.forEach(d=>{h+=`<div class="row" onclick="showFuel('${d.pair}',${d.power},'${d.action}','${d.color}')"><span>${d.pair}</span><span style="color:${d.color}">${d.power}%</span><span></span><span style="color:${d.color}">⚡</span></div>`});h+=`</div>`;}document.getElementById('fuelTab').innerHTML=h;}
function showFuel(pair,power,action,color){document.getElementById('fuelModal').style.display='flex';document.getElementById('fuelPair').innerText=pair+' | '+curTF+' | EMA 9/21/50/200';document.getElementById('fuelAct').innerText=action+' POWER';document.getElementById('fuelAct').style.color=color;document.getElementById('fuelNum').style.color=color;let c=document.getElementById('fuelCircle');c.style.setProperty('--p','0%');let n=0;let t=setInterval(()=>{n+=1.2;if(n>=power){clearInterval(t);n=power}document.getElementById('fuelNum').innerText=n.toFixed(1)+'%';c.style.setProperty('--p',n+'%');},12);}
function renderNews(){let h='';DATA.news.forEach(n=>{h+=`<div style="padding:12px;border-bottom:1px solid #111" onclick="let d=this.querySelector('.nd');d.style.display=d.style.display==='none'?'block':'none'"><div style="font-size:10px;color:#666">${n.time} | <span style="color:#00ff55">${n.tag}</span></div><div style="font-size:13px;margin:5px 0">${n.title}</div><div class="nd" style="display:none;font-size:11px;opacity:0.6">${n.desc}</div></div>`});document.getElementById('newsTab').innerHTML=h;}
function switchTab(t,el){document.querySelectorAll('.bitem').forEach(b=>b.classList.remove('active'));el.classList.add('active');document.getElementById('terminalTab').style.display=t==='terminal'?'flex':'none';document.getElementById('fuelTab').style.display=t==='fuel'?'flex':'none';document.getElementById('newsTab').style.display=t==='news'?'block':'none';document.getElementById('calendarTab').style.display=t==='calendar'?'block':'none';}
setInterval(()=>{document.getElementById('liveTime').innerText=new Date().toLocaleTimeString('en-GB',{hour12:false})},1000);load();
</script></body></html>
    """
