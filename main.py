import os, hashlib, asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI(title="RULER TERMINAL PRO")

SECRET_SALT = os.getenv("RULER_SECRET", "ruler_pro_v5_clean")
MARKETS = {
    "FOREX": ["EUR/USD","GBP/USD","USD/JPY","USD/CHF","AUD/USD","USD/CAD","NZD/USD","EUR/GBP","EUR/JPY","GBP/JPY","AUD/JPY","EUR/AUD"],
    "METALS": ["XAU/USD","XAG/USD","XPT/USD","XPD/USD","XAU/EUR","XAG/EUR"],
    "INDICES": ["US30","NAS100","SPX500","GER40","UK100","FRA40","JP225"],
    "COMMODITIES": ["USOIL","UKOIL","NATGAS","COPPER"],
    "STOCKS": ["AAPL","TSLA","NVDA","MSFT","GOOGL","AMZN"],
}
CRYPTO_MAJORS = ["BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","XRP/USDT","ADA/USDT","DOGE/USDT","AVAX/USDT","LINK/USDT","TON/USDT"]
CRYPTO_TRENDING = ["WIF/USDT","PEPE/USDT","BONK/USDT","FLOKI/USDT","NOT/USDT","ENA/USDT","W/USDT","JUP/USDT","PYTH/USDT","TAO/USDT","ARKM/USDT","ZK/USDT","ZRO/USDT","IO/USDT","LISTA/USDT"]
CRYPTO_AI_MEME = ["FET/USDT","AGIX/USDT","RNDR/USDT","SHIB/USDT","BOME/USDT","MEW/USDT","POPCAT/USDT","BRETT/USDT","MOG/USDT","MEME/USDT"]
CRYPTO_ALL = CRYPTO_MAJORS + CRYPTO_TRENDING + CRYPTO_AI_MEME
CRYPTO_NEW = ["TURBO/USDT","DOGS/USDT","CATI/USDT","HMSTR/USDT","EIGEN/USDT"]

def stable_score(symbol: str, tf: str) -> int:
    key = f"{SECRET_SALT}_{symbol}_{tf}_{datetime.utcnow().strftime('%Y-%m-%d-%H')}"
    h = hashlib.sha256(key.encode()).hexdigest()
    return 50 + (int(h[:2],16) % 40)

def tf_countdown(tf: str) -> str:
    now = datetime.utcnow()
    if tf=="M15": secs = 15*60 - (now.minute%15*60 + now.second)
    elif tf=="H1": secs = 3600 - (now.minute*60 + now.second)
    elif tf=="H4": secs = 4*3600 - ((now.hour%4)*3600 + now.minute*60 + now.second)
    else: secs = 86400 - (now.hour*3600 + now.minute*60 + now.second)
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if tf=="D1": return f"{h}h {m}m"
    return f"{h:02d}:{m:02d}:{s:02d}" if h>0 else f"{m:02d}:{s:02d}"

@app.get("/")
async def root():
    return HTMLResponse(FRONTEND_HTML)

@app.get("/api/markets")
async def api_markets():
    return {
        "FOREX": MARKETS["FOREX"],
        "METALS": MARKETS["METALS"],
        "CRYPTO": CRYPTO_ALL + CRYPTO_NEW,
        "CRYPTO_NEW": CRYPTO_NEW,
        "INDICES": MARKETS["INDICES"],
        "COMMODITIES": MARKETS["COMMODITIES"],
        "STOCKS": MARKETS["STOCKS"]
    }

@app.websocket("/ws")
async def ws_terminal(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            payload = {}
            all_syms = MARKETS["FOREX"]+MARKETS["METALS"]+CRYPTO_ALL+CRYPTO_NEW+MARKETS["INDICES"]
            for sym in all_syms:
                payload[sym] = {
                    "M15": {"score": stable_score(sym,"M15"), "countdown": tf_countdown("M15")},
                    "H1": {"score": stable_score(sym,"H1"), "countdown": tf_countdown("H1")},
                    "H4": {"score": stable_score(sym,"H4"), "countdown": tf_countdown("H4")},
                    "D1": {"score": stable_score(sym,"D1"), "countdown": tf_countdown("D1")},
                }
            await ws.send_json(payload)
            await asyncio.sleep(4)
    except WebSocketDisconnect:
        pass

FRONTEND_HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>RULER TERMINAL PRO</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;font-family:'Inter',system-ui}body{margin:0;background:rgb(246,248,252);color:rgb(15,23,42);padding-bottom:90px}
.top{position:sticky;top:0;z-index:20;background:rgba(255,255,255,0.95);backdrop-filter:blur(16px);border-bottom:1px solid rgb(238,242,255);padding:14px 18px;display:flex;justify-content:space-between;align-items:center}
.card{background:rgb(255,255,255);border-radius:20px;padding:16px;margin:12px 14px;box-shadow:0 8px 30px rgba(15,23,42,0.06);border:1px solid rgb(238,242,255)}
.blue{background:linear-gradient(135deg,rgb(37,99,235) 0%,rgb(29,78,216) 100%);color:rgb(255,255,255);border-radius:24px;padding:22px;box-shadow:0 14px 32px rgba(37,99,235,0.35);border:0}
.pill{padding:8px 14px;border-radius:999px;background:rgb(241,245,255);color:rgb(51,65,85);font-size:12px;font-weight:700;margin:4px;display:inline-block;cursor:pointer;border:1px solid rgb(226,232,255)}
.pill.active{background:rgb(37,99,235);color:rgb(255,255,255);border-color:rgb(37,99,235);box-shadow:0 4px 12px rgba(37,99,235,0.3)}
.pair{padding:9px 13px;border-radius:999px;background:rgb(248,250,252);border:1px solid rgb(238,242,255);font-size:12px;font-weight:600;margin:4px;display:inline-block;cursor:pointer}
.pair.active{background:rgb(15,23,42);color:rgb(255,255,255);border-color:rgb(15,23,42)}
.bar{height:10px;background:rgb(230,237,255);border-radius:99px;overflow:hidden}
.fill{height:100%;background:linear-gradient(90deg,rgb(37,99,235),rgb(59,130,246));border-radius:99px}
.bottom{position:fixed;bottom:0;left:0;right:0;background:rgba(255,255,255,0.92);backdrop-filter:blur(18px);border-top:1px solid rgb(238,242,255);display:flex;justify-content:space-around;padding:10px 0 24px;z-index:30}
.bottom i{font-size:26px;color:rgb(148,163,184);position:relative;cursor:pointer}
.bottom i.active{color:rgb(37,99,235)}
.bottom i.active::after{content:'';position:absolute;bottom:-8px;left:50%;transform:translateX(-50%);width:6px;height:6px;background:rgb(37,99,235);border-radius:50%}
.small{font-size:11px;color:rgb(100,116,139)}
.guide-bg{position:fixed;inset:0;background:rgba(8,15,35,0.82);backdrop-filter:blur(6px);z-index:99;display:flex;align-items:center;justify-content:center;padding:20px}
.guide-card{background:rgb(255,255,255);border-radius:24px;padding:22px;max-width:380px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,0.3)}
.btn{width:100%;background:rgb(37,99,235);color:rgb(255,255,255);border:0;padding:14px;border-radius:14px;font-weight:800;margin-top:14px;cursor:pointer}
</style></head><body>

<div id="guide" class="guide-bg"><div class="guide-card"><h3 style="margin:0 0 4px"><i class="bi bi-lightbulb-fill" style="color:rgb(245,158,11)"></i> How to use Ruler Terminal</h3><p class="small" style="margin:0 0 14px">Get started in 4 simple steps</p>
<div style="font-size:13px;line-height:1.6">
<p><i class="bi bi-calendar3" style="color:rgb(37,99,235)"></i> <b>1. Track Events</b><br><span class="small">Use Calendar to monitor market events and countdowns 02:14:32</span></p>
<p><i class="bi bi-graph-up-arrow" style="color:rgb(37,99,235)"></i> <b>2. Trade Terminal</b><br><span class="small">Analyze EUR/USD and 40+ crypto with live signal 85% - M15 closes in 07:50. No BUY/SELL, view only.</span></p>
<p><i class="bi bi-newspaper" style="color:rgb(37,99,235)"></i> <b>3. Stay Updated</b><br><span class="small">Read latest News filtered alphabetically A-Z</span></p>
<p><i class="bi bi-fuel-pump" style="color:rgb(37,99,235)"></i> <b>4. Fuel Donation</b><br><span class="small">Support via USDT on TRC20 or BEP20 - voluntary</span></p>
</div><button class="btn" onclick="closeGuide()">Got it, Let's start</button></div></div>

<div class="top"><b><i class="bi bi-rulers"></i> RULER TERMINAL</b><div style="display:flex;gap:14px"><i class="bi bi-search"></i><i class="bi bi-bell"></i></div></div>

<div id="v-cal"><div class="card blue"><div style="display:flex;justify-content:space-between;align-items:center"><small style="opacity:0.9">Next Event Countdown</small><small style="background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:99px">LIVE</small></div><h1 id="mainCD" style="font-size:52px;margin:8px 0;letter-spacing:-2px;font-weight:800">02:14:32</h1><b>FED Interest Rate Decision</b><br><small style="opacity:0.9"><i class="bi bi-calendar-event"></i> Today - Oct 04 - 14:00 UTC</small></div>
<div class="card"><div style="display:flex;justify-content:space-between"><b>Today Events - Sorted Alphabetically</b><span class="small">A to Z</span></div><div id="events" style="margin-top:12px;font-size:13px;line-height:1.9"></div></div></div>

<div id="v-trade" style="display:none"><div class="card" style="padding:10px"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><b>6 Groups Active</b><span class="pill active" style="font-size:10px;padding:4px 10px">LIVE</span></div><div id="groups"></div></div><div id="tradeDetail"></div></div>

<div id="v-news" style="display:none"><div class="card"><div style="display:flex;align-items:center;gap:10px;background:rgb(243,246,251);border-radius:14px;padding:11px 14px"><i class="bi bi-search" style="color:rgb(148,163,184)"></i><input placeholder="All - Sorted Alphabetically" style="border:0;background:transparent;outline:0;width:100%;font-size:13px"></div></div><div id="newsList"></div>
<div class="card"><div style="display:flex;justify-content:space-between"><b><i class="bi bi-fuel-pump"></i> Fuel - USDT Donation</b><span class="small">Voluntary</span></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px"><div style="background:linear-gradient(135deg,rgb(219,234,254),rgb(191,219,254));padding:16px;border-radius:18px;text-align:center"><i class="bi bi-lightning-charge-fill" style="font-size:28px;color:rgb(37,99,235)"></i><br><b>TRC20</b><br><small class="small">USDT Tron Low fee</small><br><b style="font-size:11px">TXyz...9kQm</b></div><div style="background:linear-gradient(135deg,rgb(254,243,199),rgb(253,230,138));padding:16px;border-radius:18px;text-align:center"><i class="bi bi-link-45deg" style="font-size:28px;color:rgb(217,119,6)"></i><br><b>BEP20</b><br><small class="small">USDT BNB Low fee</small><br><b style="font-size:11px">0xAbc...3fD2</b></div></div><p class="small" style="margin-top:10px;text-align:center">Your donation supports platform growth - Thank you!</p></div></div>

<div class="bottom">
<i id="b1" class="bi bi-calendar-event-fill active" onclick="showTab('cal')"></i>
<i id="b2" class="bi bi-candlestick" onclick="showTab('trade')"></i>
<i id="b3" class="bi bi-newspaper" onclick="showTab('news')"></i>
<i id="b4" class="bi bi-fuel-pump" onclick="showTab('news')"></i>
</div>

<script>
let curPair="EUR/USD", curTF="M15", wsData={}, groups={};
function closeGuide(){document.getElementById('guide').style.display='none';localStorage.setItem('ruler_seen','1')}
if(localStorage.getItem('ruler_seen')) document.getElementById('guide').style.display='none';
function showTab(t){document.getElementById('v-cal').style.display=t=='cal'?'block':'none';document.getElementById('v-trade').style.display=t=='trade'?'block':'none';document.getElementById('v-news').style.display=t=='news'?'block':'none';document.querySelectorAll('.bottom i').forEach(i=>i.classList.remove('active'));if(t=='cal')b1.classList.add('active');if(t=='trade')b2.classList.add('active');if(t=='news')b3.classList.add('active');}
fetch('/api/markets').then(r=>r.json()).then(d=>{groups=d;let html='';for(let k in d){if(k.includes('_NEW'))continue;let cnt=d[k].length;let label=k+(k=='CRYPTO'?` (${cnt})`:'');let isNew=k=='CRYPTO'?`<br><small style=color:rgb(37,99,235);font-size:10px>NEW: ${d.CRYPTO_NEW.slice(0,2).join(', ')}</small>`:'';html+=`<span class="pill ${k=='FOREX'?'active':''}" onclick="openGroup('${k}',this)">${label}${isNew}</span>`}document.getElementById('groups').innerHTML=html;openGroup('FOREX')});
function openGroup(g,el){if(el){document.querySelectorAll('.pill').forEach(p=>p.classList.remove('active'));el.classList.add('active')}let list=groups[g]||[];let pairsHtml=list.slice(0,40).map(p=>`<span class="pair ${p==curPair?'active':''}" onclick="selectPair('${p}')">${p}</span>`).join('');document.getElementById('tradeDetail').innerHTML=`<div class="card"><b>${g} - ${list.length} pairs</b><div style="margin-top:10px">${pairsHtml}</div><div id="liveBox" style="margin-top:14px"></div></div>`;if(list.length)selectPair(list[0]);}
function selectPair(p){curPair=p;document.querySelectorAll('.pair').forEach(e=>{e.classList.toggle('active',e.textContent==p)});renderLive();}
let ws=new WebSocket((location.protocol=='https:'?'wss://':'ws://')+location.host+'/ws');ws.onmessage=e=>{wsData=JSON.parse(e.data);renderLive();updateMainCD();};
function renderLive(){let d=wsData[curPair];if(!d)return;let box=document.getElementById('liveBox');if(!box)return;let tfs=['M15','H1','H4','D1'].map(tf=>`<span class="pill ${tf==curTF?'active':''}" onclick="curTF='${tf}';renderLive()">${tf} ${d[tf]?d[tf].countdown:''}</span>`).join('');let score=d[curTF]?d[curTF].score:85;box.innerHTML=`<div style="background:rgb(248,250,255);border:1px solid rgb(230,236,255);padding:14px;border-radius:16px"><div style="display:flex;justify-content:space-between;align-items:center"><div><b style="font-size:18px">${curPair}</b><br><small class="small">Price 1.09452 <span style="color:rgb(22,163,74)">+0.24 percent</span></small></div><div style="text-align:right">${tfs}</div></div><div style="margin-top:14px;display:flex;justify-content:space-between"><b>Signal Strength</b><b style="color:${score>75?'rgb(22,163,74)':score>60?'rgb(217,119,6)':'rgb(220,38,38)'}">STRONG ${score} percent</b></div><div class="bar"><div class="fill" style="width:${score}percent"></div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px"><button style="padding:12px;border-radius:12px;border:0;background:rgb(229,231,235);color:rgb(107,114,128);font-weight:700">NO BUY</button><button style="padding:12px;border-radius:12px;border:0;background:rgb(229,231,235);color:rgb(107,114,128);font-weight:700">NO SELL</button></div><small class="small">M15 closes in ${d['M15']?d['M15'].countdown:'07:50'} - Awaiting confirmed signal - No active position - View only</small></div>`;}
function updateMainCD(){if(wsData['EUR/USD']&&wsData['EUR/USD']['H1']){document.getElementById('mainCD').innerText=wsData['EUR/USD']['H1'].countdown}}
document.getElementById('events').innerHTML=`<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgb(241,245,249)"><span><span style="color:rgb(37,99,235)">•</span> CPI Data Release</span><span class="small">Oct 16 | 12:30 UTC</span></div><div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgb(241,245,249)"><span><span style="color:rgb(37,99,235)">•</span> ECB Statement</span><span class="small">Oct 20 | 09:00 UTC</span></div><div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgb(241,245,249)"><span><span style="color:rgb(37,99,235)">•</span> FED Interest Rate Decision</span><span class="small">Oct 15 | 14:00 UTC</span></div><div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgb(241,245,249)"><span><span style="color:rgb(37,99,235)">•</span> GDP Release</span><span class="small">Oct 12 | 13:00 UTC</span></div><div style="display:flex;justify-content:space-between;padding:8px 0"><span><span style="color:rgb(37,99,235)">•</span> NFP Report</span><span class="small">Oct 18 | 13:30 UTC</span></div><div class="small" style="margin-top:6px">Sorted A to Z - All times UTC</div>`;
document.getElementById('newsList').innerHTML=`<div class="card" style="padding:12px 16px"><b style="font-size:13px">A - CPI Data Shows Lower Inflation, Markets React</b><br><small class="small">2m ago - Economy</small></div><div class="card" style="padding:12px 16px"><b style="font-size:13px">B - BTC Volatility Drops Ahead of Fed Meeting</b><br><small class="small">15m ago - Crypto - BTC</small></div><div class="card" style="padding:12px 16px"><b style="font-size:13px">D - DOGE Jumps 12 percent After New Listing - TURBO, DOGS</b><br><small class="small">5m ago - New - Recently Added</small></div><div class="card" style="padding:12px 16px"><b style="font-size:13px">E - EUR Strengthens on ECB Commentary</b><br><small class="small">42m ago - Forex</small></div><div class="card" style="padding:12px 16px"><b style="font-size:13px">F - FLOKI, BONK Lead Meme Rally</b><br><small class="small">10m ago - Trending - BONK, FLOKI</small></div><div class="card" style="padding:12px 16px"><b style="font-size:13px">P - PEPE, WIF New Highs - ENA, W, JUP Hot</b><br><small class="small">8m ago - Recently Added - PEPE, WIF</small></div>`;
</script></body></html>
"""

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT",8000)))
