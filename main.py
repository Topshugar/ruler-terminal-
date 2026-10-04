import os, hashlib, asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()
SECRET = os.getenv("RULER_SECRET", "final_pro")
FOREX = ["EUR/USD","GBP/USD","USD/JPY","USD/CHF","AUD/USD","USD/CAD","NZD/USD","EUR/GBP","EUR/JPY","GBP/JPY","AUD/JPY","EUR/AUD"]
METALS = ["XAU/USD","XAG/USD","XPT/USD"]
CRYPTO = ["BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","XRP/USDT","ADA/USDT","DOGE/USDT","AVAX/USDT","LINK/USDT","TON/USDT","WIF/USDT","PEPE/USDT","BONK/USDT","FLOKI/USDT","NOT/USDT","ENA/USDT","W/USDT","JUP/USDT","TAO/USDT","ARKM/USDT","ZK/USDT","ZRO/USDT","IO/USDT","LISTA/USDT","FET/USDT","SHIB/USDT","BOME/USDT","TURBO/USDT","DOGS/USDT","CATI/USDT"]
ALL = FOREX+METALS+CRYPTO

def sc(s,tf):
    h=hashlib.sha256(f"{SECRET}_{s}_{tf}_{datetime.utcnow().strftime('%Y-%m-%d-%H')}".encode()).hexdigest()
    return 52 + (int(h[:2],16)%38)
def cd(tf):
    n=datetime.utcnow()
    if tf=="M15": sec=15*60-(n.minute%15*60+n.second)
    elif tf=="H1": sec=3600-(n.minute*60+n.second)
    elif tf=="H4": sec=4*3600-((n.hour%4)*3600+n.minute*60+n.second)
    else: sec=86400-(n.hour*3600+n.minute*60+n.second)
    m,s=divmod(sec,60); h,m=divmod(m,60)
    return f"{m:02d}:{s:02d}" if h==0 else f"{h:02d}:{m:02d}:{s:02d}"

@app.get("/")
async def root(): return HTMLResponse(HTML)
@app.get("/api/markets")
async def mk(): return {"FOREX":FOREX,"METALS":METALS,"CRYPTO":CRYPTO}
@app.websocket("/ws")
async def w(ws: WebSocket):
    await ws.accept()
    while True:
        p={s:{"M15":{"s":sc(s,"M15"),"c":cd("M15")},"H1":{"s":sc(s,"H1"),"c":cd("H1")},"H4":{"s":sc(s,"H4"),"c":cd("H4")},"D1":{"s":sc(s,"D1"),"c":cd("D1")}} for s in ALL}
        await ws.send_json(p)
        await asyncio.sleep(3)

HTML="""
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<style>
*{box-sizing:border-box;font-family:Inter,system-ui,Arial}body{margin:0;background:#0B0E12;color:#d7dde7;padding-bottom:90px}
.top{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:#12161E;border-bottom:1px solid #1D242F;position:sticky;top:0;z-index:10}
.top b{letter-spacing:.6px}
.groups{display:flex;gap:6px;padding:10px 12px;overflow:auto}
.groups span{padding:8px 14px;border-radius:999px;background:#1A202B;border:1px solid #242E3E;color:#8A94A7;font-weight:700;font-size:11px;white-space:nowrap}
.groups span.active{background:#2F80ED;color:#fff;border-color:#2F80ED}
.pairs{margin:0 12px;background:#12161E;border:1px solid #1E2735;border-radius:16px;overflow:hidden}
.pairs.head{display:flex;justify-content:space-between;padding:10px 14px;color:#6B7588;font-size:11px;border-bottom:1px solid #1E2735}
.row{display:flex;justify-content:space-between;padding:12px 14px;border-bottom:1px solid #1A2028}
.row.active{background:#192231;border-left:3px solid #2F80ED}
.price{font-size:12px}
.terminal{margin:12px;background:#12161E;border:1px solid #253149;border-radius:18px;padding:14px}
.big{font-size:40px;font-weight:900;color:#2ECC71}
.gauge{width:86px;height:86px;border-radius:50%;border:4px solid #1E314E;border-top-color:#2F80ED;display:flex;flex-direction:column;align-items:center;justify-content:center;margin:10px auto}
.tfs{display:flex;gap:6px;margin-top:10px}
.tfs span{flex:1;text-align:center;padding:8px;border-radius:10px;background:#1E2633;color:#7D8798;font-size:11px;font-weight:700}
.tfs span.active{background:#2A3447;color:#fff;border-bottom:2px solid #2F80ED}
.chart{height:130px;background:linear-gradient(180deg,#111827,#0B0E12);border:1px solid #1E2A3C;border-radius:12px;margin-top:12px}
.btns{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}
.btns button{padding:12px;border-radius:10px;border:0;background:#222A36;color:#5B6576;font-weight:800}
.bottom{position:fixed;bottom:0;left:0;right:0;background:#0F131A;border-top:1px solid #1E2735;display:flex;justify-content:space-around;padding:10px 0 18px}
.bottom div{text-align:center;color:#5B6576}
.bottom div.active{color:#2F80ED}
.bottom i{font-size:22px;display:block}
.bottom span{font-size:10px}
.card{margin:12px;background:#12161E;border:1px solid #1E2735;border-radius:16px;padding:14px}
.blue{background:#2F80ED;border-radius:18px;padding:18px;color:#fff;margin:12px}
</style></head><body>
<div class="top"><b>RULER TERMINAL</b><span style="color:#2ECC71;font-weight:800;font-size:13px">● LIVE</span></div>

<div id="v-cal" style="display:none"><div class="blue"><small>Next Event Countdown</small><h1 id="cd" style="font-size:42px;margin:6px 0">02:14:32</h1><b>FED Interest Rate Decision</b><br><small>Today 14:00 UTC</small></div><div class="card"><b>Today Events A-Z</b><div id="ev" style="margin-top:8px;font-size:13px;line-height:2.2"></div></div></div>

<div id="v-trade"><div class="groups" id="g"></div><div class="pairs"><div class="head"><span>PAIRS</span><span>≡</span></div><div id="list"></div></div>
<div class="terminal"><div style="display:flex;justify-content:space-between;color:#6B7588;font-size:11px"><span id="pname">EUR/USD • FOREX</span><span id="pcd">M15 closes in 07:50</span></div>
<div style="display:flex;align-items:center;gap:10px"><div class="big" id="price">1.09452</div><div style="color:#2ECC71;font-weight:800">+0.24% ↑</div></div>
<div class="gauge"><small style="color:#5AA9FF;font-size:10px;font-weight:800">STRONG</small><b id="pct" style="color:#5AA9FF;font-size:22px">85%</b></div>
<div style="text-align:center;color:#6B7588;font-size:11px">Signal Strength • High Confidence</div>
<div class="tfs" id="tfs"><span class="active" onclick="setTF('M15',this)">M15 07:50</span><span onclick="setTF('H1',this)">H1</span><span onclick="setTF('H4',this)">H4</span><span onclick="setTF('D1',this)">D1</span></div>
<canvas id="chart" class="chart" width="360" height="130"></canvas>
<div class="btns"><button>NO BUY</button><button>NO SELL</button></div><div style="text-align:center;color:#4B5563;font-size:10px;margin-top:6px">View only - No trading - Awaiting confirmed signal</div></div></div>

<div id="v-news" style="display:none"><div class="card"><b>News • Alphabetical</b><div id="news" style="margin-top:8px;font-size:13px;line-height:2"></div></div><div class="card"><b>Fuel Donation</b><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px"><div style="background:#162A4A;padding:12px;border-radius:12px;text-align:center"><b>TRC20</b><br><small>TXyz...9kQm</small></div><div style="background:#3A2710;padding:12px;border-radius:12px;text-align:center"><b>BEP20</b><br><small>0xAbc...3fD2</small></div></div></div></div>

<div class="bottom"><div onclick="showV('cal',this)"><i class="bi bi-calendar3"></i><span>Calendar</span></div><div class="active" onclick="showV('trade',this)"><i class="bi bi-bar-chart-line-fill"></i><span>Chart</span></div><div onclick="showV('news',this)"><i class="bi bi-newspaper"></i><span>News</span></div><div onclick="showV('news',this)"><i class="bi bi-fuel-pump"></i><span>Fuel</span></div></div>

<script>
function showV(v,el){document.getElementById('v-cal').style.display=v=='cal'?'block':'none';document.getElementById('v-trade').style.display=v=='trade'?'block':'none';document.getElementById('v-news').style.display=v=='news'?'block':'none';document.querySelectorAll('.bottom div').forEach(d=>d.classList.remove('active'));el.classList.add('active')}
let cur="EUR/USD", curTF="M15", data={}, mkts={}
fetch('/api/markets').then(r=>r.json()).then(d=>{mkts=d;let h='';for(let k in d){h+=`<span class="${k=='FOREX'?'active':''}" onclick="openG('${k}',this)">${k}</span>`}document.getElementById('g').innerHTML=h;openG('FOREX')})
function openG(g,el){if(el){document.querySelectorAll('.groups span').forEach(s=>s.classList.remove('active'));el.classList.add('active')}let list=mkts[g]||[];let rows=list.slice(0,12).map(p=>`<div class="row ${p==cur?'active':''}" onclick="sel('${p}')"><b>${p}</b><div class="price">${(1.09+Math.random()*0.3).toFixed(5)}<br><span style="color:${Math.random()>0.5?'#2ECC71':'#FF5A5A'}">${(Math.random()>0.5?'+':'')+(Math.random()*0.8-0.2).toFixed(2)}%</span></div></div>`).join('');document.getElementById('list').innerHTML=rows;if(list.length) sel(list[0])}
function sel(p){cur=p;document.getElementById('pname').innerText=p+' • FOREX';render()}
function setTF(tf,el){curTF=tf;document.querySelectorAll('.tfs span').forEach(s=>s.classList.remove('active'));el.classList.add('active');render()}
let ws=new WebSocket((location.protocol=='https:'?'wss://':'ws://')+location.host+'/ws')
ws.onmessage=e=>{data=JSON.parse(e.data);render()}
function render(){let d=data[cur];if(!d)return;document.getElementById('pct').innerText=d[curTF].s+'%';document.getElementById('pcd').innerText=curTF+' closes in '+d[curTF].c;document.getElementById('cd').innerText=d['H1'].c;draw()}
function draw(){let c=document.getElementById('chart').getContext('2d');c.clearRect(0,0,360,130);c.strokeStyle='#1A2740';for(let i=0;i<4;i++){c.beginPath();c.moveTo(0,i*32);c.lineTo(360,i*32);c.stroke()}c.strokeStyle='#2F80ED';c.lineWidth=2;c.beginPath();c.moveTo(0,90);let y=90;for(let x=0;x<360;x+=8){y+=(Math.random()-0.45)*10;c.lineTo(x,y)}c.stroke()}
document.getElementById('ev').innerHTML='• Bonds Auction 10:30 US 30Y<br>• CPI Core YoY 13:30 US<br>• FED Decision 14:00 UTC<br>• Jobless Claims 12:30 US<br>• Retail Sales 13:30 US'
document.getElementById('news').innerHTML='A - AUD Inflation 09:12 3m ago<br>B - BTC Volatility Drops 08:45<br>D - DOGE +12% TURBO DOGS NEW 5m ago<br>F - FLOKI BONK Rally 10m ago<br>P - PEPE WIF Highs 8m ago'
</script></body></html>
"""
if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT",8000)))
