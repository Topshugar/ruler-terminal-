from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import requests, os, asyncio, math
from datetime import datetime
from collections import deque

app = FastAPI()
TWELVE_KEY = os.getenv("TWELVE_KEY", "680fed911532416a84b624c94fd78549")
BINANCE_MAP = {"BTCUSD":"BTCUSDT","ETHUSD":"ETHUSDT","SOLUSD":"SOLUSDT","XRPUSD":"XRPUSDT","BNBUSD":"BNBUSDT","ADAUSD":"ADAUSDT","DOGEUSD":"DOGEUSDT","AVAXUSD":"AVAXUSDT"}
GROUPS = {
    "CRYPTO": [["BTC-USD","BTCUSD"],["ETH-USD","ETHUSD"],["SOL-USD","SOLUSD"],["XRP-USD","XRPUSD"],["BNB-USD","BNBUSD"],["ADA-USD","ADAUSD"],["DOGE-USD","DOGEUSD"],["AVAX-USD","AVAXUSD"]],
    "FOREX": [["EURUSD=X","EURUSD"],["GBPUSD=X","GBPUSD"],["AUDUSD=X","AUDUSD"],["USDCAD=X","USDCAD"]],
    "COMMODITIES": [["GC=F","XAUUSD"],["SI=F","XAGUSD"],["CL=F","USOIL"],["BZ=F","UKOIL"]],
    "BONDS": [["^TNX","US10Y"],["^GDAXI","GER40"],["^GSPC","US500"]]
}
ALL = [(t,n,g) for g,arr in GROUPS.items() for t,n in arr]
LIVE = {"ts":0,"prices":{},"history":{}}
SYMBOL_MAP_TWELVE = {"EURUSD":"EUR/USD","GBPUSD":"GBP/USD","AUDUSD":"AUD/USD","USDCAD":"USD/CAD","XAUUSD":"XAU/USD","XAGUSD":"XAG/USD","USOIL":"WTI/USD","UKOIL":"BRENT/USD","US10Y":"US10Y/USD","GER40":"DAX","US500":"SPX"}

def ema_calc(closes, period=21):
    if not closes: return 0
    if len(closes) < period: return sum(closes)/len(closes)
    k = 2/(period+1)
    ema = sum(closes[:period])/period
    for p in closes[period:]:
        ema = p*k + ema*(1-k)
    return ema

def sma_calc(closes, period=200):
    if not closes: return 0
    if len(closes) < period: return sum(closes)/len(closes)
    return sum(closes[-period:])/period

def rsi_calc(closes, period=21):
    if len(closes) < period+1: return 50
    gains=0; losses=0
    for i in range(-period,0):
        try:
            d = closes[i]-closes[i-1]
            if d>0: gains+=d
            else: losses+=-d
        except: pass
    if losses==0: return 70
    rs=gains/losses
    return 100 - (100/(1+rs))

def bb_calc(closes, period=21, dev=2.0):
    if len(closes) < period: return (0,0,0)
    ma = sum(closes[-period:])/period
    var = sum((x-ma)**2 for x in closes[-period:])/period
    std = math.sqrt(var)
    return (ma+dev*std, ma, ma-dev*std)

def fetch_real():
    now = datetime.utcnow().timestamp()
    if now - LIVE["ts"] < 8: return
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=5)
        if r.status_code == 200:
            for it in r.json():
                LIVE["prices"][it["symbol"]] = float(it["price"])
                for our, bsym in BINANCE_MAP.items():
                    if bsym == it["symbol"]:
                        LIVE["prices"][our] = float(it["price"])
                        if our not in LIVE["history"]: LIVE["history"][our]=deque(maxlen=120)
                        LIVE["history"][our].append(float(it["price"]))
        symbols = ",".join(SYMBOL_MAP_TWELVE.values())
        r2 = requests.get(f"https://api.twelvedata.com/price?symbol={symbols}&apikey={TWELVE_KEY}", timeout=8)
        if r2.status_code == 200:
            data = r2.json()
            for clean, twelve_sym in SYMBOL_MAP_TWELVE.items():
                if twelve_sym in data and isinstance(data[twelve_sym], dict) and "price" in data[twelve_sym]:
                    try:
                        price = float(data[twelve_sym]["price"])
                        LIVE["prices"][clean] = price
                        if clean not in LIVE["history"]: LIVE["history"][clean]=deque(maxlen=120)
                        LIVE["history"][clean].append(price)
                    except: pass
        LIVE["ts"] = now
    except Exception as e:
        print(e)

def get_real_history(symbol, tf):
    if symbol in BINANCE_MAP:
        try:
            iv = {"M15":"15m","M30":"30m","H1":"1h","H4":"4h","D1":"1d"}[tf]
            k = requests.get(f"https://api.binance.com/api/v3/klines?symbol={BINANCE_MAP[symbol]}&interval={iv}&limit=200", timeout=5).json()
            return [float(x[4]) for x in k]
        except: pass
    if symbol in SYMBOL_MAP_TWELVE:
        try:
            iv = {"M15":"15min","M30":"30min","H1":"1h","H4":"4h","D1":"1day"}[tf]
            sym = SYMBOL_MAP_TWELVE[symbol]
            r = requests.get(f"https://api.twelvedata.com/time_series?symbol={sym}&interval={iv}&outputsize=200&apikey={TWELVE_KEY}", timeout=8).json()
            if "values" in r:
                return [float(x["close"]) for x in r["values"][::-1]]
        except: pass
    return list(LIVE["history"].get(symbol, []))

class M:
    def __init__(self): self.c=[];
    async def connect(self,w): await w.accept(); self.c.append(w)
    def disc(self,w):
        if w in self.c: self.c.remove(w)
    async def broad(self,m):
        for x in self.c[:]:
            try: await x.send_json(m)
            except: self.disc(x)
manager=M()

def get_htf_ltf(entry_tf):
    if entry_tf in ("M15","M30"): return ("H1","DAY")
    if entry_tf == "H1": return ("H4","DAY")
    if entry_tf == "H4": return ("D1","SWING")
    if entry_tf == "D1": return ("D1","SWING")
    return ("H1","SCALP")

def calc_mtf_ruler(symbol, entry_tf, group):
    fetch_real()
    htf, mode = get_htf_ltf(entry_tf)
    closes_ltf = get_real_history(symbol, entry_tf)
    closes_htf = get_real_history(symbol, htf)
    if len(closes_ltf)<30 or len(closes_htf)<30:
        closes_ltf = list(LIVE["history"].get(symbol, []))
        closes_htf = closes_ltf
        if not closes_ltf: return None
    price_ltf = closes_ltf[-1]
    price_htf = closes_htf[-1]
    ema21_htf = ema_calc(closes_htf, 21)
    sma200_htf = sma_calc(closes_htf, 200)
    rsi21_htf = rsi_calc(closes_htf, 21)
    ema21_ltf = ema_calc(closes_ltf, 21)
    rsi21_ltf = rsi_calc(closes_ltf, 21)
    sma200_ltf = sma_calc(closes_ltf, 200)
    bb_up, bb_mid, bb_low = bb_calc(closes_ltf, 21, 2.0)
    bb_range = bb_up - bb_low
    bb_pos = (price_ltf - bb_low)/bb_range if bb_range!=0 else 0.5
    dist_ema_pct = abs(price_ltf-ema21_ltf)/price_ltf*100 if price_ltf!=0 else 10
    is_squeeze = (bb_range/bb_mid*100 < 2.5) if bb_mid!=0 else False

    htf_score=0; htf_setup=""
    if price_htf > sma200_htf and ema21_htf > sma200_htf:
        htf_score+=4; htf_setup="BULL TREND"
    elif price_htf < sma200_htf and ema21_htf < sma200_htf:
        htf_score+=1; htf_setup="BEAR TREND"
    else:
        htf_score+=2.5; htf_setup="CHOP"
    if rsi21_htf>50: htf_score+=3
    elif rsi21_htf>45: htf_score+=2
    else: htf_score+=0.5
    if price_htf>ema21_htf: htf_score+=3
    else: htf_score+=1

    ltf_score=0; ltf_setup=""
    if group=="CRYPTO":
        if 55 <= rsi21_ltf < 70 and dist_ema_pct<1.2:
            ltf_score=8.5; ltf_setup="MOM EXP 55+"
        elif 45 <= rsi21_ltf <= 55 and 0.4 <= bb_pos <= 0.6:
            ltf_score=7.5; ltf_setup="HOLD MID"
        elif rsi21_ltf<45:
            ltf_score=3; ltf_setup="WEAK"
        else:
            ltf_score=5; ltf_setup="CHOP"
        if is_squeeze and rsi21_ltf>55:
            ltf_score+=1.5; ltf_setup=" SQUEEZE BO"
    elif group=="BONDS":
        if 40 <= rsi21_ltf <= 45 and bb_pos<=0.4 and price_ltf> sma200_ltf:
            ltf_score=9.0; ltf_setup="DIP BUY 40-45"
        elif 45 <= rsi21_ltf < 50:
            ltf_score=8.0; ltf_setup="PULLBACK 45-50 MID"
        elif 50 <= rsi21_ltf < 60 and 0.4 < bb_pos < 0.65:
            ltf_score=7.5; ltf_setup="TREND CONT"
        else:
            ltf_score=4; ltf_setup="AVOID"
    else:
        if 45 <= rsi21_ltf <= 50 and dist_ema_pct<0.8:
            ltf_score=8.5; ltf_setup="PULLBACK EMA"
        elif 40 <= rsi21_ltf < 45 and bb_pos<=0.35:
            ltf_score=8.0; ltf_setup="SUPPORT 40+LOWER"
        elif 50 < rsi21_ltf < 60 and 0.4 <= bb_pos <= 0.7:
            ltf_score=7.0; ltf_setup="CONTINUATION"
        else:
            ltf_score=4.5; ltf_setup="WAIT"
        if 0.4 < bb_pos < 0.6: ltf_score+=0.5

    ltf_score = min(10, ltf_score)
    htf_score = min(10, htf_score)
    final_score = htf_score*0.6 + ltf_score*0.4
    if htf_score<5: final_score = min(final_score, 4.9)
    if htf_score>=6 and ltf_score>=7: action = "ENTRY"
    elif htf_score>=6 and ltf_score>=5: action = "WAIT PULLBACK"
    else: action = "NO TRADE"

    if "ENTRY" in action or "WAIT" in action:
        is_buy = price_ltf > ema21_ltf and rsi21_ltf>45
        if group=="CRYPTO": sl_pct, tp_pct = 0.015, 0.04
        elif group=="BONDS": sl_pct, tp_pct = 0.008, 0.018
        elif group=="COMMODITIES": sl_pct, tp_pct = 0.012, 0.022
        else: sl_pct, tp_pct = 0.006, 0.012
        if entry_tf=="H4": sl_pct*=1.6; tp_pct*=1.6
        if entry_tf=="D1": sl_pct*=2.5; tp_pct*=2.5
        sl = price_ltf*(1-sl_pct) if is_buy else price_ltf*(1+sl_pct)
        tp = price_ltf*(1+tp_pct) if is_buy else price_ltf*(1-tp_pct)
        rr = tp_pct/sl_pct
    else:
        sl=price_ltf*0.99; tp=price_ltf*1.01; rr=1.5
    score_display = round(final_score*10,1)
    return {
        "price":round(price_ltf,4 if price_ltf<100 else 2),
        "sl":round(sl,4 if sl<100 else 2),
        "tp":round(tp,4 if tp<100 else 2),
        "action":action,
        "score":score_display,
        "htf_score":round(htf_score,1),
        "ltf_score":round(ltf_score,1),
        "rr":round(rr,1),
        "reason":f"{htf}:{htf_setup} RSI{round(rsi21_htf)} | {entry_tf}:{ltf_setup} RSI{round(rsi21_ltf)} BB{round(bb_pos,2)} {mode}",
        "name":symbol,
        "mode":mode,
        "htf":htf,
        "rsi_ltf":round(rsi21_ltf),
        "rsi_htf":round(rsi21_htf)
    }

@app.get("/", response_class=HTMLResponse)
def home():
    html = """<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RULER v2.3</title><style>
*{box-sizing:border-box}html,body{margin:0;background:#020202;color:#8aff6a;font-family:monospace;height:100dvh;overflow:hidden}
.phone{width:100%;max-width:460px;margin:0 auto;height:100dvh;background:#050805;display:flex;flex-direction:column;position:relative;border:1px solid #1a2a1a;overflow:hidden}
.header{display:flex;justify-content:space-between;padding:14px 12px;background:#0a0f0a;border-bottom:2px solid #8aff6a33}.htitle{font-size:15px;font-weight:900;color:#8aff6a}
.search{margin:8px 10px;background:#0a0f0a;border:1px solid #1a3a1a;border-radius:10px;padding:10px 12px;display:flex;gap:8px;color:#5a7a5a;font-size:12px;align-items:center}.search input{background:transparent;border:none;outline:none;color:#8aff6a;font-family:monospace;font-size:12px;width:100%}
.tf-bar{display:flex;gap:6px;padding:0 10px 8px;overflow:auto}.tf-btn{padding:6px 14px;border-radius:20px;font-size:11px;font-weight:900;border:1px solid #1a3a1a;color:#5a7a5a;background:#0a0f0a;cursor:pointer;white-space:nowrap}.tf-btn.active{background:#8aff6a;color:#000;border-color:#8aff6a}
.folder{margin:8px 10px;border:1px solid #1a3a1a;border-radius:12px;overflow:hidden;background:#080f08}.folder-head{display:flex;justify-content:space-between;padding:12px 12px;background:#0f1a0f;font-weight:900;font-size:13px;cursor:pointer}.folder-count{background:#1a2a3a;border-radius:12px;padding:2px 8px;font-size:11px;color:#8aff6a;border:1px solid #2a3a4a}
.table-head{display:flex;padding:8px 10px;font-size:8px;color:#5a7a5a;border-bottom:1px solid #111;background:#050805}.row{display:flex;padding:10px 10px;font-size:10px;border-bottom:1px solid #111;align-items:center}.col-pair{width:24%}.col-htf{width:26%}.col-ltf{width:26%}.col-score{width:12%;text-align:center}.col-action{width:12%;text-align:right;font-weight:900;font-size:9px}
.green{color:#8aff6a}.yellow{color:#ffeb3b}.red{color:#ff4444}.content{flex:1;overflow:auto;padding-bottom:80px}
</style></head><body><div class="phone">
<div class="header"><div class="htitle">RULER v2.3 <span id="clock" style="color:#5a7a5a;font-size:11px">--:--:--</span></div><div style="font-size:9px;color:#5a7a5a">LIVE</div></div>
<div class="search">🔍 <input id="searchBox" placeholder="Search BTC, EUR, XAU, SPX..." oninput="render()" /></div>
<div class="tf-bar"><div class="tf-btn" id="tf-M15" onclick="setTF('M15')">M15</div><div class="tf-btn active" id="tf-M30" onclick="setTF('M30')">M30</div><div class="tf-btn" id="tf-H1" onclick="setTF('H1')">H1</div><div class="tf-btn" id="tf-H4" onclick="setTF('H4')">H4</div><div class="tf-btn" id="tf-D1" onclick="setTF('D1')">D1</div></div>
<div class="content" id="content">Loading...</div>
</div>
<script>
let all=[]; let curTF='M30'; let ws=null;
function setTF(tf){curTF=tf; document.querySelectorAll('.tf-btn').forEach(b=>b.classList.remove('active')); document.getElementById('tf-'+tf).classList.add('active'); if(ws)ws.close(); conn();}
function conn(){let p=location.protocol==='https:'?'wss:':'ws:'; ws=new WebSocket(p+'//'+location.host+'/ws?tf='+curTF); ws.onmessage=e=>{let d=JSON.parse(e.data); if(d.signals){all=d.signals; render();}}; ws.onclose=()=>setTimeout(conn,3000);}
function render(){
  let q = (document.getElementById('searchBox').value||'').toUpperCase().trim();
  let groups={};
  groups["CRYPTO"]=all.filter(s=>["BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD"].includes(s.name));
  groups["FOREX"]=all.filter(s=>["EURUSD","GBPUSD","AUDUSD","USDCAD"].includes(s.name));
  groups["COMMODITIES"]=all.filter(s=>["XAUUSD","XAGUSD","USOIL","UKOIL"].includes(s.name));
  groups["BONDS"]=all.filter(s=>["US10Y","GER40","US500"].includes(s.name));
  if(q){ Object.keys(groups).forEach(g=>{ groups[g]=groups[g].filter(s=>s.name.includes(q)); }); }
  let html='';
  Object.keys(groups).forEach(g=>{
    let arr=groups[g]; arr.sort((a,b)=>b.score-a.score);
    if(arr.length==0) return;
    html+=`<div class="folder"><div class="folder-head"><span>📁 ${g}</span><span class="folder-count">${arr.length}</span></div>`;
    html+=`<div class="table-head"><span class="col-pair">PAIR</span><span class="col-htf">HTF</span><span class="col-ltf">LTF</span><span class="col-score">SCORE</span><span class="col-action"></span></div>`;
    arr.forEach(x=>{
      let col = x.score>=70? 'green' : x.score>=50? 'yellow' : 'red';
      let actCol = x.action.includes('ENTRY')? 'green' : x.action.includes('WAIT')? 'yellow' : 'red';
      html+=`<div class="row"><span class="col-pair">○ ${x.name}</span><span class="col-htf" style="font-size:9px">${x.htf}:${x.htf_score}</span><span class="col-ltf" style="font-size:9px">${curTF}:${x.ltf_score}</span><span class="col-score ${col}">${(x.score/10).toFixed(1)}</span><span class="col-action ${actCol}">${x.action}</span></div>`;
    });
    html+=`</div>`;
  });
  document.getElementById('content').innerHTML=html || 'Waiting...';
}
setInterval(()=>{document.getElementById('clock').innerText=new Date().toLocaleTimeString();},1000);
conn();
</script></body></html>"""
    return HTMLResponse(html)

@app.websocket("/ws")
async def ws_ep(websocket: WebSocket, tf: str="M30"):
    await manager.connect(websocket)
    try:
        while True:
            out=[]
            for tk,name,gr in ALL:
                d=calc_mtf_ruler(name, tf, gr)
                if d: out.append(d)
            await manager.broad({"signals":sorted(out,key=lambda x:x["score"],reverse=True)})
            await asyncio.sleep(8)
    except Exception as e:
        print(e)
        manager.disc(websocket)
