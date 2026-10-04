import os, hashlib, asyncio, json
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()
SECRET = os.getenv("RULER_SECRET", "ruler_gmt2_mt5_final")
MARKET_OFFSET = 2 # GMT+2

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
                "market_date": mt.strftime("%Y-%m-%d")
            })
            await asyncio.sleep(2)
    except:
        pass

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RULER GMT+2</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
<style>
*{box-sizing:border-box;font-family:Consolas,Monaco,monospace}
body{margin:0;background:rgb(0,0,0);color:rgb(220,220,220);padding-bottom:60px}
.top{background:rgb(5,5,5);border-bottom:1px solid rgb(25,25,25);position:sticky;top:0;z-index:10;padding:12px}
.top-row{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px}
.top b{color:rgb(0,255,0);font-size:13px;letter-spacing:0.5px}
.local-time{color:rgb(120,120,120);font-size:11px}
.market-time{color:rgb(0,255,255);font-size:11px}
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
.bottom{position:fixed;bottom:0;left:0;right:0;background:rgb(10,10,10);border-top:1px solid rgb(25,25,25);display:flex;justify-content:space-around;padding:10px 0 18px;color:rgb(80,80,80);font-size:10px}
</style>
</head>
<body>
<div class="top">
<div class="top-row">
<b>RULER v1.1 <span id="marketClock">--:--:--</span> GMT+2 LIVE <span id="tfLabel" style="color:rgb(0,255,255)">[M30]</span></b>
<span class="local-time" id="localClock">Local --:--:--</span>
</div>
<div class="tf-bar">
<div class="tf-btn" data-tf="M15" onclick="setTF('M15')">M15</div>
<div class="tf-btn active" data-tf="M30" onclick="setTF('M30')">M30</div>
<div class="tf-btn" data-tf="H1" onclick="setTF('H1')">H1</div>
<div class="tf-btn" data-tf="H4" onclick="setTF('H4')">H4</div>
<div class="tf-btn" data-tf="D1" onclick="setTF('D1')">D1</div>
</div>
</div>
<div id="folders"></div>
<div class="bottom"><div style="color:rgb(0,255,0)">TERMINAL</div><div>CALENDAR</div><div>NEWS</div><div>FUEL</div></div>
<script>
let openFolders = {"Forex":true,"Metals & Energies":true,"Bonds":true,"Crypto":true,"Commodities":true,"Indices":true};
let currentTF = "M30";
function setTF(tf){
 currentTF=tf;
 document.querySelectorAll('.tf-btn').forEach(b=>b.classList.remove('active'));
 document.querySelector(`[data-tf="${tf}"]`).classList.add('active');
 document.getElementById('tfLabel').innerText=`[${tf}]`;
 if(ws.readyState===1) ws.send(JSON.stringify({tf:tf}));
}
function toggle(name){ openFolders[name]=!openFolders[name]; render(); }
let lastData=null;
function render(){
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
 document.getElementById('marketClock').innerText = lastData.market_time;
 render();
};
</script>
</body>
</html>
"""
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT",8000))) 
