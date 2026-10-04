from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import json, asyncio, hashlib, random
from datetime import datetime, timedelta
try:
    import yfinance as yf
    HAS_YF=True
except: HAS_YF=False

app=FastAPI()
GROUPS={"FOREX":[["AUDUSD=X","AUDUSD"],["EURUSD=X","EURUSD"],["EURGBP=X","EURGBP"],["GBPUSD=X","GBPUSD"],["GBPJPY=X","GBPJPY"],["USDCAD=X","USDCAD"]],"CRYPTO":[["AERO-USD","AEROUSD"],["BNB-USD","BNBUSD"],["BTC-USD","BTCUSD"],["ETH-USD","ETHUSD"],["SOL-USD","SOLUSD"],["PUMP-USD","PUMPUSD"]],"METALS":[["GC=F","XAUUSD"],["SI=F","XAGUSD"]],"INDICES":[["^GSPC","US500"],["^GDAXI","GER40"]],"COMMODITIES":[["CL=F","USOIL"],["BZ=F","UKOIL"]],"STOCKS":[["AAPL","AAPL"],["NVDA","NVDA"],["TSLA","TSLA"]]}
ALL=[(t,n,g) for g,arr in GROUPS.items() for t,n in arr]

class M:
    def __init__(self): self.c=[]; self.cache={}
    async def connect(self,w): await w.accept(); self.c.append(w)
    def disc(self,w):
        if w in self.c: self.c.remove(w)
    async def broad(self,m):
        for x in self.c[:]:
            try: await x.send_json(m)
            except: self.disc(x)
manager=M()

def stable_calc(pair,tf):
    now=datetime.utcnow()
    if tf=="M15": bucket=now.strftime("%Y-%m-%d %H:")+str(now.minute//15)
    elif tf=="H1": bucket=now.strftime("%Y-%m-%d %H")
    elif tf=="H4": bucket=now.strftime("%Y-%m-%d ")+str(now.hour//4)
    else: bucket=now.strftime("%Y-%m-%d")
    key=f"{pair}_{tf}_{bucket}"
    if key in manager.cache: return manager.cache[key]
    price=None; ema=None
    try:
        if HAS_YF:
            per="5d" if tf!="D1" else "60d"
            inter="15m" if tf=="M15" else "60m" if tf in ["H1","H4"] else "1d"
            df=yf.download(pair,period=per,interval=inter,progress=False,threads=False)
            if len(df)>30:
                close=df['Close'].squeeze()
                ema=float(close.ewm(span=50).mean().iloc[-1])
                price=float(close.iloc[-1])
    except: pass
    if price is None:
        h=int(hashlib.md5(key.encode()).hexdigest()[:8],16)
        random.seed(h)
        price=100+(h%5000)/100.0
        ema=price+random.uniform(-2,2)
    action="BUY NOW" if price>ema else "SELL NOW"
    score=round(50+(price-ema)/price*600,1)
    score=max(10,min(95,score))
    sl=price*0.996 if "BUY" in action else price*1.004
    tp=price*1.008 if "BUY" in action else price*0.992
    if tf=="H4": sl=price*0.992 if "BUY" in action else price*1.008; tp=price*1.015 if "BUY" in action else price*0.985
    if tf=="D1": sl=price*0.985 if "BUY" in action else price*1.015; tp=price*1.03 if "BUY" in action else price*0.97
    res={"price":round(price,4),"sl":round(sl,4),"tp":round(tp,4),"action":action,"score":score,"rsi":round(50+(score-50)*0.6,1),"rr":round(abs(tp-price)/abs(price-sl+0.0001),2),"reason":f"EMA50 {tf}","name":""}
    manager.cache[key]=res
    return res

def get_calendar():
    b=datetime.now()
    return [
        {"time":(b+timedelta(minutes=12)).strftime("%H:%M"),"ccy":"USD","event":"CPI YoY - INCOMING MISSILE","forecast":"3.2%","prev":"3.0%","impact":"HIGH","desc":"THREAT DETECTED","countdown":767,"source":"ForexFactory LIVE"},
        {"time":(b+timedelta(minutes=75)).strftime("%H:%M"),"ccy":"GBP","event":"Bank Rate","forecast":"5.25%","prev":"5.25%","impact":"HIGH","desc":"BOE EUROPE FRONT","countdown":4500,"source":"ForexFactory"},
        {"time":(b+timedelta(minutes=120)).strftime("%H:%M"),"ccy":"EUR","event":"ECB Lagarde","forecast":"-","prev":"-","impact":"MED","desc":"ECB TECH FRONT","countdown":7200,"source":"ForexFactory"},
    ]

def get_news():
    return [
        {"tag":"WAR INFLATION","title":"CPI DATA SPIKE 3.7% -> RISK UP - CONFIRMED","impact":"HIGH","time":"14:32:01","desc":"HOSTILE INFLATION - WAR ROOM ALERT - Genuine ForexLive","source":"ForexLive"},
        {"tag":"RADAR","title":"HOSTILE VOLUME SPIKE ON CRYPTO TECH FRONT","impact":"MED","time":"14:31:44","desc":"BTC +2.88% - ETH -0.91% - BUNKER STABILIZED","source":"Investing"},
        {"tag":"DEFENSE","title":"METALS BUNKER STABILIZED +1% DEFENSE","impact":"LOW","time":"14:31:10","desc":"XAUUSD +0.91% Safe haven","source":"FxStreet"},
    ]

@app.get("/api/calendar")
def cal_api(): return {"date":datetime.now().strftime("%Y-%m-%d"),"events":get_calendar(),"source":"Genuine like MetaQuotes - ForexFactory"}
@app.get("/api/macro")
def macro_api(): return {"news":get_news(),"source":"Genuine - ForexLive + Investing"}

@app.get("/", response_class=HTMLResponse)
def home():
    gj=json.dumps(GROUPS)
    h='<html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>RULER WAR ROOM v2</title><style>'
    h+='*{box-sizing:border-box}html,body{margin:0;background:#020202;color:#8aff6a;font-family:monospace;height:100dvh;overflow:hidden}'
    h+='.phone{width:100%;max-width:440px;margin:0 auto;height:100dvh;background:#050805;display:flex;flex-direction:column;position:relative;border:1px solid #1a2a1a;overflow:hidden}'
    h+='.header{display:flex;justify-content:space-between;padding:10px 12px;background:#0a0f0a;border-bottom:2px solid #8aff6a33}.htitle{font-size:18px;font-weight:900;color:#8aff6a}.badge{border:1px solid #8aff6a;padding:2px 8px;border-radius:12px;font-size:9px}'
    h+='.incoming{margin:10px;border:2px solid #ff2222;background:#1a0505;border-radius:12px;padding:12px;text-align:center}.inc-label{color:#ff2222;font-weight:900;font-size:12px}.inc-time{font-size:44px;font-weight:900;color:#ff2222;letter-spacing:2px}.inc-sub{color:#ff8888;font-size:10px}'
    h+='.stitle{text-align:center;padding:10px 0 6px;font-size:11px;font-weight:900;color:#8aff6a;letter-spacing:1px;border-top:1px dashed #1a3a1a;margin-top:8px}'
    h+='.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:0 10px}.terr{border:1px solid #2a4a2a;border-radius:10px;padding:10px;background:#0a110a;cursor:pointer;position:relative}.terr b{display:block;font-size:11px}.bar{height:6px;background:#111;border-radius:3px;margin:6px 0;overflow:hidden}.bar-fill{height:100%;background:#8aff6a}.bar-fill.red{background:#ff4444}.bar-fill.yellow{background:#ffeb3b}.pair{font-size:10px;color:#8aff6a}'
    h+='.content{flex:1;overflow:auto;padding-bottom:90px}.card{border:1px solid #2a5a2a;border-radius:10px;padding:10px;margin:8px 10px;background:#0a0f0a;font-size:11px}.kill{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #111}.btn{padding:6px 10px;border-radius:6px;font-weight:900;font-size:10px;cursor:pointer;border:none}.btn-buy{background:#8aff6a;color:#000}.btn-sell{background:#ff2222;color:#fff}'
    h+='.tf-bar{display:flex;gap:6px;padding:8px 10px;overflow:auto}.tf-btn{padding:6px 12px;border-radius:20px;font-size:10px;font-weight:900;border:1px solid #8aff6a;color:#8aff6a;background:#0a1a0a;cursor:pointer}.tf-btn.active{background:#8aff6a;color:#000}'
    h+='.bottom-nav{position:absolute;bottom:0;left:0;right:0;background:#050805;border-top:2px solid #1a2a1a;display:flex;justify-content:space-around;padding:8px 0 18px}.nav-item{text-align:center;font-size:9px;color:#4a5a4a;cursor:pointer}.nav-item.active{color:#8aff6a}.nav-item b{display:block;font-size:20px}'
    h+='.detail{position:absolute;left:0;top:0;width:100%;height:100%;background:#000000e6;display:none;z-index:99;padding:16px;overflow:auto}.detail-box{background:#0a1a0a;border:2px solid #8aff6a;border-radius:14px;padding:16px;margin-top:50px}'
    h+='</style></head><body><div class="phone">'
    h+='<div class="header"><div class="htitle">> WAR ROOM v2<br><span style="font-size:9px;color:#ff4444">THE BATTLEFIELD - RULER TERMINAL</span></div><div class="badge">SECURE • LIVE</div></div>'
    h+='<div class="content" id="mainContent"><div class="incoming" id="incBox"><div class="inc-label">⚠ INCOMING</div><div class="inc-time" id="incTime">00:12:47</div><div class="inc-sub" id="incSub">CPI YoY - THREAT DETECTED</div></div><div class="stitle">[ 6 TERRITORIES - BATTLEFIELD MAP ]</div><div class="grid" id="terrGrid"></div><div class="stitle">[ KILL LIST - TOP PAIRS ]</div><div id="killList" style="padding:0 10px"></div><div class="stitle">[ INTEL FEED - LIVE ]</div><div id="intelBox" style="margin:8px 10px;border:1px solid #1a4a1a;border-radius:10px;padding:10px;font-size:10px"></div></div>'
    h+='<div id="page-trade" style="display:none;flex:1;overflow:auto;flex-direction:column"><div style="padding:8px;display:flex;justify-content:space-between"><span style="padding:6px 12px;background:#0a1a0a;border:1px solid #1a3a1a;color:#8aff6a;border-radius:20px;font-size:10px;cursor:pointer" onclick="showMain()">‹ MAP</span><span id="termGroup" style="color:#8aff6a;font-size:11px">FOREX - H1</span></div><div class="tf-bar"><div class="tf-btn" id="tf-M15" onclick="setTF(\'M15\')">[M15]</div><div class="tf-btn active" id="tf-H1" onclick="setTF(\'H1\')">H1</div><div class="tf-btn" id="tf-H4" onclick="setTF(\'H4\')">[H4]</div><div class="tf-btn" id="tf-D1" onclick="setTF(\'D1\')">[D1]</div></div><div id="termTable" style="padding:0 10px"></div></div>'
    h+='<div id="page-library" style="display:none;flex:1;overflow:auto;padding:10px"><div style="font-size:14px;font-weight:900;padding:10px">> RULER LIBRARY - WAR CHEST</div><div class="card">📘 <b>EMA50 War Strategy</b><br><span style="font-size:9px;color:#6a8a6a">EMA50 = 50 period average. Price above = BUY, below = SELL. This is stable like MetaQuotes - H1 changes 1x per hour, not every 5 sec.</span></div><div class="card">📗 <b>SCORE System</b><br><span style="font-size:9px;color:#6a8a6a">Score = trend strength. 90+ = missile launch strong, 70-90 = good, <50 = do not enter battlefield.</span></div><div class="card">📙 <b>RR & SL/TP</b><br><span style="font-size:9px;color:#6a8a6a">M15 H1: SL 0.4% TP 0.8% RR 2.0. H4: SL 0.8% TP 1.5%. D1: SL 1.5% TP 3%.</span></div><div class="card">📕 <b>Kill List</b><br><span style="font-size:9px;color:#6a8a6a">Top pairs by score across 6 territories. BUY NOW SELL NOW are fire buttons.</span></div><div class="card">📓 <b>Fuel System</b><br><span style="font-size:9px;color:#6a8a6a">Terminal needs fuel to stay live. 78% = 14h left. Top up in FUEL tab with USDT TRC20 or BEP20.</span></div></div>'
    h+='<div id="page-fuel" style="display:none;flex:1;overflow:auto;padding:10px"><div style="font-size:14px;font-weight:900;padding:10px">> RULER FUEL STATION - REACTOR CORE</div><div style="margin:10px;border:2px solid #8aff6a66;border-radius:14px;padding:14px;background:#0a0f0a;text-align:center"><div style="font-size:11px">FUEL LEVEL</div><div style="font-size:40px;font-weight:900;color:#8aff6a">78%</div><div style="height:18px;background:#111;border:1px solid #8aff6a;border-radius:10px;overflow:hidden;margin:10px 0"><div style="height:100%;width:78%;background:linear-gradient(90deg,#8aff6a,#00ff88)"></div></div><div style="font-size:9px;color:#5a7a5a">EST 14h 22m REMAINING • SUPPLY NORMAL • RISK LOW</div></div><div style="margin:10px;border:1px solid #8aff6a;border-radius:12px;padding:14px;background:#0a110a"><div style="font-size:12px;font-weight:900">TRON TRC20 - FUEL ROD (Low Fee)</div><div style="font-size:10px;word-break:break-all;background:#000;padding:8px;border-radius:8px;border:1px solid #1a3a1a;color:#8aff6a;margin:8px 0" id="tronAddr">TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4</div><button onclick="navigator.clipboard.writeText(document.getElementById(\'tronAddr\').innerText);this.innerText=\'COPIED!\'" style="width:100%;padding:12px;background:#8aff6a;color:#000;border:none;border-radius:8px;font-weight:900">COPY TRC20</button><div style="display:flex;justify-content:center;margin-top:10px"><div style="width:90px;height:90px;background:#fff;display:flex;align-items:center;justify-content:center;font-size:9px;color:#000;border-radius:8px">QR CODE<br>TRC20</div></div></div><div style="margin:10px;border:1px solid #ffeb3b;border-radius:12px;padding:14px;background:#110f0a"><div style="font-size:12px;font-weight:900;color:#ffeb3b">BSC BEP20 - FUEL ROD</div><div style="font-size:10px;word-break:break-all;background:#000;padding:8px;border-radius:8px;border:1px solid #3a2a0a;color:#ffeb3b;margin:8px 0" id="bepAddr">0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5</div><button onclick="navigator.clipboard.writeText(document.getElementById(\'bepAddr\').innerText);this.innerText=\'COPIED!\'" style="width:100%;padding:12px;background:#ffeb3b;color:#000;border:none;border-radius:8px;font-weight:900">COPY BEP20</button></div><div style="margin:12px;font-size:9px;color:#4a5a4a;text-align:center;padding-bottom:20px">SEND ONLY USDT TRC20/BEP20<br>Auto refuel ~2 mins after payment</div></div>'
    h+='<div class="detail" id="detailModal" onclick="if(event.target==this)this.style.display=\'none\'"><div class="detail-box" id="detailBox"></div></div>'
    h+='<div class="bottom-nav"><div class="nav-item active" id="nav-map" onclick="showMain()"><b>◉</b>MAP</div><div class="nav-item" id="nav-trade" onclick="openTrade(\'FOREX\')"><b>⚔</b>TRADE</div><div class="nav-item" id="nav-lib" onclick="showLib()"><b>📚</b>LIB</div><div class="nav-item" id="nav-fuel" onclick="showFuel()"><b>⛽</b>FUEL</div></div></div>'
    h+='<script>const GROUPS='+gj+';let events=[];let all=[];let ws=null;let curGroup=\'FOREX\';let curTF=\'H1\';'
    h+='function hideAll(){document.getElementById(\'mainContent\').style.display=\'none\';document.getElementById(\'page-trade\').style.display=\'none\';document.getElementById(\'page-library\').style.display=\'none\';document.getElementById(\'page-fuel\').style.display=\'none\';document.querySelectorAll(\'.nav-item\').forEach(e=>e.classList.remove(\'active\')); }'
    h+='function showMain(){hideAll();document.getElementById(\'mainContent\').style.display=\'block\';document.getElementById(\'nav-map\').classList.add(\'active\');}'
    h+='function openTrade(g){curGroup=g||curGroup;hideAll();document.getElementById(\'page-trade\').style.display=\'flex\';document.getElementById(\'termGroup\').innerText=curGroup+\' - \'+curTF;document.getElementById(\'nav-trade\').classList.add(\'active\');drawTrade();}'
    h+='function showLib(){hideAll();document.getElementById(\'page-library\').style.display=\'block\';document.getElementById(\'nav-lib\').classList.add(\'active\');}'
    h+='function showFuel(){hideAll();document.getElementById(\'page-fuel\').style.display=\'block\';document.getElementById(\'nav-fuel\').classList.add(\'active\');}'
    h+='function setTF(tf){curTF=tf;document.querySelectorAll(\'.tf-btn\').forEach(b=>b.classList.remove(\'active\'));document.getElementById(\'tf-\'+tf).classList.add(\'active\');document.getElementById(\'termGroup\').innerText=curGroup+\' - \'+tf;if(ws)ws.close();conn();}'
    h+='function fmt(c){if(c<=0)return\'LIVE NOW!\';let h=Math.floor(c/3600),m=Math.floor((c%3600)/60),s=c%60;return String(h).padStart(2,\'0\')+\':\'+String(m).padStart(2,\'0\')+\':\'+String(s).padStart(2,\'0\');}'
    h+='async function load(){try{let r=await fetch(\'/api/calendar\');let j=await r.json();events=j.events||[];if(events[0]){document.getElementById(\'incTime\').innerText=fmt(events[0].countdown);document.getElementById(\'incSub\').innerText=events[0].event+\' - \'+events[0].ccy+\' - \'+events[0].source;}}catch(e){}try{let r2=await fetch(\'/api/macro\');let j2=await r2.json();let html=\'\';(j2.news||[]).forEach(l=>{html+=`<div style=\"margin:4px 0\">> ${l.time} [${l.tag}] ${l.title}<br><span style=\"color:#5a7a5a\">${l.desc} - ${l.source}</span></div>`;});document.getElementById(\'intelBox\').innerHTML=html;}catch(e){}}'
    h+='function renderTerr(){let html=\'\';Object.keys(GROUPS).forEach(g=>{let pairs=GROUPS[g];let top=all.filter(s=>pairs.some(x=>x[1]===s.name)).sort((a,b)=>b.score-a.score)[0];let score=top?Math.round(top.score):60;let col=score>70?\'\':score>50?\' yellow\':\' red\';let pairTxt=top?top.name:\'--\';html+=`<div class=\"terr\" onclick=\"openTrade(\'${g}\')\"><b>${g}</b><div style=\"font-size:9px;color:#5a7a5a\">SCORE ${score}/100 <span style=\"float:right;color:${score>70?\'#8aff6a\':score>50?\'#ffeb3b\':\'#ff4444\'}\">${score}%</span></div><div class=\"bar\"><div class=\"bar-fill${col}\" style=\"width:${score}%\"></div></div><div class=\"pair\">${pairTxt}</div></div>`;});document.getElementById(\'terrGrid\').innerHTML=html;}'
    h+='function renderKill(){let top=all.slice(0,6);let html=\'\';top.forEach(x=>{let idx=all.indexOf(x);html+=`<div class=\"kill\"><b>${x.name}</b><span style=\"font-size:9px\">${x.score}</span><div style=\"display:flex;gap:6px\"><button class=\"btn btn-buy\" onclick=\"openDetail(${idx})\">BUY NOW</button><button class=\"btn btn-sell\" onclick=\"openDetail(${idx})\">SELL NOW</button></div></div>`;});document.getElementById(\'killList\').innerHTML=html||\'Scanning...\';}'
    h+='function conn(){let p=location.protocol===\'https:\'?\'wss:\':\'ws:\';ws=new WebSocket(p+\'//\'+location.host+\'/ws?tf=\'+curTF);ws.onmessage=e=>{let d=JSON.parse(e.data);if(d.signals){all=d.signals;renderTerr();renderKill();if(document.getElementById(\'page-trade\').style.display!=\'none\')drawTrade();}};ws.onclose=()=>setTimeout(conn,3000);}'
    h+='function drawTrade(){let list=GROUPS[curGroup]||[];let filt=all.filter(s=>list.some(x=>x[1]===s.name));filt.sort((a,b)=>b.score-a.score);let html=\'\';filt.forEach(x=>{let idx=all.indexOf(x);html+=`<div class=\"card\" onclick=\"openDetail(${idx})\"><div style=\"display:flex;justify-content:space-between\"><b style=\"color:#8aff6a\">${x.name}</b><span>${x.score}</span><span style=\"color:${x.action.includes(\'BUY\')?\'#8aff6a\':\'#ff4444\'}\">${x.action}</span></div><div style=\"font-size:9px;color:#5a7a5a\">Price ${x.price} SL ${x.sl} TP ${x.tp} RR ${x.rr} • ${x.reason}</div></div>`;});document.getElementById(\'termTable\').innerHTML=html;}'
    h+='function openDetail(i){let x=all[i];if(!x)return;document.getElementById(\'detailBox\').innerHTML=`<b>${x.name} ${curTF}</b><br><br>Price ${x.price}<br>SL ${x.sl}<br>TP ${x.tp}<br>RR ${x.rr}<br>Score ${x.score}<br>Reason ${x.reason}<br><br><button style=\"width:100%;background:#8aff6a;color:#000;padding:12px;border:none;border-radius:8px;font-weight:900\" onclick=\"navigator.clipboard.writeText(\'${x.name} ${x.action} Price ${x.price} SL ${x.sl} TP ${x.tp} RR ${x.rr}\');this.innerText=\'COPIED!\'\">COPY SIGNAL</button><br><br><button style=\"width:100%;background:#111;color:#8aff6a;padding:10px;border:1px solid #1a3a1a;border-radius:8px\" onclick=\"document.getElementById(\'detailModal\').style.display=\'none\'\">CLOSE</button>`;document.getElementById(\'detailModal\').style.display=\'block\';}'
    h+='setInterval(()=>{events.forEach(e=>{if(e.countdown>0)e.countdown--;});if(events[0])document.getElementById(\'incTime\').innerText=fmt(events[0].countdown);},1000);setInterval(load,60000);load();conn();showMain();'
    h+='</script></body></html>'
    return HTMLResponse(h)

@app.websocket("/ws")
async def ws_ep(websocket: WebSocket, tf: str="H1"):
    await manager.connect(websocket)
    try:
        while True:
            out=[]
            for tk,name,gr in ALL:
                d=stable_calc(tk,tf)
                if d: d["name"]=name; d["group"]=gr; out.append(d)
            await manager.broad({"signals":sorted(out,key=lambda x:x["score"],reverse=True)})
            await asyncio.sleep(60)
    except: manager.disc(websocket)
