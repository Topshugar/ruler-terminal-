from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import yfinance as yf, json, asyncio

app = FastAPI()

GROUPS = {
    "COMMODITIES": [["CL=F","USOIL"], ["BZ=F","UKOIL"]],
    "CRYPTO": [["BTC-USD","BTCUSD"], ["ETH-USD","ETHUSD"]],
    "FOREX": [["AUDUSD=X","AUDUSD"], ["EURUSD=X","EURUSD"], ["GBPUSD=X","GBPUSD"], ["USDJPY=X","USDJPY"], ["USDCAD=X","USDCAD"], ["USDCHF=X","USDCHF"], ["NZDUSD=X","NZDUSD"], ["EURJPY=X","EURJPY"], ["GBPJPY=X","GBPJPY"]],
    "INDICES": [["^GSPC","US500"], ["^DJI","US30"]],
    "METALS": [["GC=F","XAUUSD"], ["SI=F","XAGUSD"]],
    "STOCKS": [["AAPL","AAPL"], ["TSLA","TSLA"]]
}
ALL = [(t,n,g) for g,arr in GROUPS.items() for t,n in arr]

USDT_TRC20 = "TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4"
USDT_BEP20 = "0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5"

TF_SECONDS = {"M15":900, "H1":3600, "H4":14400, "D1":86400}

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
        per="5d" if tf!="D1" else "100d"
        inter="15m" if tf=="M15" else "60m" if tf!="D1" else "1d"
        df=yf.download(pair,period=per,interval=inter,progress=False)
        if len(df)<30: return None
        close=df['Close'].squeeze()
        ema=close.ewm(span=50).mean().iloc[-1]
        price=float(close.iloc[-1])
        action="BUY" if price>ema else "SELL"
        score=round(50 + (price-ema)/price*500,1)
        score=max(5,min(95,score))
        return {"price":round(price,5),"action":action,"score":score,"sl":round(price*0.998,5),"tp":round(price*1.002,5),"rsi_text":"FRESH","rsi_color":"#00ff88","name":""}
    except: return None

@app.get("/", response_class=HTMLResponse)
def home():
    groups_json = json.dumps(GROUPS)
    return HTMLResponse(f"""
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RULER</title>
<style>
body{{background:#070a0f;color:#e6e6e6;font-family:monospace;margin:0;display:flex;height:100vh;overflow:hidden}}
.sidebar{{width:180px;min-width:180px;background:#0b0f1a;border-right:1px solid #1a233a;padding:10px;overflow-y:auto;transition:transform 0.3s}}
.main{{flex:1;padding:12px;overflow:auto;background:#070a0f;position:relative}}
.group{{padding:10px;border:1px solid #1a233a;border-radius:8px;margin:6px 0;cursor:pointer;font-size:11px;color:#8892b0}}
.group.active{{border-color:#c9a227;color:#c9a227;background:#0f1a2f;font-weight:bold}}
.live{{color:#00ff88;animation:blink 1s infinite}}@keyframes blink{{50%{{opacity:.3}}}}
table{{width:100%;border-collapse:collapse;margin-top:10px}}th{{color:#5a6a8a;font-size:10px;text-align:left;padding:6px;border-bottom:1px solid #1a233a}}td{{padding:8px 6px;border-bottom:1px solid #121a2b;font-size:12px;white-space:nowrap}}
.tf{{padding:6px 12px;border:1px solid #1a233a;border-radius:20px;cursor:pointer;font-size:11px;color:#888}}.tf.active{{background:#c9a227;color:#000;font-weight:900}}
#backBtn{{display:none;align-items:center;gap:6px;background:#0f1a2f;border:1px solid #1a233a;padding:8px 12px;border-radius:20px;font-size:12px;cursor:pointer;color:#c9a227;margin-bottom:10px}}
#intro{{position:fixed;inset:0;background:#070a0f;z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px}}
.box{{max-width:480px;background:#0f1a2f;border:1px solid #c9a227;border-radius:16px;padding:20px}}
#fuelAd{{position:fixed;left:-360px;bottom:20px;width:320px;background:#111a2f;border:1px solid #00ff88;border-radius:0 14px 14px 0;padding:12px;transition:left 0.7s;z-index:6000}}
#fuelAd.show{{left:0}}

/* MOBILE FIT */
@media(max-width:768px){{
  body{{flex-direction:column}}
 .sidebar{{width:100%;min-width:100%;height:100vh;position:fixed;left:0;top:0;z-index:5000;transform:translateX(0)}}
 .sidebar.hide{{transform:translateX(-100%)}}
 .main{{width:100%;height:100vh}}
  #backBtn{{display:flex}}
  table{{font-size:11px}}
}}
</style></head><body>

<div id="intro"><div class="box">
<h2 style="color:#c9a227;text-align:center">RULER TERMINAL</h2>
<p style="text-align:center;color:#8892b0;font-size:10px;letter-spacing:2px">CENTRAL BANK GRADE</p>
<p style="font-size:13px;line-height:1.5">RULER is your confirmation ruler. Scan markets by candle time.<br><br>
<b>M15</b> updates every 15 mins, <b>H1</b> every 1 hour, <b>H4</b> every 4 hours, <b>D1</b> daily.<br>
Use it with your own chart to confirm price.<br><br>
No rush. Follow TOP score.</p>
<button onclick="localStorage.setItem('seen','1');document.getElementById('intro').style.display='none'" style="width:100%;padding:12px;background:#c9a227;border:none;border-radius:10px;font-weight:900">ENTER TERMINAL</button>
</div></div>

<div class="sidebar" id="sidebar">
<div style="display:flex;justify-content:space-between;align-items:center">
<div style="color:#c9a227;font-weight:900;font-size:12px;letter-spacing:1px">MARKETS</div>
<span style="font-size:10px;color:#555">A-Z</span>
</div>
<div id="gs" style="margin-top:10px"></div>
<button onclick="document.getElementById('sheet').style.transform='translateY(0)'" style="margin-top:20px;width:100%;padding:10px;background:#00ff88;border:none;border-radius:10px;font-weight:bold">💚 FUEL</button>
</div>

<div class="main" id="main">
<div id="backBtn" onclick="showMarkets()">‹ MARKETS</div>
<h3 style="margin:0;display:flex;align-items:center;gap:8px;flex-wrap:wrap">RULER <span class="live">● LIVE</span> <span id="tm" style="font-size:10px;color:#666"></span></h3>
<div style="display:flex;gap:6px;margin:10px 0;overflow-x:auto"><span class="tf" id="tf_M15" onclick="setTF('M15')">M15</span><span class="tf" id="tf_H1" onclick="setTF('H1')">H1</span><span class="tf" id="tf_H4" onclick="setTF('H4')">H4</span><span class="tf" id="tf_D1" onclick="setTF('D1')">D1</span></div>
<div style="color:#5a6a8a;font-size:10px">Update matches candle. M15=15m • H1=1h • H4=4h • D1=1d — use with your chart for confirmation.</div>
<div id="t">Loading live...</div>
</div>

<div id="fuelAd"><div style="display:flex;justify-content:space-between"><b style="color:#00ff88">⚡ FUEL RULER</b><span onclick="this.parentElement.parentElement.classList.remove('show')" style="cursor:pointer">✕</span></div><p style="font-size:11px;color:#aaa">Keep server alive. 1 USDT = 1 day.</p>
<div style="display:flex;gap:6px;margin-top:8px">
<a href="trust://send?coin=195&address={USDT_TRC20}" style="flex:1;background:#00ff88;color:#000;text-align:center;padding:10px;border-radius:8px;text-decoration:none;font-weight:900;font-size:11px">PAY TRC20</a>
<a href="https://link.trustwallet.com/send?coin=60&address={USDT_BEP20}" style="flex:1;background:#ffcc00;color:#000;text-align:center;padding:10px;border-radius:8px;text-decoration:none;font-weight:900;font-size:11px">PAY BEP20</a>
</div></div>

<div id="sheet" style="position:fixed;bottom:0;left:0;width:100%;background:#0f1a2f;border-top:2px solid #c9a227;border-radius:18px 18px 0 0;transform:translateY(100%);transition:0.4s;z-index:8000;padding:16px;max-height:80vh;overflow:auto">
<div style="display:flex;justify-content:space-between"><h3 style="color:#c9a227;margin:0">FUEL</h3><span onclick="document.getElementById('sheet').style.transform='translateY(100%)'" style="cursor:pointer">✕</span></div>
<div style="text-align:center;margin-top:12px;background:#070a0f;padding:12px;border-radius:12px">
<p style="font-size:11px;color:#00ff88">TRC20</p><p style="font-size:8px;word-break:break-all">{USDT_TRC20}</p>
<img src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={USDT_TRC20}" style="border:5px solid white;border-radius:8px"><br>
<a href="trust://send?coin=195&address={USDT_TRC20}" style="display:inline-block;margin-top:8px;background:#00ff88;color:#000;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:900">OPEN IN TRUST WALLET</a>
</div>
<div style="text-align:center;margin-top:12px;background:#070a0f;padding:12px;border-radius:12px">
<p style="font-size:11px;color:#ffcc00">BEP20</p><p style="font-size:8px;word-break:break-all">{USDT_BEP20}</p>
<img src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={USDT_BEP20}" style="border:5px solid white;border-radius:8px"><br>
<a href="https://link.trustwallet.com/send?coin=60&address={USDT_BEP20}" style="display:inline-block;margin-top:8px;background:#ffcc00;color:#000;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:900">OPEN IN BINANCE</a>
</div>
</div>

<script>
const GROUPS = {groups_json};
const TF_SEC = {json.dumps(TF_SECONDS)};
let curG = localStorage.getItem('ruler_group')||'FOREX';
let curTF = localStorage.getItem('ruler_tf')||'H1';
let all=[]; let ws=null; let last=Date.now(); let nextUpdate=Date.now()+TF_SEC[curTF]*1000;
if(localStorage.getItem('seen')) document.getElementById('intro').style.display='none';

function isMobile(){{return window.innerWidth<=768;}}
function drawGroups(){{
  let h=''; Object.keys(GROUPS).sort().forEach(g=>{{ h+=`<div class="group ${{g===curG?'active':''}}" onclick="selG('${{g}}')">${{g}} <span style="float:right">${{GROUPS[g].length}}</span></div>`; }});
  document.getElementById('gs').innerHTML=h;
}}
function selG(g){{
  curG=g; localStorage.setItem('ruler_group',g); drawGroups(); draw();
  if(isMobile()){{ document.getElementById('sidebar').classList.add('hide'); }}
}}
function showMarkets(){{ document.getElementById('sidebar').classList.remove('hide'); }}
function setTF(tf){{
  curTF=tf; localStorage.setItem('ruler_tf',tf);
  document.querySelectorAll('.tf').forEach(e=>e.classList.remove('active'));
  document.getElementById('tf_'+tf).classList.add('active');
  nextUpdate=Date.now()+TF_SEC[tf]*1000;
  if(ws) ws.close(); conn();
}}
function conn(){{
  let proto=location.protocol==='https:'?'wss:':'ws:';
  ws=new WebSocket(proto+'//'+location.host+'/ws?tf='+curTF);
  ws.onmessage=(e)=>{{let d=JSON.parse(e.data); all=d.signals; last=Date.now(); nextUpdate=Date.now()+TF_SEC[d.tf]*1000; draw();}};
  ws.onclose=()=>setTimeout(conn,3000);
}}
function draw(){{
  let list=GROUPS[curG]||[]; let filt=all.filter(s=>list.some(x=>x[1]===s.name)); filt.sort((a,b)=>b.score-a.score);
  let h=`<div style="color:#5a6a8a;font-size:11px;margin:8px 0">${{curG}} • ${{filt.length}} pairs • Next update in <span id="cd"></span></div><table><tr><th>PAIR</th><th>SCORE</th><th>ACTION</th><th>PRICE</th><th>SL</th><th>TP</th></tr>`;
  filt.forEach(x=>{{let c=x.score>60?'#00ff88':x.score>45?'#ffcc00':'#888'; h+=`<tr><td>${{x.name}}</td><td style="color:${{c}};font-weight:bold">${{x.score}}</td><td>${{x.action}}</td><td>${{x.price}}</td><td style="color:#f44">${{x.sl}}</td><td style="color:#0f8">${{x.tp}}</td></tr>`;}});
  h+='</table>'; document.getElementById('t').innerHTML=h;
}}
function showAd(){{document.getElementById('fuelAd').classList.add('show'); setTimeout(()=>document.getElementById('fuelAd').classList.remove('show'),5000);}}
setTimeout(showAd,4000); setInterval(showAd,30000);
setInterval(()=>{{
  let s=Math.floor((Date.now()-last)/1000);
  let left=Math.max(0, Math.floor((nextUpdate-Date.now())/1000));
  let m=Math.floor(left/60); let sc=left%60;
  let cd=document.getElementById('cd'); if(cd) cd.innerText=m+'m '+sc+'s';
  document.getElementById('tm').innerText='Live '+s+'s ago • TF:'+curTF+' • Next:'+m+'m';
}},1000);
drawGroups(); document.getElementById('tf_'+curTF).classList.add('active'); conn();
if(isMobile()){{}} // start with markets visible on mobile
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
                    d["name"]=name; d["group"]=gr; out.append(d)
            await manager.broad({"tf":tf,"signals":sorted(out,key=lambda x:x["score"],reverse=True)})
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        manager.disc(websocket) 
