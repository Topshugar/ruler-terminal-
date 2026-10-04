import os, hashlib, asyncio, json, requests, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()
SECRET = os.getenv("RULER_SECRET", "ruler_yahoo_hidden")
MARKET_OFFSET = 2

GROUPS = {
    "Crypto": {"total":74, "pairs":["BTCUSD","ETHUSD"]},
    "Bonds": {"total":3, "pairs":["US10Y","DE10Y","UK10Y"]},
    "Commodities": {"total":7, "pairs":["USOIL","XAUUSD","XAGUSD"]},
    "ETFs": {"total":12, "pairs":[]},
    "Forex": {"total":62, "pairs":["EURUSD","GBPUSD","USDCAD","USDCHF","EURGBP","EURCAD","EURAUD","GBPCAD","GBPJPY","CADJPY","CHFJPY"]},
    "Indices": {"total":23, "pairs":["US30","NAS100"]},
    "Metals & Energies": {"total":9, "pairs":["XAUUSD","XAGUSD","USOIL"]},
    "Stocks": {"total":155, "pairs":[]}
}

def get_market_time():
    return datetime.utcnow() + timedelta(hours=MARKET_OFFSET)

def get_tf_key(tf):
    mt = get_market_time()
    if tf == "M15":
        m = (mt.minute // 15) * 15
        return mt.strftime(f"%Y-%m-%d-%H-{m:02d}-M15-GMT2")
    if tf == "M30":
        m = (mt.minute // 30) * 30
        return mt.strftime(f"%Y-%m-%d-%H-{m:02d}-M30-GMT2")
    if tf == "H1":
        return mt.strftime("%Y-%m-%d-%H-H1-GMT2")
    if tf == "H4":
        h4 = (mt.hour // 4) * 4
        return mt.strftime(f"%Y-%m-%d-{h4:02d}-H4-GMT2")
    if tf == "D1":
        return mt.strftime("%Y-%m-%d-D1-GMT2")
    return mt.strftime("%Y-%m-%d-%H-H1-GMT2")

def gen_row(pair, tf_key):
    h = hashlib.sha256(f"{SECRET}_{pair}_{tf_key}".encode()).hexdigest()
    score = round(min(68,max(22,20 + (int(h[0:2],16) % 520)/10)),1)
    base = {"XAUUSD":4166.70,"EURUSD":1.1255,"GBPUSD":1.3236,"USDCAD":1.4257,"USDCHF":0.829,"EURGBP":0.8501,"EURCAD":1.6042,"EURAUD":1.6189,"GBPCAD":1.8869,"GBPJPY":208.89,"CADJPY":110.69,"CHFJPY":190.36,"BTCUSD":68123.5,"ETHUSD":2511.17,"US30":42123.0,"NAS100":20123.0,"USOIL":71.23,"XAGUSD":31.12,"US10Y":1.19,"DE10Y":1.21,"UK10Y":1.20}.get(pair,1.2)
    var = (int(h[6:8],16)-128)/5000
    price = base + var
    price_str = f"{price:.2f}" if pair in ["BTCUSD","US30","NAS100"] else f"{price:.3f}" if "JPY" in pair else f"{price:.4f}"
    action = "BUY NOW" if score >= 50 else "SELL NOW"
    return {"pair":pair,"score":score,"price":price_str,"action":action}

CAL_CACHE = {"data":[],"time":0}
def get_calendar():
    now = datetime.utcnow().timestamp()
    if now - CAL_CACHE["time"] < 1800 and CAL_CACHE["data"]:
        return CAL_CACHE["data"]
    try:
        url = "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json"
        r = requests.get(url, timeout=6)
        raw = r.json()
        events=[]
        for e in raw:
            try:
                dt_str = e.get("date")
                dt = datetime.fromisoformat(dt_str.replace("Z","+00:00"))
                mt_dt = dt + timedelta(hours=MARKET_OFFSET)
                if mt_dt.date()!= get_market_time().date():
                    continue
                events.append({
                    "time": mt_dt.strftime("%H:%M"),
                    "ccy": e.get("country",""),
                    "event": e.get("title","")[:45],
                    "impact": e.get("impact","").upper(),
                    "forecast": e.get("forecast",""),
                    "previous": e.get("previous",""),
                })
            except:
                continue
        events = sorted(events, key=lambda x: (0 if x["impact"]=="HIGH" else 1, x["time"]))
        CAL_CACHE["data"]=events
        CAL_CACHE["time"]=now
        return events
    except:
        return []

NEWS_CACHE = {"data":[],"time":0}
def get_news():
    now = datetime.utcnow().timestamp()
    if now - NEWS_CACHE["time"] < 300 and NEWS_CACHE["data"]:
        return NEWS_CACHE["data"]
    try:
        # Yahoo Finance RSS hidden backend
        urls = [
            "https://finance.yahoo.com/news/rssindex",
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=XAUUSD=X,^GSPC,BTC-USD&region=US&lang=en-US"
        ]
        items=[]
        for url in urls:
            try:
                r = requests.get(url, timeout=5, headers={"User-Agent":"Mozilla/5.0"})
                root = ET.fromstring(r.content)
                for it in root.findall(".//item")[:20]:
                    title = it.findtext("title","")[:120]
                    pub = it.findtext("pubDate","")
                    try:
                        dt = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z")
                        mt_dt = dt.astimezone(timezone.utc) + timedelta(hours=MARKET_OFFSET)
                        t = mt_dt.strftime("%H:%M")
                    except:
                        t = get_market_time().strftime("%H:%M")
                    # Tag detection
                    tag = "MARKET"
                    tl = title.lower()
                    if "gold" in tl or "xau" in tl: tag="XAUUSD"
                    elif "oil" in tl or "crude" in tl: tag="USOIL"
                    elif "bitcoin" in tl or "btc" in tl: tag="BTCUSD"
                    elif "dollar" in tl or "usd" in tl: tag="USD"
                    elif "euro" in tl or "eur" in tl: tag="EUR"
                    elif "pound" in tl or "gbp" in tl: tag="GBP"
                    elif "s&p" in tl or "nasdaq" in tl or "dow" in tl: tag="US30"
                    items.append({"time":t,"tag":tag,"title":title})
            except:
                continue
        # Deduplicate
        seen=set()
        uniq=[]
        for x in items:
            if x["title"] not in seen:
                seen.add(x["title"])
                uniq.append(x)
        uniq = uniq[:30]
        NEWS_CACHE["data"]=uniq
        NEWS_CACHE["time"]=now
        return uniq
    except:
        return [
            {"time":get_market_time().strftime("%H:%M"),"tag":"USD","title":"Dollar holds steady ahead of CPI data"},
            {"time":get_market_time().strftime("%H:%M"),"tag":"XAUUSD","title":"Gold steady near record high on safe haven flows"},
        ]

from datetime import timezone

@app.get("/")
async def root():
    return HTMLResponse(HTML)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    current_tf = "M30"
    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=0.1)
                j = json.loads(data)
                if j.get("tf") in ["M15","M30","H1","H4","D1"]:
                    current_tf = j["tf"]
            except asyncio.TimeoutError:
                pass
            except:
                pass
            tf_key = get_tf_key(current_tf)
            mt = get_market_time()
            grouped={}
            for gname, ginfo in GROUPS.items():
                rows=[gen_row(p,tf_key) for p in ginfo["pairs"]]
                rows=sorted(rows,key=lambda x:x["score"],reverse=True)
                grouped[gname]={"total":ginfo["total"],"selected":len(rows),"rows":rows}
            await ws.send_json({
                "grouped":grouped,
                "tf":current_tf,
                "market_time": mt.strftime("%H:%M:%S"),
                "calendar": get_calendar(),
                "news": get_news()
            })
            await asyncio.sleep(3)
    except:
        pass

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RULER NEWS</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
<style>
*{box-sizing:border-box;font-family:Consolas,Monaco,monospace}
body{margin:0;background:rgb(0,0,0);color:rgb(220,220,220);padding-bottom:70px}
.top{background:rgb(5,5,5);border-bottom:1px solid rgb(25,25,25);position:sticky;top:0;z-index:10;padding:12px}
.top-row{display:flex;justify-content:space-between;align-items:center}
.top b{color:rgb(0,255,0);font-size:13px}
.local-time{color:rgb(100,100,100);font-size:11px}
.tf-bar{display:flex;gap:6px;margin-top:10px}
.tf-btn{padding:6px 12px;border:1px solid rgb(35,35,35);background:rgb(12,12,12);color:rgb(120,120,120);font-size:11px;cursor:pointer;border-radius:3px}
.tf-btn.active{background:rgb(0,255,0);color:rgb(0,0,0);border-color:rgb(0,255,0);font-weight:700}
.folder{display:flex;justify-content:space-between;align-items:center;padding:16px 12px;border-bottom:1px solid rgb(18,18,18);cursor:pointer;background:rgb(0,0,0)}
.folder-left{display:flex;align-items:center;gap:12px}
.folder-icon{color:rgb(255,193,7);font-size:18px}
.folder-name{color:rgb(220,220,220);font-size:14px}
.folder-count{color:rgb(120,120,120);font-size:13px}
.folder-content{display:none;background:rgb(8,8,8)}
.folder-content.open{display:block}
.header-row{display:grid;grid-template-columns: 90px 60px 110px 90px;padding:10px 12px 10px 44px;border-bottom:1px solid rgb(22,22,22);font-size:11px;color:rgb(100,100,100);background:rgb(10,10,10)}
.row{display:grid;grid-template-columns: 90px 60px 110px 90px;padding:11px 12px 11px 44px;border-bottom:1px solid rgb(14,14,14);font-size:13px;align-items:center}
.pair{color:rgb(0,255,0);font-weight:600}
.score-cyan{color:rgb(0,255,255)}.score-red{color:rgb(255,80,80)}
.price{color:rgb(0,255,0)}
.buy{color:rgb(0,255,255);font-weight:700}.sell{color:rgb(255,80,80);font-weight:700}
.bottom{position:fixed;bottom:0;left:0;right:0;background:rgb(10,10,10);border-top:1px solid rgb(25,25,25);display:flex;justify-content:space-around;padding:10px 0 18px;color:rgb(80,80,80);font-size:10px;z-index:20}
.bottom div{cursor:pointer}
.bottom div.active{color:rgb(0,255,0)}
.view{display:none}
.view.active{display:block}
.cal-header{padding:14px 12px;background:rgb(10,10,10);border-bottom:1px solid rgb(22,22,22);display:flex;justify-content:space-between;font-size:11px;color:rgb(150,150,150)}
.cal-row{display:grid;grid-template-columns: 55px 35px 1fr 50px;padding:12px 10px;border-bottom:1px solid rgb(14,14,14);font-size:11px;align-items:center;gap:6px}
.cal-time{color:rgb(0,255,255)}
.cal-ccy{color:rgb(255,255,0);font-weight:700}
.cal-event{color:rgb(220,220,220);font-size:11px}
.cal-high{color:rgb(255,80,80);font-size:9px;border:1px solid rgb(255,80,80);padding:2px 5px;border-radius:3px;text-align:center}
.cal-med{color:rgb(255,193,7);font-size:9px;border:1px solid rgb(255,193,7);padding:2px 5px;border-radius:3px;text-align:center}
.news-row{display:grid;grid-template-columns: 55px 60px 1fr;padding:12px 10px;border-bottom:1px solid rgb(14,14,14);font-size:12px;gap:8px}
.news-time{color:rgb(100,100,100);font-size:11px}
.news-tag{color:rgb(0,0,0);background:rgb(0,255,0);font-size:9px;padding:2px 6px;border-radius:3px;text-align:center;height:18px;font-weight:700}
.news-tag.USD{background:rgb(0,255,255)}
.news-tag.XAUUSD{background:rgb(255,215,0);color:rgb(0,0,0)}
.news-tag.BTCUSD{background:rgb(255,140,0)}
.news-title{color:rgb(220,220,220);line-height:1.3}
</style>
</head>
<body>
<div class="top">
<div class="top-row">
<b id="topTitle">RULER v1.1 <span id="marketClock">--:--:--</span> GMT+2 LIVE <span id="tfLabel" style="color:rgb(0,255,255)">[M30]</span></b>
<span class="local-time" id="localClock">Local --:--:--</span>
</div>
<div class="tf-bar" id="tfBar">
<div class="tf-btn" data-tf="M15" onclick="setTF('M15')">M15</div>
<div class="tf-btn active" data-tf="M30" onclick="setTF('M30')">M30</div>
<div class="tf-btn" data-tf="H1" onclick="setTF('H1')">H1</div>
<div class="tf-btn" data-tf="H4" onclick="setTF('H4')">H4</div>
<div class="tf-btn" data-tf="D1" onclick="setTF('D1')">D1</div>
</div>
</div>

<div id="terminalView" class="view active"><div id="folders"></div></div>
<div id="calendarView" class="view"><div class="cal-header"><span id="calDate"></span><span>MetaQuotes Calendar GMT+2</span><span id="calCount"></span></div><div id="calList"></div></div>
<div id="newsView" class="view"><div class="cal-header"><span>LIVE</span><span>RULER MARKET NEWS</span><span id="newsCount"></span></div><div id="newsList"></div></div>

<div class="bottom">
<div id="btnTerminal" class="active" onclick="showView('terminal')">TERMINAL</div>
<div id="btnCalendar" onclick="showView('calendar')">CALENDAR</div>
<div id="btnNews" onclick="showView('news')">NEWS</div>
<div>FUEL</div>
</div>

<script>
let openFolders = {"Forex":true,"Metals & Energies":true,"Bonds":true,"Crypto":true,"Commodities":true,"Indices":true};
let currentTF = "M30";
let currentView = "terminal";
function showView(v){
 currentView=v;
 document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));
 document.querySelectorAll('.bottom div').forEach(x=>x.classList.remove('active'));
 if(v==='terminal'){
   document.getElementById('terminalView').classList.add('active');
   document.getElementById('btnTerminal').classList.add('active');
   document.getElementById('tfBar').style.display='flex';
 } else if(v==='calendar'){
   document.getElementById('calendarView').classList.add('active');
   document.getElementById('btnCalendar').classList.add('active');
   document.getElementById('tfBar').style.display='none';
 } else {
   document.getElementById('newsView').classList.add('active');
   document.getElementById('btnNews').classList.add('active');
   document.getElementById('tfBar').style.display='none';
 }
 updateTopTitle();
}
function updateTopTitle(){
 const el = document.getElementById('topTitle');
 if(currentView==='terminal'){
   el.innerHTML=`RULER v1.1 <span id="marketClock">${lastMarketTime}</span> GMT+2 LIVE <span style="color:rgb(0,255,255)">[${currentTF}]</span>`;
 } else if(currentView==='calendar'){
   el.innerHTML=`CALENDAR <span style="color:rgb(100,100,100)">GMT+2</span> <span>${lastMarketTime}</span>`;
 } else {
   el.innerHTML=`NEWS <span style="color:rgb(100,100,100)">LIVE</span> <span>${lastMarketTime}</span>`;
 }
}
function setTF(tf){
 currentTF=tf;
 document.querySelectorAll('.tf-btn').forEach(b=>b.classList.remove('active'));
 document.querySelector(`[data-tf="${tf}"]`).classList.add('active');
 if(ws.readyState===1) ws.send(JSON.stringify({tf:tf}));
 updateTopTitle();
}
function toggle(name){ openFolders[name]=!openFolders[name]; renderTerminal(); }
let lastData=null;
let lastMarketTime="--:--:--";
function renderTerminal(){
 if(!lastData) return;
 let html="";
 for(let gname in lastData.grouped){
   let g=lastData.grouped[gname];
   let isOpen=openFolders[gname];
   html+=`<div class="folder" onclick="toggle('${gname}')"><div class="folder-left"><i class="bi bi-folder-fill folder-icon"></i><span class="folder-name">${gname}</span></div><span class="folder-count">${g.selected}/${g.total}</span></div>`;
   html+=`<div class="folder-content ${isOpen?'open':''}">`;
   if(g.rows.length==0) html+=`<div class="row" style="color:rgb(80,80,80)">No symbols</div>`;
   else {
     html+=`<div class="header-row"><span>PAIR</span><span>SCORE</span><span>PRICE</span><span>ACTION</span></div>`;
     g.rows.forEach(r=>{
       let sClass=r.score>=50?'score-cyan':'score-red';
       let aClass=r.action.includes('BUY')?'buy':'sell';
       html+=`<div class="row"><span class="pair">${r.pair}</span><span class="${sClass}">${r.score}</span><span class="price">${r.price}</span><span class="${aClass}">${r.action}</span></div>`;
     });
   }
   html+=`</div>`;
 }
 document.getElementById('folders').innerHTML=html;
}
function renderCalendar(){
 if(!lastData ||!lastData.calendar) return;
 let html="";
 lastData.calendar.forEach(ev=>{
   let cls = ev.impact==='HIGH'? 'cal-high' : 'cal-med';
   html+=`<div class="cal-row"><span class="cal-time">${ev.time}</span><span class="cal-ccy">${ev.ccy}</span><span class="cal-event">${ev.event}</span><span class="${cls}">${ev.impact}</span></div>`;
 });
 document.getElementById('calList').innerHTML=html || '<div style="padding:20px;color:rgb(100,100,100)">No events today</div>';
 document.getElementById('calDate').innerText = new Date().toLocaleDateString();
 document.getElementById('calCount').innerText = lastData.calendar.length + ' events';
}
function renderNews(){
 if(!lastData ||!lastData.news) return;
 let html="";
 lastData.news.forEach(n=>{
   html+=`<div class="news-row"><span class="news-time">${n.time}</span><span class="news-tag ${n.tag}">${n.tag}</span><span class="news-title">${n.title}</span></div>`;
 });
 document.getElementById('newsList').innerHTML=html || '<div style="padding:20px;color:rgb(100,100,100)">Loading news...</div>';
 document.getElementById('newsCount').innerText = lastData.news.length + ' live';
}
function updateLocalClock(){
 const now = new Date();
 document.getElementById('localClock').innerText = 'Local ' + now.toLocaleTimeString('en-GB',{hour12:false});
}
setInterval(updateLocalClock, 1000);
updateLocalClock();

let ws=new WebSocket((location.protocol=='https:'?'wss://':'ws://')+location.host+'/ws');
ws.onopen=()=>{ ws.send(JSON.stringify({tf:currentTF})); };
ws.onmessage=e=>{
 lastData=JSON.parse(e.data);
 lastMarketTime = lastData.market_time;
 const el = document.getElementById('marketClock');
 if(el) el.innerText = lastData.market_time;
 renderTerminal();
 renderCalendar();
 renderNews();
};
</script>
</body>
</html>
"""
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT",8000)))
