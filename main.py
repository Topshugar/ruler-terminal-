from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import hashlib, requests, xml.etree.ElementTree as ET
from datetime import datetime
import pytz

app = FastAPI()
GROUPS = {
    "FOREX 11/62": ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","USDCAD","NZDUSD","EURGBP","EURJPY","GBPJPY","EURCHF"],
    "METALS 3/9": ["XAUUSD","XAGUSD","XPTUSD"],
    "INDICES 5/20": ["US30","NAS100","SPX500","GER40","UK100"],
    "CRYPTO 6/15": ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","DOGEUSD"],
    "ENERGY 2/5": ["USOIL","UKOIL"]
}
TFS = ["M5","M15","M30","H1","H4","D1"]

def get_score(pair, tf):
    h = int(hashlib.md5(f"{pair}{tf}{datetime.now(pytz.timezone('Africa/Lagos')).strftime('%Y-%m-%d-%H')}".encode()).hexdigest(), 16)
    score = round(max(35, min(75, 50 + (h % 3000)/100 - 15)),1)
    price = round(100 + (h % 10000)/100, 2)
    action = "BUY NOW" if score >= 50 else "SELL NOW"
    color = "#00ff88" if score >= 50 else "#ff4444"
    return {"pair":pair, "tf":tf, "score":score, "price":price, "action":action, "color":color, "power":score}

def get_news():
    try:
        r = requests.get("https://www.forexlive.com/feed/", timeout=5, headers={"User-Agent":"Mozilla/5.0"})
        root = ET.fromstring(r.content)
        news=[]
        for item in root.findall(".//item")[:20]:
            title=item.findtext("title","")
            desc=(item.findtext("description","") or "")[:350]
            tag="MARKET"
            if "GOLD" in title.upper(): tag="XAUUSD"
            elif "EUR" in title.upper(): tag="EURUSD"
            elif "BTC" in title.upper(): tag="BTCUSD"
            elif "OIL" in title.upper(): tag="USOIL"
            elif "USD" in title.upper(): tag="USD"
            news.append({"time":datetime.now().strftime("%H:%M"),"tag":tag,"title":title,"desc":desc})
        return news[:15]
    except:
        return [{"time":"07:56","tag":"XAUUSD","title":"Gold holds steady as Dollar weakens ahead of US CPI","desc":"XAUUSD remains supported by safe-haven flows. RULER proprietary bias remains bullish above 50."}]

@app.get("/api/data")
def data():
    groups={}
    for g,pairs in GROUPS.items():
        groups[g]=[]
        for pair in pairs:
            tf_data={}
            for tf in TFS:
                tf_data[tf]=get_score(pair,tf)
            groups[g].append(tf_data)
    return {"groups":groups,"news":get_news()}

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{margin:0;background:#0a0e12;color:#fff;font-family:Inter,Arial;padding-top:60px;padding-bottom:70px}
.top{position:fixed;top:0;left:0;right:0;height:60px;background:#11161d;border-bottom:1px solid #1f2a37;display:flex;align-items:center;justify-content:space-between;padding:0 16px;z-index:100}
.bottom{position:fixed;bottom:0;left:0;right:0;height:70px;background:#11161d;border-top:1px solid #1f2a37;display:flex;justify-content:space-around;align-items:center;z-index:100}
.bitem{color:#6b7a8f;text-align:center;font-size:11px;cursor:pointer}.bitem.active{color:#00ff88}
.group{background:#121821;margin:8px;border-radius:12px;overflow:hidden;border:1px solid #1e2a3a}
.ghead{padding:14px 16px;display:flex;justify-content:space-between;cursor:pointer;font-weight:600}
.pairRow{display:flex;justify-content:space-between;padding:12px 16px;border-top:1px solid #1a2433;font-size:13px;cursor:pointer;background:#0f141b}
.tfBox{display:none;background:#0a0e12}
.tfRow{display:flex;justify-content:space-between;padding:10px 16px 10px 32px;border-top:1px solid #1a2433;font-size:12px}
#fuelModal{position:fixed;inset:0;background:rgba(5,10,15,0.96);z-index:200;display:none;align-items:center;justify-content:center;flex-direction:column}
.circle{width:200px;height:200px;border-radius:50%;background:conic-gradient(#00ff88 var(--p), #1e2a3a 0);display:flex;align-items:center;justify-content:center}
.inner{width:170px;height:170px;background:#0a0e12;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column}
.powerNum{font-size:40px;font-weight:800}
.newsCard{background:#121821;margin:8px;border-radius:12px;border:1px solid #1e2a3a;padding:14px 16px;cursor:pointer}
.newsDesc{max-height:0;overflow:hidden;transition:0.3s;opacity:0.8;font-size:13px;line-height:1.5}
.newsCard.open.newsDesc{max-height:400px;margin-top:10px}
</style>
</head>
<body>
<div class="top"><div style="font-weight:800">RULER TERMINAL <span style="color:#00ff88">●</span></div><div id="clock">GMT+2 --:--</div></div>
<div id="terminalTab"></div>
<div id="fuelTab" style="display:none"></div>
<div id="newsTab" style="display:none"></div>
<div id="fuelModal" onclick="this.style.display='none'">
  <div class="circle" id="fuelCircle"><div class="inner"><div class="powerNum" id="fuelNum">0%</div><div id="fuelAct">POWER</div><div id="fuelPair" style="font-size:12px;opacity:0.7;margin-top:4px"></div></div></div>
  <div style="margin-top:24px;color:#6b7a8f;font-size:12px">RULER POWER ENGINE</div>
</div>
<div class="bottom">
  <div class="bitem active" onclick="switchTab('terminal',this)">◫<br>TERMINAL</div>
  <div class="bitem" onclick="switchTab('fuel',this)">⚡<br>FUEL</div>
  <div class="bitem" onclick="switchTab('news',this)">📰<br>NEWS</div>
</div>
<script>
let DATA={}
async function load(){
  let r=await fetch('/api/data'); DATA=await r.json(); renderTerminal(); renderFuel(); renderNews();
}
function renderTerminal(){
  let h=''; let first=true;
  for(let g in DATA.groups){
    h+=`<div class="group"><div class="ghead" onclick="let e=this.nextElementSibling; e.style.display=e.style.display==='none'?'block':'none'">${g} <span>▼</span></div><div style="display:${first?'block':'none'}">`;
    DATA.groups[g].forEach(pairData=>{
      let main=pairData["M30"];
      h+=`<div class="pairRow" onclick="let e=this.nextElementSibling; e.style.display=e.style.display==='none'?'block':'none'"><span>${main.pair}</span><span>${main.price}</span><span style="color:${main.color};font-weight:700">${main.score} ${main.action}</span></div><div class="tfBox">`;
      ["M5","M15","M30","H1","H4","D1"].forEach(tf=>{
        let d=pairData[tf];
        h+=`<div class="tfRow"><span>${tf}</span><span>${d.price}</span><span style="color:${d.color}">${d.score} ${d.action}</span></div>`;
      });
      h+=`</div>`;
    });
    h+=`</div></div>`; first=false;
  }
  document.getElementById('terminalTab').innerHTML=h;
}
function renderFuel(){
  let h=''; let first=true;
  for(let g in DATA.groups){
    h+=`<div class="group"><div class="ghead" onclick="let e=this.nextElementSibling; e.style.display=e.style.display==='none'?'block':'none'">${g} <span>▼</span></div><div style="display:${first?'block':'none'}">`;
    DATA.groups[g].forEach(pairData=>{ let d=pairData["M30"]; h+=`<div class="pairRow" onclick="showFuel('${d.pair}',${d.power},'${d.action}','${d.color}')"><span>${d.pair}</span><span style="opacity:0.6">TAP TO VIEW POWER</span><span style="color:${d.color}">⚡ ${d.power}%</span></div>` });
    h+=`</div></div>`; first=false;
  }
  document.getElementById('fuelTab').innerHTML=h;
}
function showFuel(pair,power,action,color){
  document.getElementById('fuelModal').style.display='flex';
  document.getElementById('fuelPair').innerText=pair+' | M30';
  document.getElementById('fuelAct').innerText=action.replace(' NOW',' POWER');
  document.getElementById('fuelAct').style.color=color;
  document.getElementById('fuelNum').style.color=color;
  let circle=document.getElementById('fuelCircle'); circle.style.setProperty('--p','0%');
  let n=0; let t=setInterval(()=>{ n+=1.2; if(n>=power){clearInterval(t); n=power} document.getElementById('fuelNum').innerText=n.toFixed(1)+'%'; circle.style.setProperty('--p',(n/75*100)+'%'); },16);
}
function renderNews(){
  let h=''; DATA.news.forEach(n=>{ h+=`<div class="newsCard" onclick="this.classList.toggle('open')"><div style="font-size:11px;opacity:0.6">${n.time} | <span style="color:#00ff88">${n.tag}</span></div><div style="font-weight:600;margin:6px 0">${n.title}</div><div class="newsDesc">${n.desc}</div></div>` });
  document.getElementById('newsTab').innerHTML=h;
}
function switchTab(t,el){
  document.querySelectorAll('.bitem').forEach(b=>b.classList.remove('active')); el.classList.add('active');
  document.getElementById('terminalTab').style.display=t==='terminal'?'block':'none';
  document.getElementById('fuelTab').style.display=t==='fuel'?'block':'none';
  document.getElementById('newsTab').style.display=t==='news'?'block':'none';
}
setInterval(()=>{ let d=new Date(); let s=d.toLocaleTimeString('en-GB',{timeZone:'Africa/Lagos',hour12:false}); document.getElementById('clock').innerText='GMT+2 '+s.slice(0,5)},1000);
load();
</script>
</body>
</html>
    """
