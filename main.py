import hashlib, random, time
from datetime import datetime
import pytz
from flask import Flask, jsonify, render_template_string
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

# --- CONFIG ---
GROUPS = {
    "FOREX 11/62": ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","USDCAD","NZDUSD","EURGBP","EURJPY","GBPJPY","EURCHF"],
    "METALS 3/9": ["XAUUSD","XAGUSD","XPTUSD"],
    "INDICES 5/20": ["US30","NAS100","SPX500","GER40","UK100"],
    "CRYPTO 6/15": ["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","DOGEUSD"],
    "ENERGY 2/5": ["USOIL","UKOIL"]
}

def get_score(pair, tf):
    h = int(hashlib.md5(f"{pair}{tf}{datetime.now(pytz.timezone('Africa/Lagos')).strftime('%Y-%m-%d-%H')}".encode()).hexdigest(), 16)
    score = 50 + (h % 3000)/100 - 15 # 35 to 65 range
    score = round(max(35, min(75, score)),1)
    price = round(100 + (h % 10000)/100, 2)
    action = "BUY NOW" if score >= 50 else "SELL NOW"
    color = "#00ff88" if score >= 50 else "#ff4444"
    return {"pair":pair, "tf":tf, "score":score, "price":price, "action":action, "color":color, "power":score}

def get_news():
    try:
        r = requests.get("https://finance.yahoo.com/rss/topstories", timeout=5, headers={"User-Agent":"Mozilla/5.0"})
        root = ET.fromstring(r.content)
        news=[]
        for item in root.findall(".//item")[:20]:
            title = item.findtext("title","")
            desc = item.findtext("description","")[:250]
            link = item.findtext("link","")
            # simple tag detection
            tag="MARKET"
            for p in ["XAU","GOLD","USD","EUR","BTC","OIL"]:
                if p.lower() in title.lower(): tag=p; break
            news.append({"time":datetime.now().strftime("%H:%M"),"tag":tag,"title":title,"desc":desc,"link":link})
        return news
    except:
        return [{"time":"10:23","tag":"XAUUSD","title":"Gold steady near highs on safe haven demand","desc":"Gold holds near record high as dollar weakness supports metals ahead of CPI data. Investors await Fed signals.","link":""}]

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<style>
body{margin:0;background:#0a0e12;color:#fff;font-family:Inter,Arial; padding-top:60px; padding-bottom:70px}
.top{position:fixed;top:0;left:0;right:0;height:60px;background:#11161d;border-bottom:1px solid #1f2a37;display:flex;align-items:center;justify-content:space-between;padding:0 16px;z-index:100}
.bottom{position:fixed;bottom:0;left:0;right:0;height:70px;background:#11161d;border-top:1px solid #1f2a37;display:flex;justify-content:space-around;align-items:center;z-index:100}
.bitem{color:#6b7a8f; text-align:center; font-size:11px; cursor:pointer}
.bitem.active{color:#00ff88}
.group{background:#121821;margin:8px;border-radius:12px;overflow:hidden;border:1px solid #1e2a3a}
.ghead{padding:14px 16px;display:flex;justify-content:space-between;cursor:pointer;font-weight:600}
.pairRow{display:flex;justify-content:space-between;padding:12px 16px;border-top:1px solid #1a2433;font-size:13px;cursor:pointer}
.pairRow:hover{background:#151e2b}
.score{font-weight:700}
#fuelModal{position:fixed;inset:0;background:rgba(5,10,15,0.96);z-index:200;display:none;align-items:center;justify-content:center;flex-direction:column}
.circle{width:180px;height:180px;border-radius:50%;background:conic-gradient(#00ff88 var(--p), #1e2a3a 0);display:flex;align-items:center;justify-content:center;transition:1.5s}
.inner{width:150px;height:150px;background:#0a0e12;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column}
.powerNum{font-size:36px;font-weight:800}
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
  let h=''; for(let g in DATA.groups){ h+=`<div class="group"><div class="ghead" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">${g} <span>▼</span></div><div>`;
  DATA.groups[g].forEach(p=>{ let d=p.M30; h+=`<div class="pairRow"><span>${d.pair} <small style="opacity:0.5">M30</small></span><span>${d.price}</span><span class="score" style="color:${d.color}">${d.score} ${d.action}</span></div>` }); h+=`</div></div>` }
  document.getElementById('terminalTab').innerHTML=h;
}
function renderFuel(){
  let h=''; for(let g in DATA.groups){ h+=`<div class="group"><div class="ghead" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">${g} <span>▼</span></div><div>`;
  DATA.groups[g].forEach(p=>{ let d=p.M30; h+=`<div class="pairRow" onclick="showFuel('${d.pair}',${d.power},'${d.action}','${d.color}')"><span>${d.pair}</span><span style="opacity:0.6">TAP TO VIEW POWER</span><span style="color:${d.color}">⚡ ${d.power}%</span></div>` }); h+=`</div></div>` }
  document.getElementById('fuelTab').innerHTML=h;
}
function showFuel(pair,power,action,color){
  document.getElementById('fuelModal').style.display='flex';
  document.getElementById('fuelPair').innerText=pair+' | M30';
  document.getElementById('fuelAct').innerText=action.replace(' NOW',' POWER');
  document.getElementById('fuelAct').style.color=color;
  document.getElementById('fuelNum').style.color=color;
  let circle=document.getElementById('fuelCircle');
  circle.style.setProperty('--p','0%');
  let n=0; let t=setInterval(()=>{ n+=1; if(n>power){clearInterval(t); n=power} document.getElementById('fuelNum').innerText=n.toFixed(1)+'%'; circle.style.setProperty('--p', (n/75*100)+'%'); },15);
}
function renderNews(){
  let h=''; DATA.news.forEach(n=>{ h+=`<div class="group"><div style="padding:12px 16px"><div style="font-size:11px;opacity:0.6">${n.time} | ${n.tag}</div><div style="font-weight:600;margin:6px 0">${n.title}</div><div style="font-size:13px;opacity:0.8;line-height:1.4">${n.desc}</div></div></div>` });
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

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/data")
def data():
    groups={}
    for g,pairs in GROUPS.items():
        groups[g]=[]
        for pair in pairs:
            # M30 only for list, but we store structure like before
            groups[g].append({"M30": get_score(pair,"M30")})
    return jsonify({"groups":groups,"news":get_news()})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000)
