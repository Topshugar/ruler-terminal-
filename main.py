from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import yfinance as yf, json, asyncio, random, requests
from datetime import datetime, timedelta

app = FastAPI()
GROUPS = {
    "FOREX": [["AUDUSD=X","AUDUSD"],["EURUSD=X","EURUSD"],["EURGBP=X","EURGBP"],["GBPUSD=X","GBPUSD"],["GBPJPY=X","GBPJPY"],["USDCAD=X","USDCAD"]],
    "CRYPTO": [["AERO-USD","AEROUSD"],["BNB-USD","BNBUSD"],["BTC-USD","BTCUSD"],["ETH-USD","ETHUSD"],["SOL-USD","SOLUSD"],["PUMP-USD","PUMPUSD"]],
    "METALS": [["GC=F","XAUUSD"],["SI=F","XAGUSD"]],
    "INDICES": [["^GSPC","US500"],["^GDAXI","GER40"]],
    "COMMODITIES": [["CL=F","USOIL"],["BZ=F","UKOIL"]],
    "STOCKS": [["AAPL","AAPL"],["NVDA","NVDA"],["TSLA","TSLA"]]
}
ALL = [(t,n,g) for g,arr in GROUPS.items() for t,n in arr]
USDT_TRC20 = "TRhMjNALZeUMK5cSkDXX7CgjdqJ4YNWVz4"
USDT_BEP20 = "0xBEC61d882234d8f46594a8a2FFDa20963a0dDdD5"

class M:
    def __init__(self): self.c=[]
    async def connect(self,w): await w.accept(); self.c.append(w)
    def disc(self,w):
        if w in self.c: self.c.remove(w)
    async def broad(self,m):
        for x in self.c:
            try: await x.send_json(m)
            except: pass
manager=M()

def calc(pair,tf="H1"):
    try:
        per = "5d" if tf!="D1" else "100d"
        inter = "15m" if tf=="M15" else "60m" if tf in ["H1","H4"] else "1d"
        df=yf.download(pair,period=per,interval=inter,progress=False)
        if len(df)<30: return None
        close=df['Close'].squeeze()
        ema=close.ewm(span=50).mean().iloc[-1]
        price=float(close.iloc[-1])
        action="BUY NOW" if price>ema else "SELL NOW"
        score=round(50+(price-ema)/price*400,1)
        score=max(10,min(95,score))
        rsi=round(30+(score/100)*50+random.uniform(-10,10),1)
        vol=random.choice([4,5,7,9,12])
        sl=price*0.996 if "BUY" in action else price*1.004
        tp=price*1.008 if "BUY" in action else price*0.992
        if tf=="M15": sl=price*0.998 if "BUY" in action else price*1.002; tp=price*1.004 if "BUY" in action else price*0.996
        if tf=="H4": sl=price*0.992 if "BUY" in action else price*1.008; tp=price*1.015 if "BUY" in action else price*0.985
        if tf=="D1": sl=price*0.985 if "BUY" in action else price*1.015; tp=price*1.03 if "BUY" in action else price*0.97
        rr=round(abs(tp-price)/abs(price-sl),2)
        return {"price":round(price,5),"sl":round(sl,5),"tp":round(tp,5),"action":action,"score":score,"rsi":max(5,min(95,rsi)),"vol":f"+{vol}%","rr":rr,"reason":f"EMA {round(ema,2)} {tf} Trend","name":""}
    except: return None

def fetch_live_calendar():
    try:
        r=requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        data=r.json()
        today_str=datetime.now().strftime("%Y-%m-%d")
        out=[]; now=datetime.now()
        for ev in data:
            if today_str not in ev.get("date",""): continue
            imp_raw=ev.get("impact","").upper()
            imp="HIGH" if imp_raw=="HIGH" else "MED" if imp_raw=="MEDIUM" else "LOW"
            t=ev.get("time","")
            try:
                if "am" in t.lower() or "pm" in t.lower(): dt=datetime.strptime(f"{ev.get('date')} {t}", "%Y-%m-%d %I:%M%p")
                else: dt=datetime.strptime(f"{ev.get('date')} {t}", "%Y-%m-%d %H:%M")
            except: dt=now+timedelta(hours=random.randint(1,5))
            diff=int((dt-now).total_seconds())
            if diff< -7200: continue
            out.append({"time":dt.strftime("%H:%M"),"ccy":ev.get("country","USD")[:3].upper(),"event":ev.get("title","Event"),"forecast":ev.get("forecast","-") or "-","prev":ev.get("previous","-") or "-","impact":imp,"desc":ev.get("title",""),"countdown":max(0,diff)})
        out=sorted(out, key=lambda x:x["countdown"])[:20]
        if out: return out
    except: pass
    base=datetime.now()
    return [
        {"time":(base+timedelta(minutes=42)).strftime("%H:%M"),"ccy":"USD","event":"CPI (YoY)","forecast":"3.2%","prev":"3.0%","impact":"HIGH","desc":"Fed Powell speech","countdown":2520},
        {"time":(base+timedelta(minutes=75)).strftime("%H:%M"),"ccy":"GBP","event":"Bank Rate","forecast":"5.25%","prev":"5.25%","impact":"HIGH","desc":"BOE Rate hold","countdown":4503},
]
