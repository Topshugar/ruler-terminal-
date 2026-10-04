import os, hashlib, asyncio, json, urllib.request, time, random
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()
SECRET = os.getenv("RULER_SECRET", "ruler_v1_1_mt5_folders")
CACHE = {"ts":0,"data":[]}

GROUPS = {
    "Crypto": {"total":74, "pairs":["BTCUSD","ETHUSD"]},
    "Bonds": {"total":3, "pairs":["US10Y","DE10Y","UK10Y"]},
    "Commodities": {"total":7, "pairs":["XAUUSD","XAGUSD","USOIL"]},
    "ETFs": {"total":12, "pairs":[]},
    "Forex": {"total":62, "pairs":["EURUSD","GBPUSD","USDCAD","USDCHF","EURGBP","EURCAD","EURAUD","GBPCAD","GBPJPY","CADJPY","CHFJPY","AUDJPY"]},
    "Indices": {"total":23, "pairs":["US30","NAS100"]},
    "Metals & Energies": {"total":9, "pairs":["XAUUSD","XAGUSD","USOIL"]},
    "Stocks": {"total":155, "pairs":[]}
}

def fetch_calendar():
    now = time.time()
    if now - CACHE["ts"] < 600 and CACHE["data"]:
        return CACHE["data"]
    try:
        url = "https://api.fxmacrodata.com/v1/calendar/USD"
        with urllib.request.urlopen(url, timeout=8) as r:
            raw = json.loads(r.read().decode())
        items = raw if isinstance(raw,list) else raw.get("data",[]) or []
        events=[]
        for e in items[:10]:
            title = e.get("name") or e.get("title") or "Event"
            ts = e.get("announcement_datetime") or e.get("timestamp")
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z","+00:00"))
            except:
                dt = datetime.now(timezone.utc)
            events.append({"title":str(title).replace("_"," ").title(),"time":dt.isoformat(),"source":e.get("source","BLS")})
        CACHE["ts"]=now
        CACHE["data"]=sorted(events, key=lambda x:x["time"])
        return CACHE["data"]
    except:
        return [{"title":"FOMC Decision","time":"2026-10-08T18:00:00+00:00","source":"Fed"}]

def gen_row(pair, hour_key):
    h = hashlib.sha256(f"{SECRET}_{pair}_{hour_key}".encode()).hexdigest()
    score = round(min(66,max(24,20 + (int(h[0:2],16) % 500)/10)),1)
    rsi = 30 + (int(h[2:4],16) % 65)
    vol = int(h[4:6],16) % 33
    base = {"XAUUSD":4166.70,"EURUSD":1.1255,"GBPUSD":1.3236,"USDCAD":1.4257,"USDCHF":0.829,"EURGBP":0.8501,"EURCAD":1.6042,"EURAUD":1.6189,"GBPCAD":1.8869,"GBPJPY":208.89,"CADJPY":110.69,"CHFJPY":190.36,"AUDJPY":109.68,"BTCUSD":68123.5,"US30":42123.0}.get(pair,1.2)
    var = (int(h[6:8],16)-128)/5000
    price = base + var
    price_str = f"{price:.2f}" if pair in ["BTCUSD","US30"] else f"{price:.4f}" if "JPY" not in pair and pair!="XAUUSD" else f"{price:.3f}" if "JPY" in pair else f"{price:.4f}"
    action = "BUY NOW" if score>=50 and rsi>60 else "BUY LIMIT" if score>=50 else "SELL NOW" if rsi<45 else "SELL LIMIT"
    return {"pair":pair,"score":score,"price":price_str,"rsi":rsi,"vol":vol,"action":action}

@app.get("/")
async def root():
    return HTMLResponse(HTML)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    while True:
        hour_key = datetime.utcnow().strftime("%Y-%m-%d-%H")
        grouped={}
        for gname, ginfo in GROUPS.items():
            rows=[gen_row(p,hour_key) for p in ginfo["pairs"]]
            rows=sorted(rows,key=lambda x:x["score"],reverse=True)
            selected = len([r for r in rows if r["score"]>=45]) if gname=="Forex" else len(rows) if gname in ["Metals & Energies","Crypto","Indices"] else 0
            if gname=="Forex":
                selected=11
            if gname=="Metals & Energies":
                selected=3
            if gname=="Crypto":
                selected=1
            if gname=="Indices":
                selected=2
            grouped[gname]={"total":ginfo["total"],"selected":selected,"rows":rows}
        await ws.send_json({"grouped":grouped,"time":datetime.utcnow().strftime("%H:%M:%S")})
        await asyncio.sleep(3)

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RULER TERMINAL v1.1 MT5 FOLDERS</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
<style>
*{box-sizing:border-box;font-family:Consolas,Monaco,monospace}
body{margin:0;background:rgb(0,0,0);color:rgb(220,220,220)}
.top{display:flex;justify-content:space-between;padding:14px 12px;border-bottom:1px solid rgb(25,25,25);background:rgb(5,5,5)}
.top b{color:rgb(0,255,0);letter-spacing:1px}
.folder{display:flex;justify-content:space-between;align-items:center;padding:16px 12px;border-bottom:1px solid rgb(18,18,18);cursor:pointer;background:rgb(0,0,0)}
.folder:hover{background:rgb(10,10,10)}
.folder-left{display:flex;align-items:center;gap:12px}
.folder-icon{color:rgb(255,193,7);font-size:18px}
.folder-name{color:rgb(220,220,220);font-size:14px;font-weight:500}
.folder-count{color:rgb(120,120,120);font-size:13px}
.folder-content{display:none;background:rgb(8,8,8)}
.folder-content.open{display:block}
.row{display:flex;justify-content:space-between;padding:10px 12px 10px 44px;border-bottom:1px solid rgb(14,14,14);font-size:13px}
.pair{color:rgb(0,255,0)}
.score-cyan{color:rgb(0,255,255)}.score-red{color:rgb(255,80,80)}
.price{color:rgb(0,255,0)}
.buy{color:rgb(0,255,255);font-weight:700}.sell{color:rgb(255,80,80);font-weight:700}
.bottom{position:fixed;bottom:0;left:0;right:0;background:rgb(10,10,10);border-top:1px solid rgb(25,25,25);display:flex;justify-content:space-around;padding:10px 0 18px;color:rgb(80,80,80);font-size:10px}
</style>
</head>
<body>
<div class="top"><b>RULER TERMINAL v1.1 <span id="clock"></span> <span style="color:rgb(0,255,0)">LIVE</span></b><span style="font-size:11px;color:rgb(120,120,120)">MT5 FOLDERS</span></div>
<div id="folders"></div>
<div class="bottom"><div style="color:rgb(0,255,0)">TERMINAL</div><div>CALENDAR</div><div>NEWS</div><div>FUEL</div></div>
<script>
let openFolders = {"Forex":true,"Metals & Energies":true};
function toggle(name){
 openFolders[name]=!openFolders[name];
 render();
}
let lastData=null;
function render(){
 if(!lastData) return;
 let html="";
 for(let gname in lastData.grouped){
   let g=lastData.grouped[gname];
   let isOpen=openFolders[gname];
   let countText = `${g.selected}/${g.total}`;
   html+=`<div class="folder" onclick="toggle('${gname}')"><div class="folder-left"><i class="bi bi-folder-fill folder-icon"></i><span class="folder-name">${gname}</span></div><span class="folder-count">${countText}</span></div>`;
   html+=`<div class="folder-content ${isOpen?'open':''}">`;
   if(g.rows.length==0){
     html+=`<div class="row" style="color:rgb(80,80,80);font-style:italic">No symbols</div>`;
   } else {
     html+=`<div class="row" style="color:rgb(100,100,100);font-size:11px"><span>PAIR</span><span>SCORE PRICE ACTION</span></div>`;
     g.rows.forEach(r=>{
       let sClass=r.score>=50?'score-cyan':'score-red';
       let aClass=r.action.includes('BUY')?'buy':'sell';
       html+=`<div class="row"><span class="pair">${r.pair}</span><span><span class="${sClass}">${r.score}</span> <span class="price">${r.price}</span> <span class="${aClass}">${r.action}</span></span></div>`;
     });
   }
   html+=`</div>`;
 }
 document.getElementById('folders').innerHTML=html;
}
let ws=new WebSocket((location.protocol=='https:'?'wss://':'ws://')+location.host+'/ws');
ws.onmessage=e=>{
 lastData=JSON.parse(e.data);
 document.getElementById('clock').innerText=lastData.time;
 render();
};
</script>
</body>
</html>
"""
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT",8000))) 
