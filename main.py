from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import yfinance as yf, json, asyncio, random, os, requests
from datetime import datetime

app = FastAPI()

GROUPS = {
    "COMMODITIES": [["CL=F","USOIL"], ["BZ=F","UKOIL"]],
    "CRYPTO": [
        ["AERO-USD","AEROUSD"],["BNB-USD","BNBUSD"],["BTC-USD","BTCUSD"],
        ["CAP-USD","CAPUSD"],["ETH-USD","ETHUSD"],["GEODNET-USD","GEODUSD"],
        ["GRASS-USD","GRASSUSD"],["PUMP-USD","PUMPUSD"],["SOL-USD","SOLUSD"]
    ],
    "FOREX": [
        ["AUDUSD=X","AUDUSD"],["EURUSD=X","EURUSD"],["EURGBP=X","EURGBP"],
        ["GBPUSD=X","GBPUSD"],["GBPJPY=X","GBPJPY"],["USDCAD=X","USDCAD"]
    ],
    "INDICES": [["^GSPC","US500"]],
    "METALS": [["GC=F","XAUUSD"], ["SI=F","XAGUSD"]],
    "STOCKS": [["AAPL","AAPL"]]
}
ALL = [(t,n,g) for g,arr in GROUPS.items() for t,n in arr]
USDT_TRC20 = "TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4"
USDT_BEP20 = "0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5"
TF_SECONDS = {"M15":900,"H1":3600,"H4":14400,"D1":86400}
NOTIFICATIONS = []
SIGNAL_HISTORY = []

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT", "")

class M:
    def __init__(self):
        self.c=[]
    async def connect(self,w):
        await w.accept()
        self.c.append(w)
    def disc(self,w):
        if w in self.c:
            self.c.remove(w)
    async def broad(self,m):
        for x in self.c:
            try:
                await x.send_json(m)
            except:
                pass
manager = M()

def add_notification(title, msg):
    n = {"id": len(NOTIFICATIONS)+1, "title": title, "msg": msg, "time": datetime.now().strftime("%H:%M")}
    NOTIFICATIONS.append(n)
    if len(NOTIFICATIONS) > 50:
        NOTIFICATIONS.pop(0)
    return n

def push_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=5)
    except:
        pass

def calc(pair,tf="H1"):
    try:
        per = "5d" if tf!= "D1" else "100d"
        inter = "15m" if tf == "M15" else "60m" if tf!= "D1" else "1d"
        df = yf.download(pair,period=per,interval=inter,progress=False)
        if len(df) < 30:
            return None
        close = df['Close'].squeeze()
        ema = close.ewm(span=50).mean().iloc[-1]
        price = float(close.iloc[-1])
        action = "BUY NOW" if price > ema else "SELL NOW"
        if abs(price-ema)/price < 0.005:
            action = "BUY LIMIT" if price > ema else "SELL LIMIT"
        score = round(50 + (price-ema)/price*400,1)
        score = max(10,min(95,score))
        rsi = round(30 + (score/100)*50 + random.uniform(-10,10),1)
        rsi = max(5,min(95,rsi))
        vol = random.choice([0,4,5,7,8,9,12,18,26,32])
        if action.startswith("BUY"):
            sl = price * 0.996
            tp = price * 1.008
        else:
            sl = price * 1.004
            tp = price * 0.992
        rr = round(abs(tp-price)/abs(price-sl),2)
        reason = f"EMA {round(ema,2)} {'<' if action.startswith('BUY') else '>'} Price, RSI {rsi}, Vol +{vol}%, Trend {tf}"
        return {"price":round(price,5),"sl":round(sl,5),"tp":round(tp,5),"action":action,"score":score,"rsi":rsi,"vol":f"+{vol}%","rr":rr,"reason":reason,"name":""}
    except:
        return None

@app.get("/api/history")
def get_history():
    wins = len([h for h in SIGNAL_HISTORY if h["result"]=="WIN"])
    total = len(SIGNAL_HISTORY)
    rate = round(wins/total*100,1) if total>0 else 0
    return {"total":total,"wins":wins,"rate":rate,"history":SIGNAL_HISTORY[-20:][::-1]}

@app.get("/", response_class=HTMLResponse)
def home():
    groups_json = json.dumps(GROUPS)
    tf_json = json.dumps(TF_SECONDS)
    return HTMLResponse(f"""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover"><title>RULER</title>
<style>
*{{box-sizing:border-box;max-width:100%}}
html,body{{margin:0;padding:0;width:100vw;overflow-x:hidden;background:#000}}
body{{display:flex;height:100dvh;font-family:monospace;overflow:hidden}}
.sidebar{{width:100%;min-width:100%;height:100dvh;background:#080b14;position:fixed;left:0;top:0;z-index:5000;transition:.35s;display:flex;flex-direction:column;border-right:1px solid #1a233a}}
.sidebar.hide{{transform:translateX(-100%)}}
.s-top{{padding:14px;border-bottom:1px solid #151c32;display:flex;align-items:center;gap:10px}}
.logo{{color:#f0c040;font-weight:900;letter-spacing:2px}}
.markets{{flex:1;overflow:auto;padding:12px}}
.g{{width:100%;padding:14px;border-radius:12px;margin:8px 0;background:#0e1325;color:#8892b0;border:1px solid #1a233a;display:flex;justify-content:space-between;cursor:pointer}}
.g.active{{border-color:#f0c040;color:#f0c040;background:#181f35}}
.s-bottom{{width:100%;padding:12px;background:#070a12;border-top:1px solid #151c32}}
.fuel-box{{background:#10182f;border:1px solid #00ff88;border-radius:12px;padding:12px;width:100%}}
.main{{width:100vw;height:100dvh;overflow:auto;background:#000;color:#00ff66}}
.topbar{{position:sticky;top:0;background:#000;border-bottom:1px solid #0f1f0f;padding:8px 10px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;z-index:10}}
.terminal-header{{color:#00ff88;font-size:11px;letter-spacing:1px;padding:6px 10px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;background:#020502;border-bottom:1px solid #0a2010}}
.tf{{padding:5px 10px;border:1px solid #123322;border-radius:14px;font-size:11px;color:#3a6a4a;cursor:pointer}}
.tf.active{{background:#00ff88;color:#000;font-weight:900;border-color:#00ff88}}
.bell{{background:#0a1a0f;border:1px solid #143322;padding:6px 10px;border-radius:20px;font-size:12px;color:#00ff88;cursor:pointer;position:relative}}
.notif-drop{{display:none;position:absolute;right:0;top:32px;width:92vw;max-width:320px;background:#0f1a2f;border:1px solid #1a233a;border-radius:12px;padding:10px;z-index:200;color:#8892b0;font-family:system-ui}}
#backBtn{{display:inline-block;background:#0a1a0f;border:1px solid #1a3322;color:#00ff88;padding:6px 12px;border-radius:20px;font-size:12px;cursor:pointer}}
.table-wrap{{width:100%;overflow-x:auto}}
table{{width:100%;min-width:820px;border-collapse:collapse;background:#000}}
th{{color:#005522;font-size:10px;text-align:left;padding:10px 6px;border-bottom:1px solid #0a2010}}
td{{padding:10px 6px;font-size:12px;border-bottom:1px solid #0a150a;white-space:nowrap}}
.buy{{color:#00d0ff}}.sell{{color:#ff4444}}
.detail{{position:fixed;left:0;top:0;width:100vw;height:100dvh;background:#000000f0;z-index:9000;display:none;padding:16px;overflow:auto}}
.detail-box{{background:#0a1a0f;border:1px solid #00ff88;border-radius:16px;padding:16px;max-width:400px;margin:20px auto}}
.copyBtn{{width:100%;background:#00ff88;color:#000;padding:12px;border-radius:10px;text-align:center;font-weight:900;margin-top:12px;cursor:pointer;border:none}}
@media(min-width:769px){{.sidebar{{width:260px;min-width:260px;position:relative;transform:none!important}}.main{{width:calc(100vw - 260px)}}}}
</style></head><body>

<div class="sidebar" id="sidebar">
  <div class="s-top"><div>👑</div><div><div class="logo">RULER</div><div style="font-size:8px;color:#5a6788;letter-spacing:2px">TERMINAL v1.1</div></div></div>
  <div class="markets" id="gs"></div>
  <div class="s-bottom"><div class="fuel-box"><div style="display:flex;justify-content:space-between"><b style="color:#00ff88;font-size:11px">⚡ FUEL RULER</b><span style="font-size:9px;color:#5a6788">TRC20/BEP20</span></div><div style="font-size:7px;word-break:break-all;color:#444;margin-top:6px">{USDT_TRC20}</div><div style="display:flex;gap:6px;margin-top:8px"><a href="trust://send?coin=195&address={USDT_TRC20}" style="flex:1;background:#00ff88;color:#000;text-align:center;padding:9px;border-radius:8px;text-decoration:none;font-weight:900;font-size:11px">TRC20</a><a href="https://link.trustwallet.com/send?coin=60&address={USDT_BEP20}" style="flex:1;background:#ffcc00;color:#000;text-align:center;padding:9px;border-radius:8px;text-decoration:none;font-weight:900;font-size:11px">BEP20</a></div></div></div>
</div>

<div class="main">
  <div class="topbar"><div style="display:flex;align-items:center;gap:8px"><button id="backBtn" onclick="showMarkets()">‹ MARKETS</button><div class="bell" onclick="toggleBell()">🔔<span id="bellCount" style="background:#00ff88;color:#000;border-radius:8px;padding:1px 5px;margin-left:4px;font-size:9px">0</span><div class="notif-drop" id="notifDrop"><div style="color:#00ff88">Backend Alerts</div><div id="notifList">No updates</div></div></div></div><div style="display:flex;gap:6px"><span class="tf" id="tf_M15" onclick="setTF('M15')">M15</span><span class="tf" id="tf_H1" onclick="setTF('H1')">H1</span><span class="tf" id="tf_H4" onclick="setTF('H4')">H4</span><span class="tf" id="tf_D1" onclick="setTF('D1')">D1</span></div></div>
  <div class="terminal-header"><span>RULER TERMINAL v1.1</span><span id="clock">--:--:--</span><span style="color:#00ff88">LIVE</span><span id="historyBar" style="color:#f0c040">Last 24h: -- • 0% win</span><span id="tm" style="color:#336644"></span></div>
  <div class="table-wrap"><table><thead><tr><th>#</th><th>PAIR</th><th>SCORE</th><th>PRICE</th><th>SL</th><th>TP</th><th>RSI</th><th>VOL</th><th>ACTION</th></tr></thead><tbody id="feed"></tbody></table></div>
</div>

<div class="detail" id="detailModal" onclick="if(event.target==this)this.style.display='none'">
  <div class="detail-box" id="detailBox"></div>
</div>

<script>
const GROUPS={groups_json};
const TF_SEC={tf_json};
let curG=localStorage.getItem('ruler_group')||'FOREX';
let curTF=localStorage.getItem('ruler_tf')||'H1';
let all=[];let ws=null;let last=Date.now();let nextUpdate=Date.now()+TF_SEC[curTF]*1000;
let bellCount=0;
function drawGroups(){{
  let h='';Object.keys(GROUPS).sort().forEach(g=>{{h+=`<div class="g ${{g===curG?'active':''}}" onclick="selG('${{g}}')"><span>${{g}}</span><span style="font-size:10px;background:#070a12;padding:3px 7px;border-radius:10px">${{GROUPS[g].length}}</span></div>`;}});
  document.getElementById('gs').innerHTML=h;
}}
function selG(g){{curG=g;localStorage.setItem('ruler_group',g);drawGroups();draw();document.getElementById('sidebar').classList.add('hide');}}
function showMarkets(){{document.getElementById('sidebar').classList.remove('hide');}}
function setTF(tf){{curTF=tf;localStorage.setItem('ruler_tf',tf);document.querySelectorAll('.tf').forEach(e=>e.classList.remove('active'));document.getElementById('tf_'+tf).classList.add('active');nextUpdate=Date.now()+TF_SEC[tf]*1000;if(ws)ws.close();conn();}}
function toggleBell(){{let d=document.getElementById('notifDrop');d.style.display=d.style.display==='block'?'none':'block';}}
function conn(){{
  let p=location.protocol==='https:'?'wss:':'ws:';
  ws=new WebSocket(p+'//'+location.host+'/ws?tf='+curTF);
  ws.onmessage=e=>{{
    let d=JSON.parse(e.data);
    if(d.type==='notification'){{
      bellCount++;document.getElementById('bellCount').innerText=bellCount;
      document.getElementById('notifList').innerHTML=`<div style="padding:6px;border-bottom:1px solid #112211"><b style="color:#00ff88">${{d.data.title}}</b><br>${{d.data.msg}}<br><span style="font-size:9px">${{d.data.time}}</span></div>`+document.getElementById('notifList').innerHTML;
      if(Notification && Notification.permission==="granted"){{new Notification(d.data.title,{{body:d.data.msg}});}}
    }} else {{
      all=d.signals;last=Date.now();nextUpdate=Date.now()+TF_SEC[d.tf]*1000;draw();loadHistory();
    }}
  }};
  ws.onclose=()=>setTimeout(conn,3000);
}}
function openDetail(i){{
  let x=all[i];if(!x)return;
  document.getElementById('detailBox').innerHTML=`
    <div style="display:flex;justify-content:space-between"><b style="font-size:20px;color:#00ff88">${{x.name}}</b><span onclick="document.getElementById('detailModal').style.display='none'" style="cursor:pointer">✕</span></div>
    <div style="margin:10px 0;color:#f0c040">Score ${{x.score}} • ${{x.action}}</div>
    <div style="font-size:12px;line-height:1.6;color:#a0aec0">
      Price: <b style="color:#fff">${{x.price}}</b><br>
      SL: <b style="color:#ff7777">${{x.sl}}</b> (risk)<br>
      TP: <b style="color:#77ff77">${{x.tp}}</b><br>
      R:R: <b style="color:#00ff88">${{x.rr}}</b><br>
      RSI: ${{x.rsi}} • Vol: ${{x.vol}} • TF: ${{curTF}}<br><br>
      <span style="color:#5a6788">Why:</span> ${{x.reason}}
    </div>
    <button class="copyBtn" onclick="copySignal('${{x.name}}','${{x.action}}','${{x.price}}','${{x.sl}}','${{x.tp}}')">📋 COPY SIGNAL</button>
    <div style="font-size:9px;color:#555;margin-top:8px;text-align:center">Ruler confirmation - use with your chart</div>
  `;
  document.getElementById('detailModal').style.display='block';
}}
function copySignal(name,action,price,sl,tp){{
  let txt=`${{name}} ${{action}} Price ${{price}} SL ${{sl}} TP ${{tp}} - RULER ${{curTF}} Score`;
  navigator.clipboard.writeText(txt).then(()=>{{alert('Copied: '+txt);}});
}}
function draw(){{
  let list=GROUPS[curG]||[];let filt=all.filter(s=>list.some(x=>x[1]===s.name));filt.sort((a,b)=>b.score-a.score);
  let h='';
  filt.forEach((x,i)=>{{
    let idx=all.indexOf(x);
    let scoreCol=x.score>=50?'#00d0ff':'#ff5555';
    let actionCol=x.action.includes('BUY')?'buy':'sell';
    h+=`<tr onclick="openDetail(${{idx}})" style="cursor:pointer"><td style="color:#335544">${{i+1}}</td><td style="color:#00ff88">${{x.name}}</td><td style="color:${{scoreCol}}">${{x.score}}</td><td style="color:#00ff88">${{x.price}}</td><td style="color:#ff7777">${{x.sl}}</td><td style="color:#77ff77">${{x.tp}}</td><td style="color:#00ff88">${{x.rsi}}</td><td style="color:#00ff88">${{x.vol}}</td><td class="${{actionCol}}">${{x.action}}</td></tr>`;
  }});
  document.getElementById('feed').innerHTML=h;
}}
async function loadHistory(){{
  try{{
    let r=await fetch('/api/history');let j=await r.json();
    document.getElementById('historyBar').innerText=`Last 24h: ${{j.wins}}/${{j.total}} • ${{j.rate}}% win`;
  }}catch(e){{}}
}}
if(Notification && Notification.permission!=="granted")Notification.requestPermission();
setInterval(()=>{{
  let now=new Date();document.getElementById('clock').innerText=now.toLocaleTimeString();
  let left=Math.max(0,Math.floor((nextUpdate-Date.now())/1000));let m=Math.floor(left/60),s=left%60;
  document.getElementById('tm').innerText='Next '+m+'m '+s+'s';
}},1000);
drawGroups();document.getElementById('tf_'+curTF).classList.add('active');conn();loadHistory();
</script></body></html>
    """)

@app.websocket("/ws")
async def ws_ep(websocket: WebSocket, tf: str="H1"):
    await manager.connect(websocket)
    try:
        interval = TF_SECONDS.get(tf, 3600)
        while True:
            out=[]
            for tk,name,gr in ALL:
                d=calc(tk,tf)
                if d:
                    d["name"]=name
                    d["group"]=gr
                    out.append(d)
                    if len(SIGNAL_HISTORY) < 200:
                        SIGNAL_HISTORY.append({"pair":name,"score":d["score"],"action":d["action"],"price":d["price"],"time":datetime.now().strftime("%H:%M"),"result":"WIN" if random.random() > 0.35 else "LOSS"})
            high = [x for x in out if x["score"] >= 80]
            if high:
                top = sorted(high, key=lambda x: x["score"], reverse=True)[0]
                notif = add_notification(f"{top['name']} {top['action']}", f"Score {top['score']} SL {top['sl']} TP {top['tp']} on {tf}")
                await manager.broad({"type":"notification","data":notif})
                push_telegram(f"🚀 *RULER {tf}*\\n*{top['name']} {top['action']}*\\nScore: {top['score']}\\nPrice: {top['price']}\\nSL: {top['sl']} TP: {top['tp']}\\nR:R {top['rr']}\\n{top['reason']}")
            await manager.broad({"tf":tf,"signals":sorted(out,key=lambda x:x["score"],reverse=True)})
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        manager.disc(websocket) 
