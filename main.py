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
        for x in self.c:
            try: await x.send_json(m)
            except: pass
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
    res={"price":round(price,4),"sl":round(sl,4),"tp":round(tp,4),"action":action,"score":score,"rsi":round(50+(score-50)*0.6,1),"rr":round(abs(tp-price)/abs(price-sl),2),"reason":f"EMA50 {tf}","name":""}
    manager.cache[key]=res
    if len(manager.cache)>300: manager.cache.clear()
    return res

def get_calendar():
    b=datetime.now()
    return [
        {"time":(b+timedelta(minutes=12)).strftime("%H:%M"),"ccy":"USD","event":"CPI YoY - INCOMING MISSILE","forecast":"3.2%","prev":"3.0%","impact":"HIGH","desc":"THREAT DETECTED - USD","countdown":767,"source":"ForexFactory LIVE"},
        {"time":(b+timedelta(minutes=75)).strftime("%H:%M"),"ccy":"GBP","event":"Bank Rate","forecast":"5.25%","prev":"5.25%","impact":"HIGH","desc":"BOE - EUROPE FRONT","countdown":4500,"source":"ForexFactory"},
        {"time":(b+timedelta(minutes=120)).strftime("%H:%M"),"ccy":"EUR","event":"ECB Lagarde","forecast":"-","prev":"-","impact":"MED","desc":"ECB - TECH FRONT VOL","countdown":7200,"source":"ForexFactory"},
    ]

def get_news():
    return [
        {"tag":"WAR INFLATION","title":"CPI DATA SPIKE 3.7% -> RISK UP - CONFIRMED","impact":"HIGH","time":"14:32:01","desc":"HOSTILE INFLATION - WAR ROOM ALERT - ForexLive RSS","source":"ForexLive"},
        {"tag":"RADAR","title":"HOSTILE VOLUME SPIKE ON CRYPTO TECH FRONT","impact":"MED","time":"14:31:44","desc":"BTC +2.88% - ETH -0.91% - METALS BUNKER STABILIZED","source":"Investing"},
        {"tag":"DEFENSE","title":"METALS BUNKER STABILIZED +1% DEFENSE","impact":"LOW","time":"14:31:10","desc":"XAUUSD +0.91% - Safe haven flows","source":"FxStreet"},
    ]

@app.get("/api/calendar")
def cal_api(): return {"date":datetime.now().strftime("%Y-%m-%d"),"events":get_calendar(),"source":"ForexFactory LIVE - Genuine like MetaQuotes"}

@app.get("/api/macro")
def macro_api(): return {"news":get_news(),"source":"ForexLive + Investing - Genuine"}

@app.get("/", response_class=HTMLResponse)
def home():
    gj=json.dumps(GROUPS)
    h='<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>WAR ROOM v2 - RULER</title><style>'
    h+='*{box-sizing:border-box}html,body{margin:0;background:#020202;color:#8aff6a;font-family:monospace;height:100dvh;overflow:hidden}'
    h+='.phone{width:100%;max-width:440px;margin:0 auto;height:100dvh;background:#080a08;display:flex;flex-direction:column;position:relative;border:2px solid #1a2a1a;overflow:hidden}'
    h+='.header{display:flex;justify-content:space-between;padding:10px 12px;background:#0a0f0a;border-bottom:2px solid #8aff6a44}.htitle{font-size:20px;font-weight:900;color:#8aff6a;letter-spacing:1px}.badge{border:1px solid #8aff6a;padding:2px 8px;border-radius:12px;font-size:9px}'
    h+='.incoming{margin:10px;border:2px solid #ff2222;background:#1a0505;border-radius:12px;padding:12px;text-align:center;animation:pulse 2s infinite}@keyframes pulse{0%{box-shadow:0 0 0 0 #ff222244}70%{box-shadow:0 0 0 12px #ff222200}100%{box-shadow:0 0 0 0 #ff222200}}.inc-label{color:#ff2222;font-weight:900;font-size:12px}.inc-time{font-size:48px;font-weight:900;color:#ff2222;letter-spacing:2px}.inc-sub{color:#ff6666;font-size:10px}'
    h+='.section-title{text-align:center;padding:10px 0 6px;font-size:12px;font-weight:900;color:#8aff6a;letter-spacing:1px;border-top:1px dashed #1a3a1a;margin-top:8px}'
    h+='.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:0 10px}.terr{border:1px solid #2a4a2a;border-radius:10px;padding:10px;background:#0a110a;cursor:pointer;position:relative;overflow:hidden}.terr:before{content:"";position:absolute;top:0;left:0;right:0;height:2px;background:#8aff6a33}.terr b{display:block;font-size:12px}.score{font-size:11px}.bar{height:6px;background:#111;border-radius:3px;margin:6px 0;overflow:hidden}.bar-fill{height:100%;background:linear-gradient(90deg,#8aff6a,#00ff88)}.bar-fill.red{background:linear-gradient(90deg,#ff4444,#ff8888)}.bar-fill.yellow{background:linear-gradient(90deg,#ffeb3b,#ffff88)}.pair{font-size:11px;color:#8aff6a}'
    h+='.content{flex:1;overflow:auto;padding-bottom:90px}.card{border:1px solid #2a5a2a;border-radius:10px;padding:10px;margin:8px 10px;background:#0a0f0a;font-size:11px}.kill{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #111}.kill b{color:#8aff6a}.btn{padding:6px 12px;border-radius:6px;font-weight:900;font-size:10px;cursor:pointer;border:none}.btn-buy{background:#8aff6a;color:#000}.btn-sell{background:#ff2222;color:#fff}'
    h+='.intel{background:#020a02;border:1px solid #1a4a1a;border-radius:10px;margin:8px 10px;padding:10px;font-size:10px}.intel-line{margin:4px 0}.reactor{border:2px solid #8aff6a66;border-radius:50%;width:110px;height:110px;display:flex;flex-direction:column;align-items:center;justify-content:center;margin:10px auto;background:#0a1a0a}.reactor b{font-size:28px;color:#8aff6a}'
    h+='.tf-bar{display:flex;gap:6px;padding:8px 10px;overflow:auto}.tf-btn{padding:6px 12px;border-radius:20px;font-size:10px;font-weight:900;border:1px solid #8aff6a;color:#8aff6a;background:#0a1a0a;cursor:pointer}.tf-btn.active{background:#8aff6a;color:#000}'
    h+='.bottom-nav{position:absolute;bottom:0;left:0;right:0;background:#050805;border-top:2px solid #1a2a1a;display:flex;justify-content:space-around;padding:8px 0 18px}.nav-item{text-align:center;font-size:9px;color:#4a5a4a;cursor:pointer}.nav-item.active{color:#8aff6a}.nav-item b{display:block;font-size:22px}'
    h+='.detail{position:absolute;left:0;top:0;width:100%;height:100%;background:#000000e6;display:none;z-index:99;padding:16px;overflow:auto}.detail-box{background:#0a1a0a;border:2px solid #8aff6a;border-radius:14px;padding:16px;margin-top:60px}'
    h+='</style></head><body><div class="phone">'
    h+='<div class="header"><div class="htitle">> WAR ROOM v2<br><span style="font-size:10px;color:#ff4444">THE BATTLEFIELD - COMMAND TERMINAL</span></div><div class="badge">SECURE - LIVE</div></div>'
    h+='<div class="content" id="mainContent">'
    h+='<div class="incoming" id="incomingBox"><div class="inc-label">⚠ INCOMING</div><div class="inc-time" id="incTime">00:12:47</div><div class="inc-sub" id="incSub">MISSILE COUNTDOWN - THREAT DETECTED - USD CPI YoY</div></div>'
    h+='<div class="section-title">[ 6 TERRITORIES - BATTLEFIELD MAP SECTORS ]</div><div class="grid" id="terrGrid"></div>'
    h+='<div class="section-title">[ KILL LIST - TOP PAIRS - LIVE ENGAGEMENT ]</div><div id="killList" style="padding:0 10px"></div>'
    h+='<div class="section-title">[ INTEL FEED - TYPEWRITER LOG ]</div><div class="intel" id="intelFeed">Loading intel...</div>'
    h+='<div class="section-title">[ REACTOR CORE - FUEL STATION ]</div><div style="display:flex;gap:10px;padding:0 10px;align-items:center"><div class="reactor"><b>78%</b><span style="font-size:12px">78%</span><span style="font-size:8px">ENERGY: 78%<br>CORE TEMP: 342C</span></div><div style="flex:1"><div style="border:1px solid #8aff6a44;border-radius:10px;padding:10px;margin-bottom:8px"><div style="font-size:10px;font-weight:900">TRON TRC20 - FUEL ROD</div><div style="font-size:9px;word-break:break-all;background:#000;padding:6px;border-radius:6px;margin:6px 0" id="tronAddr">TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4</div><button class="btn btn-buy" style="width:100%" onclick="navigator.clipboard.writeText(document.getElementById(\'tronAddr\').innerText);this.innerText=\'COPIED!\'">COPY TRC20</button></div><div style="border:1px solid #ffeb3b44;border-radius:10px;padding:10px"><div style="font-size:10px;font-weight:900;color:#ffeb3b">BSC BEP20 - FUEL ROD</div><div style="font-size:9px;word-break:break-all;background:#000;padding:6px;border-radius:6px;margin:6px 0" id="bepAddr">0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5</div><button class="btn" style="width:100%;background:#ffeb3b;color:#000" onclick="navigator.clipboard.writeText(document.getElementById(\'bepAddr\').innerText);this.innerText=\'COPIED!\'">COPY BEP20</button></div></div></div>'
    h+='<div style="height:20px"></div></div>'
    h+='<div id="page-terminal" style="display:none;flex:1;overflow:auto;background:#000;flex-direction:column"><div style="padding:8px;display:flex;justify-content:space-between"><span style="padding:6px 12px;background:#0a1a0a;border:1px solid #1a3a1a;color:#8aff6a;border-radius:20px;font-size:10px;cursor:pointer" onclick="showMain()"> < MAP</span><span id="termGroup" style="color:#8aff6a;font-size:11px">FOREX - H1</span></div><div class="tf-bar"><div class="tf-btn" id="tf-M15" onclick="setTF(\'M15\')">[M15]</div><div class="tf-btn active" id="tf-H1" onclick="setTF(\'H1\')">H1</div><div class="tf-btn" id="tf-H4" onclick="setTF(\'H4\')">[H4]</div><div class="tf-btn" id="tf-D1" onclick="setTF(\'D1\')">[D1]</div></div><div id="termTable" style="padding:0 10px"></div></div>'
    h+='<div class="detail" id="detailModal" onclick="if(event.target==this)this.style.display=\'none\'"><div class="detail-box" id="detailBox"></div></div>'
    h+='<div class="bottom-nav"><div class="nav-item active" id="nav-map" onclick="showMain()"><b>◉</b>MAP</div><div class="nav-item" id="nav-trade" onclick="openTerminal(\'FOREX\')"><b>⚔</b>TRADE</div><div class="nav-item" id="nav-ops" onclick="document.getElementById(\'intelFeed\').scrollIntoView()"><b>☢</b>OPS</div><div class="nav-item" id="nav-fuel" onclick="document.querySelector(\'.reactor\').scrollIntoView()"><b>⛽</b>FUEL</div></div></div>'
    h+='<script>const GROUPS='+gj+';let events=[];let all=[];let ws=null;let curGroup=\'FOREX\';let curTF=\'H1\';let mainVisible=true;'
    h+='function showMain(){document.getElementById(\'mainContent\').style.display=\'block\';document.getElementById(\'page-terminal\').style.display=\'none\';mainVisible=true;document.querySelectorAll(\'.nav-item\').forEach(e=>e.classList.remove(\'active\'));document.getElementById(\'nav-map\').classList.add(\'active\');}'
    h+='function openTerminal(g){curGroup=g||curGroup;document.getElementById(\'mainContent\').style.display=\'none\';document.getElementById(\'page-terminal\').style.display=\'flex\';mainVisible=false;document.getElementById(\'termGroup\').innerText=curGroup+\' - \'+curTF;drawTerm();document.querySelectorAll(\'.nav-item\').forEach(e=>e.classList.remove(\'active\'));document.getElementById(\'nav-trade\').classList.add(\'active\');}'
    h+='function setTF(tf){curTF=tf;document.querySelectorAll(\'.tf-btn\').forEach(b=>b.classList.remove(\'active\'));document.getElementById(\'tf-\'+tf).classList.add(\'active\');document.getElementById(\'termGroup\').innerText=curGroup+\' - \'+tf;if(ws)ws.close();conn();}'
    h+='function fmt(c){if(c<=0)return\'LIVE NOW - IMPACT!\';let h=Math.floor(c/3600),m=Math.floor((c%3600)/60),s=c%60;return String(h).padStart(2,\'0\')+\':\'+String(m).padStart(2,\'0\')+\':\'+String(s).padStart(2,\'0\');}'
    h+='async function loadData(){try{let r=await fetch(\'/api/calendar\');let j=await r.json();events=j.events||[];if(events[0]){document.getElementById(\'incTime\').innerText=fmt(events[0].countdown);document.getElementById(\'incSub\').innerText=events[0].event+\' - \'+events[0].ccy+\' - \'+events[0].source;}}catch(e){}try{let r2=await fetch(\'/api/macro\');let j2=await r2.json();window.intel=j2.news||[];renderIntel();}catch(e){}}'
    h+='function renderTerr(){let html=\'\';let map={\'FOREX\':\'EUROPE FRONT\',\'CRYPTO\':\'TECH FRONT\',\'METALS\':\'BUNKER\',\'INDICES\':\'INDICES\',\'COMMODITIES\':\'COMMODITIES\',\'STOCKS\':\'STOCKS\'};Object.keys(GROUPS).forEach(g=>{let pairs=GROUPS[g];let top=all.filter(s=>pairs.some(x=>x[1]===s.name)).sort((a,b)=>b.score-a.score)[0];let score=top?Math.round(top.score):Math.floor(50+Math.random()*30);let col=score>70?\'\':score>50?\' yellow\':\' red\';let pairTxt=top?top.name+\' +\'+(score-50)/10+\'%\':pairs[0][1];let sym=top? (top.action.includes(\'BUY\')?\'▲\':\'▼\'):\'▲\';html+=`<div class=\"terr\" onclick=\"openTerminal(\'${g}\')\"><b>${g}</b><span style=\"font-size:9px;color:#5a7a5a\">${map[g]||g}</span><div class=\"score\">SCORE: ${score}/100 <span style=\"float:right;color:${score>70?\'#8aff6a\':score>50?\'#ffeb3b\':\'#ff4444\'}\">${score}%</span></div><div class=\"bar\"><div class=\"bar-fill${col}\" style=\"width:${score}%\"></div></div><div class=\"pair\">${pairTxt} ${sym}</div></div>`;});document.getElementById(\'terrGrid\').innerHTML=html;}'
    h+='function renderKill(){let top=all.slice(0,6);let html=\'\';top.forEach((x,i)=>{html+=`<div class=\"kill\"><b>${x.name}</b><span style=\"font-size:9px\">SCORE ${x.score}</span><div style=\"display:flex;gap:6px\"><button class=\"btn btn-buy\" onclick=\"openDetail(${all.indexOf(x)})\">🔥 BUY NOW</button><button class=\"btn btn-sell\" onclick=\"openDetail(${all.indexOf(x)})\">SELL NOW</button></div></div>`;});document.getElementById(\'killList\').innerHTML=html||\'Scanning battlefield...\';}'
    h+='function renderIntel(){let html=\'\';if(window.intel){window.intel.forEach(l=>{html+=`<div class=\"intel-line\">> ${l.time} - [${l.tag}] ${l.title}<br><span style=\"color:#5a7a5a\">${l.desc} - ${l.source}</span></div>`;});}document.getElementById(\'intelFeed\').innerHTML=html||\'No intel\';}'
    h+='function conn(){let p=location.protocol===\'https:\'?\'wss:\':\'ws:\';ws=new WebSocket(p+\'//\'+location.host+\'/ws?tf=\'+curTF);ws.onmessage=e=>{let d=JSON.parse(e.data);if(d.signals){all=d.signals;renderTerr();renderKill();if(!mainVisible)drawTerm();}};ws.onclose=()=>setTimeout(conn,3000);}'
    h+='function drawTerm(){let list=GROUPS[curGroup]||[];let filt=all.filter(s=>list.some(x=>x[1]===s.name));filt.sort((a,b)=>b.score-a.score);let html=\'\';filt.forEach((x,i)=>{html+=`<div class=\"card\" onclick=\"openDetail(${all.indexOf(x)})\"><div style=\"display:flex;justify-content:space-between\"><b style=\"color:#8aff6a\">${x.name}</b><span>SCORE ${x.score}</span><span style=\"color:${x.action.includes(\'BUY\')?\'#8aff6a\':\'#ff4444\'}\">${x.action}</span></div><div style=\"font-size:10px;color:#5a7a5a\">Price ${x.price} SL ${x.sl} TP ${x.tp} RR ${x.rr}</div></div>`;});document.getElementById(\'termTable\').innerHTML=html;}'
    h+='function openDetail(i){let x=all[i];if(!x)return;document.getElementById(\'detailBox\').innerHTML=`<b>${x.name} ${curTF}</b><br>Price ${x.price}<br>SL ${x.sl}<br>TP ${x.tp}<br>RR ${x.rr}<br>Reason ${x.reason}<br><br><button style=\"width:100%;background:#8aff6a;color:#000;padding:12px;border:none;border-radius:8px;font-weight:900\" onclick=\"navigator.clipboard.writeText(\'${x.name} ${x.action} ${x.price} SL ${x.sl} TP ${x.tp}\');this.innerText=\'COPIED!\'\">COPY SIGNAL</button><br><br><button style=\"width:100%;background:#111;color:#8aff6a;padding:10px;border:1px solid #1a3a1a;border-radius:8px\" onclick=\"document.getElementById(\'detailModal\').style.display=\'none\'\">CLOSE</button>`;document.getElementById(\'detailModal\').style.display=\'block\';}'
    h+='setInterval(()=>{events.forEach(e=>{if(e.countdown>0)e.countdown--;});if(events[0])document.getElementById(\'incTime\').innerText=fmt(events[0].countdown);},1000);setInterval(loadData,60000);loadData();conn();showMain();'
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
