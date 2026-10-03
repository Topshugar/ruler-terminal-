from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import yfinance as yf, csv, os, requests, asyncio, json
from datetime import datetime

app = FastAPI()
PAIRS = ["EURUSD=X","GBPUSD=X","USDJPY=X","AUDUSD=X","USDCAD=X","NZDUSD=X","EURJPY=X","GBPJPY=X","EURGBP=X","AUDJPY=X","EURAUD=X","EURCAD=X","GBPCAD=X","GBPAUD=X","AUDCAD=X","USDCHF=X","EURCHF=X","GBPCHF=X","GC=F"]
NAMES = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","NZDUSD","EURJPY","GBPJPY","EURGBP","AUDJPY","EURAUD","EURCAD","GBPCAD","GBPAUD","AUDCAD","USDCHF","EURCHF","GBPCHF","XAUUSD"]
CSV_FILE = "signals.csv"
TF_MAP = {"M15":{"interval":"15m","period":"5d"},"H1":{"interval":"60m","period":"5d"},"H4":{"interval":"60m","period":"20d"},"D1":{"interval":"1d","period":"100d"}}
SITE_URL = "https://ruler-terminal.onrender.com"

# --- MANAGER FOR SOCKET NETWORKING ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

def calc(pair,tf="H1"):
    try:
        cfg=TF_MAP.get(tf,TF_MAP["H1"])
        df=yf.download(pair,period=cfg["period"],interval=cfg["interval"],progress=False)
        if len(df)<50: return None
        close=df['Close'].squeeze(); high=df['High'].squeeze(); low=df['Low'].squeeze()
        ema_len=50 if tf in ["M15","H1"] else 200
        ema=close.ewm(span=ema_len).mean().iloc[-1]
        diff=close.diff(); up=diff.where(diff>0,0).rolling(14).mean(); down=-diff.where(diff<0,0).rolling(14).mean()
        rsi=100-(100/(1+up/down)); rsi_v=round(float(rsi.iloc[-1]),1)
        atr=float((high-low).rolling(14).mean().iloc[-1]); price=float(close.iloc[-1])
        sl_dist=atr*1.5 if atr>0 else price*0.005; tp_dist=sl_dist*1.8
        if price>ema: sl=price-sl_dist; tp=price+tp_dist; action="BUY NOW" if rsi_v<70 else "BUY LIMIT"
        else: sl=price+sl_dist; tp=price-tp_dist; action="SELL NOW" if rsi_v>30 else "SELL LIMIT"
        trend=abs(price-ema)/price*1000; vol=float(close.pct_change().rolling(20).std().iloc[-1]*100)
        score=min(95,trend*2+(50-abs(rsi_v-50))*0.6+vol*5)
        label = f"{rsi_v} - FRESH" if 45<=rsi_v<60 else f"{rsi_v} - TIRED" if rsi_v>=70 else f"{rsi_v}"
        color = "#00ff88" if 45<=rsi_v<60 else "#ffcc00" if rsi_v<70 else "#ff4444"
        return {"score":round(score,1),"price":round(price,5),"rsi_text":label,"rsi_color":color,"action":action,"sl":round(sl,5),"tp":round(tp,5)}
    except: return None

@app.get("/")
def home():
    return HTMLResponse(f"""
<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>RULER SOCKET LIVE</title>
<style>body{{background:#0a0a0a;color:#00ff88;font-family:monospace;padding:10px}} table{{width:100%;border-collapse:collapse}} td,th{{padding:6px;border-bottom:1px solid #222}}.live{{animation:blink 1s infinite}} @keyframes blink{{50%{{opacity:0.3}}}} #status{{padding:6px;background:#111;border-radius:6px;font-size:11px;margin:8px 0}}</style>
</head><body>
<h2>RULER SOCKET MODE <span class="live">● LIVE</span></h2>
<div id="status">🔌 Connecting socket...</div>
<div id="t">Waiting for live feed...</div>
<script>
let ws_protocol = location.protocol === 'https:'? 'wss:' : 'ws:';
let ws = new WebSocket(ws_protocol + '//' + location.host + '/ws?tf=M15');

ws.onopen = () => {{ document.getElementById('status').innerHTML = '✅ SOCKET CONNECTED - Live push ON - No refresh needed'; }};
ws.onclose = () => {{ document.getElementById('status').innerHTML = '❌ Socket disconnected - Refresh page'; }};
ws.onmessage = (event) => {{
  let data = JSON.parse(event.data);
  let d = data.signals;
  d.sort((a,b)=>b.score-a.score);
  let h='<table><tr><th>#</th><th>PAIR</th><th>SCORE</th><th>ACTION</th><th>PRICE</th><th>SL</th><th>TP</th></tr>';
  d.forEach((x,i)=>{{ h+=`<tr><td>${{i+1}}</td><td>${{x.name}}</td><td style="color:${{x.score>60?'#00ff88':'#ffcc00'}}">${{x.score}}</td><td>${{x.action}}</td><td>${{x.price}}</td><td style="color:red">${{x.sl}}</td><td style="color:#00ff88">${{x.tp}}</td></tr>`; }});
  h+='</table><p style="font-size:10px;color:#666">Last push: '+data.time+' TF:'+data.tf+' | Socket networking = no F5</p>';
  document.getElementById('t').innerHTML = h;
}};
</script>
</body></html>
    """)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, tf: str = "M15"):
    await manager.connect(websocket)
    try:
        while True:
            res=[]
            for p,n in zip(PAIRS,NAMES):
                d=calc(p,tf)
                if d: d["name"]=n; res.append(d)
            res_sorted = sorted(res, key=lambda x:x['score'], reverse=True)
            await manager.broadcast({
                "time": datetime.now().strftime("%H:%M:%S"),
                "tf": tf,
                "signals": res_sorted
            })
            await asyncio.sleep(30) # push every 30s via socket
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/scan")
def scan(tf: str = Query("H1")):
    res=[]
    for p,n in zip(PAIRS,NAMES):
        d=calc(p,tf)
        if d: d["name"]=n; res.append(d)
    return sorted(res, key=lambda x:x['score'], reverse=True)
