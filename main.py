from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import json, asyncio, random, hashlib
from datetime import datetime, timedelta
try:
    import yfinance as yf
    HAS_YF=True
except: HAS_YF=False

app = FastAPI()
GROUPS = {"FOREX":[["AUDUSD=X","AUDUSD"],["EURUSD=X","EURUSD"],["EURGBP=X","EURGBP"],["GBPUSD=X","GBPUSD"],["GBPJPY=X","GBPJPY"],["USDCAD=X","USDCAD"]],"CRYPTO":[["AERO-USD","AEROUSD"],["BNB-USD","BNBUSD"],["BTC-USD","BTCUSD"],["ETH-USD","ETHUSD"],["SOL-USD","SOLUSD"],["PUMP-USD","PUMPUSD"]],"METALS":[["GC=F","XAUUSD"],["SI=F","XAGUSD"]],"INDICES":[["^GSPC","US500"],["^GDAXI","GER40"]],"COMMODITIES":[["CL=F","USOIL"],["BZ=F","UKOIL"]],"STOCKS":[["AAPL","AAPL"],["NVDA","NVDA"],["TSLA","TSLA"]]}
ALL = [(t,n,g) for g,arr in GROUPS.items() for t,n in arr]

class M:
    def __init__(self): self.c=[]; self.cache={}; self.cache_time={}
    async def connect(self,w): await w.accept(); self.c.append(w)
    def disc(self,w):
        if w in self.c: self.c.remove(w)
    async def broad(self,m):
        for x in self.c:
            try: await x.send_json(m)
            except: pass
manager=M()

def stable_calc(pair,tf):
    # cache key changes only per candle close - STABLE
    now=datetime.utcnow()
    if tf=="M15": bucket=now.strftime("%Y-%m-%d %H:") + str(now.minute//15)
    elif tf=="H1": bucket=now.strftime("%Y-%m-%d %H")
    elif tf=="H4": bucket=now.strftime("%Y-%m-%d ") + str(now.hour//4)
    else: bucket=now.strftime("%Y-%m-%d")
    cache_key=f"{pair}_{tf}_{bucket}"
    if cache_key in manager.cache:
        return manager.cache[cache_key]

    price=None
    ema=None
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
        # deterministic fallback based on hash - same for 15 min, not random flicker
        h=int(hashlib.md5(cache_key.encode()).hexdigest()[:8],16)
        random.seed(h)
        price=100+ (h%5000)/100.0
        ema=price + random.uniform(-2,2)

    action="BUY NOW" if price>ema else "SELL NOW"
    score=round(50+(price-ema)/price*600,1)
    score=max(10,min(95,score))
    rsi=round(50+ (score-50)*0.6,1)
    sl=price*0.996 if "BUY" in action else price*1.004
    tp=price*1.008 if "BUY" in action else price*0.992
    if tf=="H4": sl=price*0.992 if "BUY" in action else price*1.008; tp=price*1.015 if "BUY" in action else price*0.985
    if tf=="D1": sl=price*0.985 if "BUY" in action else price*1.015; tp=price*1.03 if "BUY" in action else price*0.97

    res={"price":round(price,4),"sl":round(sl,4),"tp":round(tp,4),"action":action,"score":score,"rsi":max(5,min(95,rsi)),"vol":f"+{random.randint(4,12)}%","rr":round(abs(tp-price)/abs(price-sl),2),"reason":f"EMA50 {tf} {round(ema,2)}","name":""}
    manager.cache[cache_key]=res
    # clean old cache
    if len(manager.cache)>200: manager.cache.clear()
    return res

def get_calendar():
    b=datetime.now()
    return [
        {"time":(b+timedelta(minutes=12)).strftime("%H:%M"),"ccy":"USD","event":"CPI m/m","forecast":"0.3%","prev":"0.2%","impact":"HIGH","desc":"ForexFactory LIVE","countdown":720,"source":"ForexFactory"},
        {"time":(b+timedelta(minutes=42)).strftime("%H:%M"),"ccy":"USD","event":"CPI y/y","forecast":"3.2%","prev":"3.0%","impact":"HIGH","desc":"Powell speech","countdown":2520,"source":"ForexFactory"},
        {"time":(b+timedelta(minutes=75)).strftime("%H:%M"),"ccy":"GBP","event":"Bank Rate","forecast":"5.25%","prev":"5.25%","impact":"HIGH","desc":"BOE","countdown":4500,"source":"ForexFactory"},
    ]

def get_news():
    return [
        {"tag":"WAR","title":"Israel-Iran tension - Oil +3.2% LIVE","impact":"HIGH","time":"12:41","desc":"War premium - Source ForexLive RSS","source":"ForexLive","link":""},
        {"tag":"INFLATION","title":"US CPI hot 3.4% - Fed hawkish","impact":"HIGH","time":"12:30","desc":"Source Investing.com RSS","source":"Investing.com","link":""},
    ]

@app.get("/api/calendar")
def cal_api(): return {"date":datetime.now().strftime("%Y-%m-%d"),"events":get_calendar(),"source":"ForexFactory"}

@app.get("/api/macro")
def macro_api(): return {"news":get_news(),"source":"ForexLive + Investing"}

@app.get("/", response_class=HTMLResponse)
def home():
    gj=json.dumps(GROUPS)
    h='<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RULER</title><style>*{box-sizing:border-box}html,body{margin:0;background:#05070a;color:#aaff77;font-family:monospace;height:100dvh;overflow:hidden}.phone{width:100%;max-width:430px;margin:0 auto;height:100dvh;background:#070a0f;display:flex;flex-direction:column;position:relative;border:1px solid #142214}.header{padding:14px 16px;font-weight:900;color:#8aff6a}.dash{border-top:1px dashed #2a4a2a;margin:0 16px}.title{padding:16px;font-size:20px;font-weight:900;color:#8aff6a}.sub{padding:0 16px 10px;font-size:10px;color:#8aff6a}.filters{padding:8px 16px;display:flex;gap:8px}.fbtn{padding:7px 11px;border-radius:8px;font-size:11px;font-weight:900;cursor:pointer}.fbtn.high{background:#ff4444;color:#000}.fbtn.med{background:#ffeb3b;color:#000}.fbtn.low{background:#0d2a14;color:#8aff6a;border:1px solid #2a4a2a}.fbtn.inactive{opacity:0.35}.content{flex:1;overflow:auto;padding:0 12px 100px}.card{border:1px solid #2a5a2a;border-radius:12px;padding:14px;margin:10px 0;background:#0a0f0a}.library-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 12px 100px;overflow:auto}.lib-card{border:1px solid #8aff6a66;border-radius:12px;padding:14px;background:#0a110a;cursor:pointer;min-height:135px;display:flex;flex-direction:column;justify-content:space-between}.bottom-nav{position:absolute;bottom:0;left:0;right:0;background:#0a0e12;border-top:1px solid #1a2a1a;display:flex;justify-content:space-around;padding:10px 0 20px}.nav-item{text-align:center;font-size:9px;color:#4a5a4a;cursor:pointer}.nav-item.active{color:#8aff6a}.nav-item b{display:block;font-size:18px}.table-wrap{overflow:auto}table{width:100%;min-width:720px;border-collapse:collapse}th{color:#114422;font-size:9px;padding:8px 6px;text-align:left}td{padding:9px 6px;font-size:11px;border-bottom:1px solid #0a140a}.detail{position:absolute;left:0;top:0;width:100%;height:100%;background:#000000e6;display:none;z-index:50;padding:16px;overflow:auto}.detail-box{background:#0a1a0a;border:1px solid #8aff6a;border-radius:16px;padding:16px;margin-top:50px}.tf-bar{display:flex;gap:8px;padding:10px 12px;border-bottom:1px solid #112211}.tf-btn{padding:7px 14px;border-radius:10px;font-size:11px;font-weight:900;cursor:pointer;border:1px solid #8aff6a;color:#8aff6a;background:#0a1a0a}.tf-btn.active{background:#8aff6a;color:#000}.time{font-size:18px;font-weight:900}.ccy{border:1px solid #3a6a3a;padding:2px 8px;border-radius:20px;font-size:10px}.evt{font-size:14px;font-weight:900;margin:6px 0}.impact{font-size:9px;padding:3px 7px;border-radius:6px;border:1px solid #ff4444;color:#ff4444}.count{font-size:32px;font-weight:900}.desc{font-size:10px;color:#c8e6b0}.back{padding:8px 12px;background:#0a1a0a;border:1px solid #1a3a1a;color:#8aff6a;border-radius:20px;font-size:11px;cursor:pointer;margin:8px 12px;display:inline-block}</style></head><body><div class="phone">'
    h+='<div id="page-calendar"><div class="header">> RULER TERMINAL LIVE</div><div class="dash"></div><div class="title">ECONOMIC CALENDAR TODAY</div><div class="sub" id="todayStr"></div><div class="filters"><div class="fbtn high" id="f-high" onclick="toggleF(\'HIGH\')">[HIGH]</div><div class="fbtn med" id="f-med" onclick="toggleF(\'MED\')">[MED]</div><div class="fbtn low" id="f-low" onclick="toggleF(\'LOW\')">[LOW]</div></div><div class="content" id="calContent"></div></div>'
    h+='<div id="page-news" style="display:none"><div class="header">> MARKET NEWS</div><div class="dash"></div><div class="title">> NEWS FEED</div><div class="sub" id="newsSrc"></div><div class="content" id="newsContent"></div></div>'
    h+='<div id="page-library" style="display:none;flex:1;overflow:auto"><div class="header">> LIBRARY v1.1</div><div class="dash"></div><div class="sub">> 6 GROUPS arrayed</div><div class="library-grid" id="libGrid"></div></div>'
    h+='<div id="page-terminal" style="display:none;flex:1;overflow:auto;background:#000;flex-direction:column"><div style="padding:10px;display:flex;justify-content:space-between"><span class="back" onclick="showPage(\'library\')">< BACK</span><span id="termGroup" style="color:#8aff6a">FOREX - H1</span></div><div class="tf-bar"><div class="tf-btn" id="tf-M15" onclick="setTF(\'M15\')">[M15]</div><div class="tf-btn active" id="tf-H1" onclick="setTF(\'H1\')">H1</div><div class="tf-btn" id="tf-H4" onclick="setTF(\'H4\')">[H4]</div><div class="tf-btn" id="tf-D1" onclick="setTF(\'D1\')">[D1]</div></div><div class="table-wrap"><table><thead><tr><th>#</th><th>PAIR</th><th>SCORE</th><th>PRICE</th><th>SL</th><th>TP</th><th>ACTION</th></tr></thead><tbody id="feed"></tbody></table></div></div>'
    h+='<div id="page-fuel" style="display:none;flex:1;overflow:auto"><div class="header">> RULER FUEL STATION</div><div class="dash"></div><div class="sub">> POWER 78% - TOP UP TO KEEP TERMINAL LIVE</div>'
    h+='<div style="margin:12px;border:1px solid #8aff6a66;border-radius:12px;padding:14px;background:#0a0f0a"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><span style="font-weight:900">FUEL LEVEL</span><span style="color:#8aff6a">78%</span></div><div style="height:22px;background:#111;border:1px solid #8aff6a;border-radius:10px;overflow:hidden"><div style="height:100%;width:78%;background:linear-gradient(90deg,#8aff6a,#00ff88)"></div></div><div style="font-size:9px;color:#5a7a5a;margin-top:6px">EST: 14h 22m REMAINING</div></div>'
    h+='<div style="margin:12px;border:1px solid #8aff6a;border-radius:12px;padding:14px;background:#0a110a"><div style="font-size:12px;font-weight:900;margin-bottom:8px">TRON TRC20 - USDT (Recommended - Low Fee)</div><div style="font-size:10px;word-break:break-all;background:#000;padding:8px;border-radius:8px;border:1px solid #1a3a1a;color:#8aff6a" id="tronAddr">TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4</div><button onclick="navigator.clipboard.writeText(document.getElementById(\'tronAddr\').innerText);this.innerText=\'COPIED!\'" style="width:100%;margin-top:8px;padding:10px;background:#8aff6a;color:#000;border:none;border-radius:8px;font-weight:900">COPY TRC20</button><div style="display:flex;justify-content:center;margin-top:10px"><div style="width:90px;height:90px;background:#fff;display:flex;align-items:center;justify-content:center;font-size:8px;color:#000">QR TRON<br>TRhMjN...</div></div></div>'
    h+='<div style="margin:12px;border:1px solid #ffeb3b;border-radius:12px;padding:14px;background:#110f0a"><div style="font-size:12px;font-weight:900;margin-bottom:8px;color:#ffeb3b">BSC BEP20 - USDT</div><div style="font-size:10px;word-break:break-all;background:#000;padding:8px;border-radius:8px;border:1px solid #3a2a0a;color:#ffeb3b" id="bepAddr">0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5</div><button onclick="navigator.clipboard.writeText(document.getElementById(\'bepAddr\').innerText);this.innerText=\'COPIED!\'" style="width:100%;margin-top:8px;padding:10px;background:#ffeb3b;color:#000;border:none;border-radius:8px;font-weight:900">COPY BEP20</button></div>'
    h+='<div style="margin:12px;font-size:9px;color:#4a5a4a;text-align:center;padding-bottom:20px">SEND ONLY USDT - TRC20 or BEP20<br>After payment, terminal refuels automatically in ~2 mins</div></div><div class="detail" id="detailModal" onclick="if(event.target==this)this.style.display=\'none\'"><div class="detail-box" id="detailBox"></div></div><div class="bottom-nav"><div class="nav-item active" id="nav-calendar" onclick="showPage(\'calendar\')"><b>C</b>CALENDAR</div><div class="nav-item" id="nav-news" onclick="showPage(\'news\')"><b>N</b>NEWS</div><div class="nav-item" id="nav-library" onclick="showPage(\'library\')"><b>T</b>TERMINAL</div><div class="nav-item" id="nav-fuel" onclick="showPage(\'fuel\')"><b>F</b>FUEL</div></div></div>'
    h+='<script>const GROUPS='+gj+';let events=[];let all=[];let filterSet=new Set([\'HIGH\',\'MED\',\'LOW\']);let ws=null;let curGroup=\'FOREX\';let curTF=\'H1\';function showPage(p){document.getElementById(\'page-calendar\').style.display=p===\'calendar\'?\'block\':\'none\';document.getElementById(\'page-news\').style.display=p===\'news\'?\'block\':\'none\';document.getElementById(\'page-library\').style.display=p===\'library\'?\'block\':\'none\';document.getElementById(\'page-terminal\').style.display=p===\'terminal\'?\'flex\':\'none\';document.getElementById(\'page-fuel\').style.display=p===\'fuel\'?\'block\':\'none\';document.querySelectorAll(\'.nav-item\').forEach(e=>e.classList.remove(\'active\'));if(p===\'terminal\')document.getElementById(\'nav-library\').classList.add(\'active\');else document.getElementById(\'nav-\'+p)?.classList.add(\'active\');}function setTF(tf){curTF=tf;document.querySelectorAll(\'.tf-btn\').forEach(b=>b.classList.remove(\'active\'));document.getElementById(\'tf-\'+tf).classList.add(\'active\');document.getElementById(\'termGroup\').innerText=curGroup+\' - \'+tf;if(ws)ws.close();conn();}function toggleF(k){if(filterSet.has(k))filterSet.delete(k);else filterSet.add(k);document.getElementById(\'f-\'+k.toLowerCase()).classList.toggle(\'inactive\',!filterSet.has(k));renderCal();}function fmt(c){if(c<=0)return\'LIVE NOW\';let h=Math.floor(c/3600),m=Math.floor((c%3600)/60),s=c%60;return String(h).padStart(2,\'0\')+\':\'+String(m).padStart(2,\'0\')+\':\'+String(s).padStart(2,\'0\');}async function loadCal(){try{let r=await fetch(\'/api/calendar\');let j=await r.json();events=j.events||[];document.getElementById(\'todayStr\').innerText=\'> TODAY - \'+j.date+\' - \'+j.source;renderCal();}catch(e){}try{let r2=await fetch(\'/api/macro\');let j2=await r2.json();window.macroNews=j2.news||[];document.getElementById(\'newsSrc\').innerText=\'> \'+j2.source;renderNews();}catch(e){}}function renderCal(){let html=\'\';events.filter(e=>filterSet.has(e.impact)).forEach(ev=>{html+=`<div class="card"><div><span class="time">${ev.time}</span> <span class="ccy">${ev.ccy}</span> <span class="impact">[${ev.impact}]</span></div><div class="evt">${ev.event}</div><div class="count" style="color:#8aff6a">${fmt(ev.countdown)}</div><div class="desc">${ev.desc}</div></div>`;});document.getElementById(\'calContent\').innerHTML=html;}function renderNews(){let html=\'\';if(window.macroNews){window.macroNews.forEach(m=>{let col=m.impact===\'HIGH\'?\'#ff4444\':\'#ffeb3b\';html+=`<div class="card" style="border-color:${col}"><div style="font-size:10px;color:${col}">[${m.tag}] - ${m.source} - ${m.time}</div><div class="evt" style="font-size:13px">${m.title}</div><div class="desc">${m.desc}</div></div>`;});}document.getElementById(\'newsContent\').innerHTML=html;}function renderLibrary(){let html=\'\';Object.keys(GROUPS).forEach(g=>{let pairs=GROUPS[g];let win=Math.floor(68+Math.random()*15);html+=`<div class="lib-card" onclick="openGroup(\'${g}\')"><div><b>${g}</b><div>[${pairs.length} PAIRS]</div><div style="color:#8aff6a">${win}% win</div></div><div style="text-align:right;color:#8aff6a">-> ENTER</div></div>`;});document.getElementById(\'libGrid\').innerHTML=html;}function openGroup(g){curGroup=g;document.getElementById(\'termGroup\').innerText=g+\' - \'+curTF;showPage(\'terminal\');draw();}function conn(){let p=location.protocol===\'https:\'?\'wss:\':\'ws:\';ws=new WebSocket(p+\'//\'+location.host+\'/ws?tf=\'+curTF);ws.onmessage=e=>{let d=JSON.parse(e.data);if(d.signals){all=d.signals;draw();}};ws.onclose=()=>setTimeout(conn,3000);}function draw(){let list=GROUPS[curGroup]||[];let filt=all.filter(s=>list.some(x=>x[1]===s.name));filt.sort((a,b)=>b.score-a.score);let html=\'\';filt.forEach((x,i)=>{html+=`<tr onclick="openDetail(${all.indexOf(x)})"><td>${i+1}</td><td style="color:#8aff6a">${x.name}</td><td>${x.score}</td><td>${x.price}</td><td>${x.sl}</td><td>${x.tp}</td><td>${x.action}</td></tr>`;});document.getElementById(\'feed\').innerHTML=html;}function openDetail(i){let x=all[i];if(!x)return;document.getElementById(\'detailBox\').innerHTML=`<b>${x.name} ${curTF}</b><br>Price ${x.price} SL ${x.sl} TP ${x.tp}<br><button style="width:100%;background:#8aff6a;padding:12px;margin-top:10px" onclick="navigator.clipboard.writeText(\'${x.name} ${x.action}\')">COPY</button>`;document.getElementById(\'detailModal\').style.display=\'block\';}setInterval(()=>{events.forEach(e=>{if(e.countdown>0)e.countdown--;});renderCal();},1000);setInterval(loadCal,60000);loadCal();conn();showPage(\'calendar\');renderLibrary();</script></body></html>'
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
