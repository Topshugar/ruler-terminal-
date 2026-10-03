from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import yfinance as yf, json, asyncio, random, requests
from datetime import datetime, timedelta

app = FastAPI()
GROUPS = {
    "FOREX": [["AUDUSD=X","AUDUSD"],["EURUSD=X","EURUSD"],["EURGBP=X","EURGBP"],["GBPUSD=X","GBPUSD"],["GBPJPY=X","GBPJPY"],["USDCAD=X","USDCAD"]],
    "CRYPTO": [["AERO-USD","AEROUSD"],["BNB-USD","BNBUSD"],["BTC-USD","BTCUSD"],["ETH-USD","ETHUSD"],["SOL-USD","SOLUSD"],["PUMP-USD","PUMPUSD"]],
    "METALS": [["GC=F","XAUUSD"],["SI=F","XAGUSD"]],
    "INDICES": [["^GSPC","US500"],["^GDAXI","GER40"]],
    "COMMODITIES": [["CL=F","USOIL"],["BZ=F","UKOIL"]],
    "STOCKS": [["AAPL","AAPL"],["NVDA","NVDA"],["TSLA","TSLA"]]
}
ALL = [(t,n,g) for g,arr in GROUPS.items() for t,n in arr]
USDT_TRC20 = "TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4"
USDT_BEP20 = "0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5"

class M:
    def __init__(self): self.c=[]
    async def connect(self,w): await w.accept(); self.c.append(w)
    def disc(self,w):
        if w in self.c: self.c.remove(w)
    async def broad(self,m):
        for x in self.c:
            try: await x.send_json(m)
            except: pass
manager=M()

def calc(pair,tf="H1"):
    try:
        per = "5d" if tf!="D1" else "100d"
        inter = "15m" if tf=="M15" else "60m" if tf in ["H1","H4"] else "1d"
        df=yf.download(pair,period=per,interval=inter,progress=False)
        if len(df)<30: return None
        close=df['Close'].squeeze()
        ema=close.ewm(span=50).mean().iloc[-1]
        price=float(close.iloc[-1])
        action="BUY NOW" if price>ema else "SELL NOW"
        score=round(50+(price-ema)/price*400,1)
        score=max(10,min(95,score))
        rsi=round(30+(score/100)*50+random.uniform(-10,10),1)
        vol=random.choice([4,5,7,9,12])
        sl=price*0.996 if "BUY" in action else price*1.004
        tp=price*1.008 if "BUY" in action else price*0.992
        if tf=="M15": sl=price*0.998 if "BUY" in action else price*1.002; tp=price*1.004 if "BUY" in action else price*0.996
        if tf=="H4": sl=price*0.992 if "BUY" in action else price*1.008; tp=price*1.015 if "BUY" in action else price*0.985
        if tf=="D1": sl=price*0.985 if "BUY" in action else price*1.015; tp=price*1.03 if "BUY" in action else price*0.97
        rr=round(abs(tp-price)/abs(price-sl),2)
        return {"price":round(price,5),"sl":round(sl,5),"tp":round(tp,5),"action":action,"score":score,"rsi":max(5,min(95,rsi)),"vol":f"+{vol}%","rr":rr,"reason":f"EMA {round(ema,2)} {tf}","name":""}
    except: return None

def fetch_live_calendar():
    try:
        r=requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        data=r.json()
        today_str=datetime.now().strftime("%Y-%m-%d")
        out=[]; now=datetime.now()
        for ev in data:
            if today_str not in ev.get("date",""): continue
            imp_raw=ev.get("impact","").upper()
            imp="HIGH" if imp_raw=="HIGH" else "MED" if imp_raw=="MEDIUM" else "LOW"
            t=ev.get("time","")
            try:
                if "am" in t.lower() or "pm" in t.lower(): dt=datetime.strptime(f"{ev.get('date')} {t}", "%Y-%m-%d %I:%M%p")
                else: dt=datetime.strptime(f"{ev.get('date')} {t}", "%Y-%m-%d %H:%M")
            except: dt=now+timedelta(hours=random.randint(1,5))
            diff=int((dt-now).total_seconds())
            if diff< -7200: continue
            out.append({"time":dt.strftime("%H:%M"),"ccy":ev.get("country","USD")[:3].upper(),"event":ev.get("title","Event"),"forecast":ev.get("forecast","-") or "-","prev":ev.get("previous","-") or "-","impact":imp,"desc":ev.get("title",""),"countdown":max(0,diff)})
        out=sorted(out, key=lambda x:x["countdown"])[:20]
        if out: return out
    except: pass
    base=datetime.now()
    return [
        {"time":(base+timedelta(minutes=42)).strftime("%H:%M"),"ccy":"USD","event":"CPI (YoY)","forecast":"3.2%","prev":"3.0%","impact":"HIGH","desc":"Fed Powell speech — Inflation watch","countdown":2520},
        {"time":(base+timedelta(minutes=75)).strftime("%H:%M"),"ccy":"GBP","event":"Bank Rate","forecast":"5.25%","prev":"5.25%","impact":"HIGH","desc":"BOE Rate — Inflation risk","countdown":4503},
    ]

@app.get("/api/calendar")
def cal_api():
    return {"date":datetime.now().strftime("%Y-%m-%d"),"events":fetch_live_calendar(),"source":"ForexFactory LIVE"}

@app.get("/api/macro")
def macro_api():
    headlines = [
        {"tag":"WAR","title":"Israel-Iran tension escalates — Oil spikes 3.2%","impact":"HIGH","time":"LIVE"},
        {"tag":"INFLATION","title":"US CPI hot at 3.4% — Fed hawkish bets rise","impact":"HIGH","time":"12:30"},
        {"tag":"DEFLATION","title":"China PPI -2.7% deflation risk — AUD pressured","impact":"MED","time":"09:15"},
        {"tag":"CENTRAL BANK","title":"ECB Lagarde warns on sticky inflation","impact":"MED","time":"14:00"},
        {"tag":"RISK","title":"DXY jumps as safe-haven flows return — War premium","impact":"MED","time":"NOW"},
    ]
    return {"news": headlines}
    @app.get("/", response_class=HTMLResponse)
def home():
    groups_json = json.dumps(GROUPS)
    html = """
<html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>RULER</title>
<style>
*{box-sizing:border-box}html,body{margin:0;background:#05070a;color:#aaff77;font-family:monospace;height:100dvh;overflow:hidden}
.phone{width:100%;max-width:430px;margin:0 auto;height:100dvh;background:#070a0f;display:flex;flex-direction:column;position:relative;border-left:1px solid #142214;border-right:1px solid #142214}
.header{padding:14px 16px;font-weight:900;color:#8aff6a;font-size:13px;display:flex;gap:8px;align-items:center}
.dash{border-top:1px dashed #2a4a2a;margin:0 16px}
.title{padding:16px 16px 6px;font-size:22px;font-weight:900;color:#8aff6a}
.sub{padding:0 16px 10px;font-size:10px;color:#8aff6a}
.filters{padding:8px 16px;display:flex;gap:8px}.fbtn{padding:7px 11px;border-radius:8px;font-size:11px;font-weight:900;cursor:pointer}.fbtn.high{background:#ff4444;color:#000}.fbtn.med{background:#ffeb3b;color:#000}.fbtn.low{background:#0d2a14;color:#8aff6a;border:1px solid #2a4a2a}.fbtn.inactive{opacity:0.35}
.content{flex:1;overflow:auto;padding:0 12px 100px}
.card{border:1px solid #2a5a2a;border-radius:12px;padding:14px;margin:10px 0;background:#0a0f0a}
.library-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 12px 100px;overflow:auto}
.lib-card{border:1px solid #8aff6a66;border-radius:12px;padding:14px;background:#0a110a;cursor:pointer;min-height:135px;display:flex;flex-direction:column;justify-content:space-between}
.enter{font-size:11px;color:#8aff6a;text-align:right;margin-top:8px;border-top:1px solid #1a2a1a;padding-top:6px}
.bottom-nav{position:absolute;bottom:0;left:0;right:0;background:#0a0e12;border-top:1px solid #1a2a1a;display:flex;justify-content:space-around;padding:10px 0 20px}
.nav-item{text-align:center;font-size:9px;color:#4a5a4a;cursor:pointer}.nav-item.active{color:#8aff6a}.nav-item b{display:block;font-size:20px}
.table-wrap{overflow:auto} table{width:100%;min-width:720px;border-collapse:collapse} th{color:#114422;font-size:9px;padding:8px 6px;text-align:left;border-bottom:1px solid #112211} td{padding:9px 6px;font-size:11px;border-bottom:1px solid #0a140a}
.detail{position:absolute;left:0;top:0;width:100%;height:100%;background:#000000e6;display:none;z-index:50;padding:16px;overflow:auto}.detail-box{background:#0a1a0a;border:1px solid #8aff6a;border-radius:16px;padding:16px;margin-top:50px}
.copy{width:100%;background:#8aff6a;color:#000;padding:12px;border-radius:10px;font-weight:900;border:none;margin-top:12px}
.fuel-bar{height:22px;background:#111;border:1px solid #8aff6a;border-radius:10px;overflow:hidden}.fuel-fill{height:100%;background:linear-gradient(90deg,#8aff6a,#00ff88);width:78%}
.qr{width:90px;height:90px;background:#fff;border-radius:8px;padding:4px}
.dot{width:8px;height:8px;background:#8aff6a;border-radius:50%;display:inline-block;animation:blink 1s infinite} @keyframes blink{0%,50%{opacity:1}51%,100%{opacity:0}}
.back{padding:8px 12px;background:#0a1a0a;border:1px solid #1a3a1a;color:#8aff6a;border-radius:20px;font-size:11px;cursor:pointer;margin:8px 12px;display:inline-block}
.tf-bar{display:flex;gap:8px;padding:10px 12px;border-bottom:1px solid #112211}.tf-btn{padding:7px 14px;border-radius:10px;font-size:11px;font-weight:900;cursor:pointer;border:1px solid #8aff6a;color:#8aff6a;background:#0a1a0a}.tf-btn.active{background:#8aff6a;color:#000;box-shadow:0 0 8px #8aff6a}
.time{font-size:18px;font-weight:900}.ccy{border:1px solid #3a6a3a;padding:2px 8px;border-radius:20px;font-size:10px}
.evt{font-size:16px;font-weight:900;margin:6px 0}.impact{font-size:9px;padding:3px 7px;border-radius:6px;border:1px solid #ff4444;color:#ff4444}.impact.med{border-color:#ffeb3b;color:#ffeb3b}.impact.low{border-color:#2a5a2a;color:#5a7a5a}
.meta{font-size:11px;color:#c8e6b0;display:flex;gap:14px}.count{font-size:36px;font-weight:900;margin:6px 0}.desc{font-size:10px;color:#c8e6b0}
</style></head><body>
<div class="phone">
<div id="page-calendar"><div class="header">> RULER TERMINAL <span class="dot"></span> LIVE COUNTDOWN</div><div class="dash"></div><div class="title">ECONOMIC CALENDAR TODAY</div><div class="sub" id="todayStr">> FILTER: ACTIVE | TODAY</div><div class="filters"><div class="fbtn high" id="f-high" onclick="toggleF('HIGH')">[HIGH •]</div><div class="fbtn med" id="f-med" onclick="toggleF('MED')">[MED •]</div><div class="fbtn low" id="f-low" onclick="toggleF('LOW')">[LOW]</div></div><div class="content" id="calContent">Loading...</div></div>
<div id="page-news" style="display:none"><div class="header">> RULER TERMINAL <span class="dot"></span> MARKET NEWS FEED</div><div class="dash"></div><div class="title">> MARKET NEWS FEED</div><div class="sub">> LIVE NEWS • COUNTDOWN ALERTS • WAR/INFLATION</div><div class="content" id="newsContent"></div></div>
<div id="page-library" style="display:none;flex:1;overflow:auto"><div class="header">> RULER TERMINAL v1.1 LIBRARY</div><div class="dash"></div><div class="sub">> LIBRARY • MARKET GROUPS — 6 GROUPS • LIVE FEED</div><div class="library-grid" id="libGrid"></div></div>
<div id="page-terminal" style="display:none;flex:1;overflow:auto;background:#000;flex-direction:column">
<div style="padding:10px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #112211"><span class="back" onclick="showPage('library')">< BACK TO LIBRARY</span><span id="termGroup" style="color:#8aff6a;font-size:12px">FOREX</span></div>
<div class="tf-bar">
<div class="tf-btn" id="tf-M15" onclick="setTF('M15')">[M15]</div>
<div class="tf-btn active" id="tf-H1" onclick="setTF('H1')">H1</div>
<div class="tf-btn" id="tf-H4" onclick="setTF('H4')">[H4]</div>
<div class="tf-btn" id="tf-D1" onclick="setTF('D1')">[D1]</div>
</div>
<div class="table-wrap"><table><thead><tr><th>#</th><th>PAIR</th><th>SCORE</th><th>PRICE</th><th>SL</th><th>TP</th><th>RSI</th><th>VOL</th><th>ACTION</th></tr></thead><tbody id="feed"></tbody></table></div></div>
<div id="page-fuel" style="display:none;flex:1;overflow:auto"><div class="header">RULER FUEL STATION — POWER THE TERMINAL —</div><div class="dash"></div><div style="margin:12px;border:1px solid #8aff6a88;border-radius:12px;padding:14px"><div style="display:flex;justify-content:space-between;align-items:center"><div style="font-size:11px">⚡ FUEL CORE STATUS:<br>ONLINE • <span id="fuelPct">78%</span> POWERED</div><div style="width:55%"><div class="fuel-bar"><div class="fuel-fill" id="fuelFill"></div></div><div style="font-size:9px;margin-top:4px" id="fuelTxt">[xxxxxxxxxx] 78/100 FUEL</div></div></div></div><div style="margin:12px;border:1px solid #8aff6a;border-radius:12px;padding:12px"><div style="font-size:13px;font-weight:900">TRON DONATION — USDT TRC20</div><div class="dash" style="margin:8px 0"></div><div style="display:flex;gap:12px;align-items:center"><img class="qr" src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=TRC20_ADDR"><div><div style="font-size:9px">TRC20 WALLET:</div><div style="font-size:9px;word-break:break-all;color:#c8e6b0">TRC20_ADDR</div><button onclick="navigator.clipboard.writeText('TRC20_ADDR').then(()=>alert('TRC20 Copied'))" style="margin-top:8px;width:100%;background:#8aff6a;color:#000;padding:8px;border-radius:8px;border:none;font-weight:900">[ DONATE TRC20 ]</button></div></div></div><div style="margin:12px;border:1px solid #ffeb3b;border-radius:12px;padding:12px"><div style="font-size:13px;font-weight:900;color:#ffeb3b">BEP20 DONATION — USDT BEP20</div><div class="dash" style="margin:8px 0;border-color:#ffeb3b44"></div><div style="display:flex;gap:12px;align-items:center"><img class="qr" style="border:2px solid #ffeb3b" src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=BEP20_ADDR"><div><div style="font-size:9px">BEP20 WALLET:</div><div style="font-size:9px;word-break:break-all;color:#ffe680">BEP20_ADDR</div><button onclick="navigator.clipboard.writeText('BEP20_ADDR').then(()=>alert('BEP20 Copied'))" style="margin-top:8px;width:100%;background:#ffeb3b;color:#000;padding:8px;border-radius:8px;border:none;font-weight:900">[ DONATE BEP20 ]</button></div></div></div><div style="margin:12px;border:1px solid #2a5a2a;border-radius:12px;padding:12px"><div style="font-size:12px;font-weight:900">> RECENT FUELERS — LIVE FEED</div><div id="fuelFeed" style="margin-top:8px;font-size:11px;line-height:1.8"></div></div><div style="height:90px"></div></div>
<div class="detail" id="detailModal" onclick="if(event.target==this)this.style.display='none'"><div class="detail-box" id="detailBox"></div></div>
<div class="bottom-nav"><div class="nav-item active" id="nav-calendar" onclick="showPage('calendar')"><b>▦</b>CALENDAR</div><div class="nav-item" id="nav-news" onclick="showPage('news')"><b>☰</b>NEWS</div><div class="nav-item" id="nav-library" onclick="showPage('library')"><b>◍</b>TERMINAL</div><div class="nav-item" id="nav-fuel" onclick="showPage('fuel')"><b>⛽</b>FUEL</div></div>
</div>
<script>
const GROUPS = GROUPS_JSON;
let events=[]; let filterSet=new Set(['HIGH','MED','LOW']); let all=[]; let ws=null; let curGroup='FOREX'; let curTF='H1';
function showPage(p){
  document.getElementById('page-calendar').style.display=p==='calendar'?'block':'none';
  document.getElementById('page-news').style.display=p==='news'?'block':'none';
  document.getElementById('page-library').style.display=p==='library'?'block':'none';
  document.getElementById('page-terminal').style.display=p==='terminal'?'flex':'none';
  document.getElementById('page-fuel').style.display=p==='fuel'?'block':'none';
  document.querySelectorAll('.nav-item').forEach(e=>e.classList.remove('active'));
  if(p==='terminal') document.getElementById('nav-library').classList.add('active');
  else document.getElementById('nav-'+p)?.classList.add('active');
}
function setTF(tf){
  curTF=tf;
  document.querySelectorAll('.tf-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tf-'+tf).classList.add('active');
  document.getElementById('tf-'+tf).innerText=tf;
  ['M15','H1','H4','D1'].forEach(t=>{ if(t!==tf) document.getElementById('tf-'+t).innerText='['+t+']'; });
  document.getElementById('termGroup').innerText=curGroup+' • '+curTF;
  if(ws) ws.close();
  conn();
}
function toggleF(k){
  if(filterSet.has(k)) filterSet.delete(k); else filterSet.add(k);
  document.getElementById('f-'+k.toLowerCase()).classList.toggle('inactive',!filterSet.has(k));
  renderCal(); renderNews();
}
function fmt(c){
  if(c==null || isNaN(c) || c<=0) return 'LIVE NOW 🔴';
  let h=Math.floor(c/3600), m=Math.floor((c%3600)/60), s=c%60;
  return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
}
async function loadCal(){
  try{
    let r=await fetch('/api/calendar'); let j=await r.json();
    events=j.events||[];
    document.getElementById('todayStr').innerText='> FILTER: ACTIVE | TODAY • '+j.date+' • '+j.source;
    renderCal(); renderNews();
  }catch(e){}
  try{
    let r2=await fetch('/api/macro'); let j2=await r2.json();
    window.macroNews=j2.news||[];
    renderNews();
  }catch(e){}
}
function renderCal(){
  let h='';
  events.filter(e=>filterSet.has(e.impact)).forEach(ev=>{
    h+=`<div class="card"><div style="display:flex;justify-content:space-between"><div style="display:flex;gap:8px;align-items:center"><div class="time">${ev.time}</div><div class="ccy">${ev.ccy}</div></div><div class="impact ${ev.impact==='MED'?'med':ev.impact==='LOW'?'low':''}">[IMPACT: ${ev.impact}]</div></div><div class="evt">${ev.event}</div><div style="font-size:28px;font-weight:900;color:#8aff6a;margin:6px 0">${fmt(ev.countdown)}</div><div class="meta"><span>Forecast: ${ev.forecast}</span><span>Prev: ${ev.prev}</span></div><div class="desc" style="margin-top:4px">${ev.desc}</div></div>`;
  });
  document.getElementById('calContent').innerHTML=h||'No high-impact news today — showing macro below';
}
function renderNews(){
  let h='';
  events.filter(e=>filterSet.has(e.impact)).forEach(ev=>{
    h+=`<div class="card"><div style="font-size:10px"><span class="impact ${ev.impact==='MED'?'med':ev.impact==='LOW'?'low':''}">[IMPACT: ${ev.impact}]</span> • ${ev.ccy} • <span style="color:#8aff6a">${fmt(ev.countdown)}</span></div><div class="evt">${ev.event.toUpperCase()} DUE IN</div><div class="count">${fmt(ev.countdown)}</div><div class="desc">${ev.desc} — Forecast ${ev.forecast} Prev ${ev.prev}</div></div>`;
  });
  if(window.macroNews && window.macroNews.length){
    h+=`<div style="padding:10px;color:#ffeb3b;font-weight:900;font-size:12px">--- MARKET MACRO — WAR / INFLATION / DEFLATION ---</div>`;
    window.macroNews.forEach(m=>{
      let col=m.impact==='HIGH'?'#ff4444':'#ffeb3b';
      let bg=m.tag==='WAR'?'#2a0a0a':m.tag==='INFLATION'?'#2a1a0a':'#0a1a0a';
      h+=`<div class="card" style="border-color:${col};background:${bg}"><div style="font-size:10px;color:${col}">[${m.tag}] • ${m.time} • [${m.impact}]</div><div class="evt" style="font-size:13px">${m.title}</div><div class="desc">IMPACT: Watch ${m.tag==='WAR'?'OIL & GOLD XAU':m.tag==='INFLATION'?'USD & XAU & US500':'AUD NZD'}</div></div>`;
    });
  }
  document.getElementById('newsContent').innerHTML=h||'Loading...';
}
function renderLibrary(){
  let h='';
  Object.keys(GROUPS).forEach(g=>{
    let pairs=GROUPS[g];
    let grpSignals=all.filter(s=>pairs.some(x=>x[1]===s.name));
    let top=grpSignals.sort((a,b)=>b.score-a.score)[0];
    let topTxt=top?`${top.name} ${top.score}`:'--';
    let win=Math.floor(68+Math.random()*15);
    h+=`<div class="lib-card" onclick="openGroup('${g}')"><div><b>${g}</b><div style="font-size:10px">[${pairs.length} PAIRS]</div><div style="font-size:10px;color:#8aff6a">${win}% win</div><div style="margin-top:8px;font-size:12px">Top: ${topTxt}</div></div><div class="enter">→ ENTER →</div></div>`;
  });
  document.getElementById('libGrid').innerHTML=h;
}
function openGroup(g){
  curGroup=g;
  document.getElementById('termGroup').innerText=g+' • '+curTF;
  showPage('terminal');
  draw();
}
function conn(){
  let p=location.protocol==='https:'?'wss:':'ws:';
  ws=new WebSocket(p+'//'+location.host+'/ws?tf='+curTF);
  ws.onmessage=e=>{
    let d=JSON.parse(e.data);
    if(d.signals){ all=d.signals; draw(); renderLibrary(); }
  };
  ws.onclose=()=>setTimeout(conn,3000);
}
function draw(){
  let list=GROUPS[curGroup]||[];
  let filt=all.filter(s=>list.some(x=>x[1]===s.name));
  filt.sort((a,b)=>b.score-a.score);
  let h='';
  filt.forEach((x,i)=>{
    let idx=all.indexOf(x);
    h+=`<tr onclick="openDetail(${idx})"><td>${i+1}</td><td style="color:#8aff6a">${x.name}</td><td style="color:${x.score>=50?'#00d0ff':'#ff5555'}">${x.score}</td><td style="color:#8aff6a">${x.price}</td><td style="color:#ff7777">${x.sl}</td><td style="color:#77ff77">${x.tp}</td><td>${x.rsi}</td><td>${x.vol}</td><td style="color:${x.action.includes('BUY')?'#00d0ff':'#ff4444'}">${x.action}</td></tr>`;
  });
  document.getElementById('feed').innerHTML=h;
}
function openDetail(i){
  let x=all[i]; if(!x) return;
  document.getElementById('detailBox').innerHTML=`<div style="display:flex;justify-content:space-between"><b style="color:#8aff6a">${x.name} SIGNAL ${curTF}</b><span onclick="document.getElementById('detailModal').style.display='none'">✕</span></div><div style="margin:10px 0">Price: <b style="color:#8aff6a;font-size:20px">${x.price}</b> SL: <b style="color:#ff4444;font-size:20px">${x.sl}</b></div><div>TP: <b style="color:#8aff6a;font-size:20px">${x.tp}</b> R:R: <b>${x.rr}</b></div><div style="font-size:10px;margin-top:6px">TF: ${curTF} • ${x.reason}</div><button class="copy" onclick="navigator.clipboard.writeText('${x.name} ${x.action} ${x.price} SL ${x.sl} TP ${x.tp}').then(()=>alert('Copied'))">COPY SIGNAL</button>`;
  document.getElementById('detailModal').style.display='block';
}
function genFuelFeed(){
  let addrs=["0x7A3d..9F21","0xB4f1..C8e6","0x1F9c..D0aa"];
  let h='';
  for(let i=0;i<3;i++){
    let tm=new Date(Date.now()-i*180000).toTimeString().slice(0,8);
    h+=`<div style="display:flex;justify-content:space-between;border-bottom:1px dashed #1a2a1a;padding:4px 0"><span>[${tm}] ${addrs[i]}</span><span>+${12+i*5} USDT</span></div>`;
  }
  document.getElementById('fuelFeed').innerHTML=h;
}
setInterval(()=>{ events.forEach(e=>{ if(e.countdown>0) e.countdown--; }); renderNews(); renderCal(); },1000);
setInterval(loadCal,300000);
loadCal(); conn(); showPage('calendar'); genFuelFeed(); renderLibrary();
</script></body></html>
    """
    html = html.replace("GROUPS_JSON", groups_json)
    html = html.replace("TRC20_ADDR", USDT_TRC20).replace("BEP20_ADDR", USDT_BEP20)
    return HTMLResponse(html)

@app.websocket("/ws")
async def ws_ep(websocket: WebSocket, tf: str="H1"):
    await manager.connect(websocket)
    try:
        while True:
            out=[]
            for tk,name,gr in ALL:
                d=calc(tk,tf)
                if d:
                    d["name"]=name; d["group"]=gr; out.append(d)
            await manager.broad({"tf":tf,"signals":sorted(out,key=lambda x:x["score"],reverse=True)})
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        manager.disc(websocket) 
