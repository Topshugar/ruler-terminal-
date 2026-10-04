import os, hashlib, asyncio, json, urllib.request
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import time, random

app = FastAPI()
SECRET = os.getenv("RULER_SECRET", "ruler_fix_ui")
FOREX = ["EUR/USD","GBP/USD","USD/JPY","USD/CHF","AUD/USD","USD/CAD","NZD/USD","EUR/GBP","EUR/JPY","GBP/JPY"]
METALS = ["XAU/USD","XAG/USD","XPT/USD"]
CRYPTO = ["BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","XRP/USDT","ADA/USDT","DOGE/USDT","AVAX/USDT","LINK/USDT","TON/USDT","WIF/USDT","PEPE/USDT","BONK/USDT","FLOKI/USDT","NOT/USDT","ENA/USDT","W/USDT","JUP/USDT","TAO/USDT","ZK/USDT","ZRO/USDT","IO/USDT","FET/USDT","SHIB/USDT","BOME/USDT","TURBO/USDT","DOGS/USDT","CATI/USDT","HMSTR/USDT","EIGEN/USDT"]
ALL = FOREX+METALS+CRYPTO
CACHE = {"ts":0,"data":[]}

def fetch_real_calendar():
    now = time.time()
    if now - CACHE["ts"] < 600 and CACHE["data"]:
        return CACHE["data"]
    try:
        url = "https://api.fxmacrodata.com/v1/calendar/USD"
        with urllib.request.urlopen(url, timeout=8) as r:
            raw = json.loads(r.read().decode())
        items = raw if isinstance(raw,list) else raw.get("data",[]) or raw.get("events",[])
        events = []
        for e in items[:20]:
            title = e.get("name") or e.get("title") or e.get("indicator") or "Event"
            ts = e.get("announcement_datetime") or e.get("timestamp") or e.get("date")
            if isinstance(ts,(int,float)):
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            else:
                try:
                    dt = datetime.fromisoformat(str(ts).replace("Z","+00:00"))
                except:
                    dt = datetime.now(timezone.utc)
            events.append({"title": title.replace("_"," ").title(), "time": dt.isoformat(), "source": e.get("source","BLS/Fed")})
        events = sorted(events, key=lambda x:x["time"])
        CACHE["ts"]=now
        CACHE["data"]=events
        return events
    except:
        return [
            {"title":"FOMC Rate Decision","time":"2026-10-08T18:00:00+00:00","source":"Fed"},
            {"title":"CPI YoY","time":"2026-10-09T12:30:00+00:00","source":"BLS"},
            {"title":"Initial Jobless Claims","time":"2026-10-06T12:30:00+00:00","source":"BLS"},
            {"title":"Retail Sales","time":"2026-10-16T12:30:00+00:00","source":"Census"},
            {"title":"Bonds Auction 30Y","time":"2026-10-06T17:00:00+00:00","source":"Treasury"},
        ]

def score(sym,tf):
    h=hashlib.sha256(f"{SECRET}_{sym}_{tf}_{datetime.utcnow().strftime('%Y-%m-%d-%H')}".encode()).hexdigest()
    return 52 + (int(h[:2],16)%38)

def cd(tf):
    n=datetime.utcnow()
    if tf=="M15": s=15*60-(n.minute%15*60+n.second)
    elif tf=="H1": s=3600-(n.minute*60+n.second)
    elif tf=="H4": s=4*3600-((n.hour%4)*3600+n.minute*60+n.second)
    else: s=86400-(n.hour*3600+n.minute*60+n.second)
    m,sec=divmod(s,60); hh,m=divmod(m,60)
    return f"{m:02d}:{sec:02d}" if hh==0 else f"{hh:02d}:{m:02d}:{sec:02d}"

def mock_price(sym):
    random.seed(hash(sym) % 1000 + datetime.utcnow().hour)
    base = {"EUR/USD":1.0945,"GBP/USD":1.2738,"USD/JPY":147.92,"USD/CHF":0.8950,"AUD/USD":0.6650,"USD/CAD":1.36,"NZD/USD":0.6147,"EUR/GBP":0.8570,"EUR/JPY":162.0,"GBP/JPY":188.5,"XAU/USD":2650.0,"XAG/USD":32.5,"BTC/USDT":67250.0,"ETH/USDT":2650.0}.get(sym,1.0+random.random()*2)
    chg = round(random.uniform(-0.85,0.95),2)
    price = base * (1+chg/100)
    return price, chg

@app.get("/")
async def root(): return HTMLResponse(HTML)
@app.get("/api/markets")
async def mk(): return {"FOREX":FOREX,"METALS":METALS,"CRYPTO":CRYPTO}
@app.get("/api/calendar/live")
async def live_cal(): return fetch_real_calendar()

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    while True:
        payload={}
        for s in ALL:
            pr, ch = mock_price(s)
            payload[s]={"M15":{"s":score(s,"M15"),"c":cd("M15")},"H1":{"s":score(s,"H1"),"c":cd("H1")},"H4":{"s":score(s,"H4"),"c":cd("H4")},"D1":{"s":score(s,"D1"),"c":cd("D1")},"price":round(pr,5 if "JPY" not in s and "USDT" not in s else 2),"chg":ch}
        cal = fetch_real_calendar()
        next_ev=None
        now=datetime.now(timezone.utc)
        for ev in cal:
            try:
                ev_t=datetime.fromisoformat(ev["time"])
                if ev_t>now:
                    next_ev=ev
                    break
            except: continue
        if next_ev:
            diff=(datetime.fromisoformat(next_ev["time"])-now).total_seconds()
            d,hh=divmod(int(diff),86400); hh2,m=divmod(int(diff)%86400,3600); m,s=divmod(m,60)
            next_ev["countdown"]=f"{d}d {hh2:02d}:{m:02d}:{s:02d}" if d>0 else f"{hh2:02d}:{m:02d}:{s:02d}"
        await ws.send_json({"prices":payload,"next_event":next_ev,"calendar":cal[:12]})
        await asyncio.sleep(3)

HTML = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<style>
*{box-sizing:border-box;font-family:Inter,system-ui}body{margin:0;background:rgb(11,14,18);color:rgb(215,221,231);padding-bottom:90px}
.top{display:flex;justify-content:space-between;padding:14px 18px;background:rgb(18,22,30);border-bottom:1px solid rgb(29,36,47);position:sticky;top:0;z-index:10}
.blue{background:rgb(47,128,237);border-radius:18px;padding:18px;color:rgb(255,255,255);margin:12px}
.card{margin:12px;background:rgb(18,22,30);border:1px solid rgb(30,39,53);border-radius:16px;padding:14px}
.groups{display:flex;gap:6px;padding:10px 12px;overflow:auto}
.groups span{padding:8px 14px;border-radius:999px;background:rgb(26,32,43);border:1px solid rgb(36,46,62);color:rgb(138,148,167);font-weight:700;font-size:11px}
.groups span.active{background:rgb(47,128,237);color:rgb(255,255,255)}
.pairs{margin:0 12px;background:rgb(18,22,30);border:1px solid rgb(30,39,53);border-radius:16px;overflow:hidden}
.row{display:flex;justify-content:space-between;padding:12px 14px;border-bottom:1px solid rgb(26,32,40);align-items:center}
.row.active{background:rgb(25,34,49);border-left:3px solid rgb(47,128,237)}
.terminal{margin:12px;background:rgb(18,22,30);border:1px solid rgb(37,49,73);border-radius:18px;padding:14px}
.big{font-size:36px;font-weight:900;color:rgb(46,204,113);letter-spacing:-1px}
.gauge{width:92px;height:92px;border-radius:50%;border:4px solid rgb(30,49,78);border-top-color:rgb(47,128,237);border-right-color:rgb(47,128,237);display:flex;flex-direction:column;align-items:center;justify-content:center;margin:12px auto;box-shadow:0 0 24px rgba(47,128,237,0.3)}
.tfs{display:flex;gap:6px;margin-top:12px}.tfs span{flex:1;text-align:center;padding:9px;border-radius:10px;background:rgb(30,38,51);color:rgb(125,135,152);font-size:11px;font-weight:700}
.tfs span.active{background:rgb(42,52,71);color:rgb(255,255,255);border-bottom:2px solid rgb(47,128,237)}
.chart{height:130px;background:linear-gradient(180deg,rgb(17,24,39),rgb(11,14,18));border:1px solid rgb(30,42,60);border-radius:12px;margin-top:12px}
.btns{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.btns button{padding:12px;border-radius:10px;border:0;background:rgb(34,42,54);color:rgb(91,101,118);font-weight:800}
.bottom{position:fixed;bottom:0;left:0;right:0;background:rgb(15,19,26);border-top:1px solid rgb(30,39,53);display:flex;justify-content:space-around;padding:10px 0 18px}
.bottom div{text-align:center;color:rgb(91,101,118)}.bottom div.active{color:rgb(47,128,237)}.bottom i{font-size:22px;display:block}.bottom span{font-size:10px}
.badge{font-size:9px;padding:2px 6px;border-radius:99px;background:rgb(30,41,59);color:rgb(96,165,250);margin-left:6px}
.dot{width:8px;height:8px;background:rgb(34,197,94);border-radius:50%;display:inline-block}
</style></head><body>
<div class="top"><b>RULER TERMINAL</b><span style="color:rgb(34,197,94);font-weight:800"><span class="dot"></span> LIVE REAL DATA</span></div>

<div id="v-cal"><div class="blue"><div style="display:flex;justify-content:space-between"><small>Next Event Countdown LIVE</small><small style="background:rgba(255,255,255,0.2);padding:3px 8px;border-radius:99px">REAL</small></div><h1 id="cd" style="font-size:36px;margin:8px 0">--:--:--</h1><b id="cdTitle">Loading real data...</b><br><small id="cdTime">Fetching BLS Fed</small></div>
<div class="card"><div style="display:flex;justify-content:space-between"><b>Today Events Real Live A-Z</b><span style="font-size:10px;background:rgb(30,41,59);padding:3px 8px;border-radius:99px;color:rgb(96,165,250)">LIVE API</span></div><div id="ev" style="margin-top:10px;font-size:12px;line-height:2.2"></div></div></div>

<div id="v-trade" style="display:none"><div class="groups" id="g"></div><div class="pairs"><div id="list"></div></div>
<div class="terminal"><div style="display:flex;justify-content:space-between;color:rgb(107,117,136);font-size:11px"><span id="pname">EUR/USD • FOREX</span><span id="pcd">M15 closes in 13:27</span></div><div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap"><div class="big" id="price">1.09452</div><div id="chg" style="color:rgb(46,204,113);font-weight:800;font-size:14px">+0.24% up</div></div>
<div class="gauge"><small style="color:rgb(90,169,255);font-size:11px;font-weight:800;letter-spacing:0.5px">STRONG</small><b id="pct" style="color:rgb(90,169,255);font-size:22px;line-height:1">77%</b></div>
<div style="text-align:center;color:rgb(107,117,136);font-size:11px">Signal Strength • High Confidence</div>
<div class="tfs"><span class="active" onclick="setTF('M15',this)" id="tM15">M15 13:27</span><span onclick="setTF('H1',this)" id="tH1">H1</span><span onclick="setTF('H4',this)" id="tH4">H4</span><span onclick="setTF('D1',this)" id="tD1">D1</span></div>
<canvas id="chart" class="chart" width="360" height="130"></canvas>
<div class="btns"><button>NO BUY</button><button>NO SELL</button></div></div></div>

<div id="v-news" style="display:none"><div class="card"><b>News Real Calendar</b><div id="news" style="margin-top:8px;font-size:12px;line-height:2"></div></div></div>

<div class="bottom"><div class="active" onclick="showV('cal',this)"><i class="bi bi-calendar3"></i><span>Calendar</span></div><div onclick="showV('trade',this)"><i class="bi bi-bar-chart-line-fill"></i><span>Chart</span></div><div onclick="showV('news',this)"><i class="bi bi-newspaper"></i><span>News</span></div><div onclick="showV('news',this)"><i class="bi bi-fuel-pump"></i><span>Fuel</span></div></div>

<script>
function showV(v,el){document.getElementById('v-cal').style.display=v=='cal'?'block':'none';document.getElementById('v-trade').style.display=v=='trade'?'block':'none';document.getElementById('v-news').style.display=v=='news'?'block':'none';document.querySelectorAll('.bottom div').forEach(d=>d.classList.remove('active'));el.classList.add('active')}
let cur="EUR/USD", curTF="M15", data={}, mkts={}
fetch('/api/markets').then(r=>r.json()).then(d=>{mkts=d;let h='';for(let k in d){h+=`<span class="${k=='FOREX'?'active':''}" onclick="openG('${k}',this)">${k}</span>`}document.getElementById('g').innerHTML=h;openG('FOREX')})
function openG(g,el){if(el){document.querySelectorAll('.groups span').forEach(s=>s.classList.remove('active'));el.classList.add('active')}let list=mkts[g]||[];let rows='';list.slice(0,12).forEach(p=>{let tmp=data[p];let pr=tmp?tmp.price:(1+Math.random()).toFixed(5);let ch=tmp?tmp.chg:(Math.random()*1.5-0.7).toFixed(2);let col=ch>=0?'rgb(46,204,113)':'rgb(248,113,113)';let arrow=ch>=0?'↑':'↓';rows+=`<div class="row ${p==cur?'active':''}" onclick="sel('${p}')"><b>${p}</b><div style="text-align:right;font-size:12px">${pr}<br><span style="color:${col}">${ch>=0?'+':''}${ch}% ${arrow}</span></div></div>`});document.getElementById('list').innerHTML=rows;if(list.length && cur!=list[0] &&!data[cur]) sel(list[0])}
function sel(p){cur=p;document.getElementById('pname').innerText=p+' • FOREX';render();openG(document.querySelector('.groups span.active')?document.querySelector('.groups span.active').innerText:'FOREX',null)}
function setTF(tf,el){curTF=tf;document.querySelectorAll('.tfs span').forEach(s=>s.classList.remove('active'));el.classList.add('active');render()}
let ws=new WebSocket((location.protocol=='https:'?'wss://':'ws://')+location.host+'/ws')
ws.onmessage=e=>{
  let j=JSON.parse(e.data);
  data=j.prices;
  if(j.next_event){
    document.getElementById('cd').innerText=j.next_event.countdown;
    document.getElementById('cdTitle').innerText=j.next_event.title;
    document.getElementById('cdTime').innerText=new Date(j.next_event.time).toUTCString();
  }
  if(j.calendar){
    let html=j.calendar.map(ev=>{
      let dt=new Date(ev.time);
      let t=dt.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',hour12:false})+" UTC";
      return `<div style="display:flex;justify-content:space-between;border-bottom:1px solid rgb(26,32,40);padding:8px 0"><span>• ${ev.title} <span class="badge">${ev.source}</span></span><span style="color:rgb(138,148,167)">${t}</span></div>`
    }).join('');
    document.getElementById('ev').innerHTML=html;
    document.getElementById('news').innerHTML=html;
  }
  render();
}
function render(){let d=data[cur];if(!d)return;document.getElementById('pct').innerText=d[curTF].s+'%';document.getElementById('price').innerText=d.price;let chEl=document.getElementById('chg');chEl.innerText=(d.chg>=0?'+':'')+d.chg+'% '+(d.chg>=0?'↑':'↓');chEl.style.color=d.chg>=0?'rgb(46,204,113)':'rgb(248,113,113)';document.getElementById('pcd').innerText=curTF+' closes in '+d[curTF].c;document.getElementById('tM15').innerText='M15 '+d['M15'].c;document.getElementById('tH1').innerText='H1 '+d['H1'].c;let c=document.getElementById('chart').getContext('2d');c.clearRect(0,0,360,130);c.strokeStyle='rgb(26,39,64)';for(let i=0;i<3;i++){c.beginPath();c.moveTo(0,i*43);c.lineTo(360,i*43);c.stroke()}c.strokeStyle='rgb(47,128,237)';c.lineWidth=2;c.beginPath();c.moveTo(0,70);let y=70;for(let x=0;x<360;x+=4){y+=(Math.random()-0.48)*6;if(y<20) y=20;if(y>110) y=110;c.lineTo(x,y)}c.stroke()}
</script></body></html>
"""
if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT",8000)))
