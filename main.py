 from fastapi import FastAPI
from fastapi.responses import HTMLResponse
app = FastAPI()
@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse("<html><body style='background:#05070a;color:#8aff77;font-family:monospace;padding:20px'><h1>RULER TERMINAL v1.1</h1><h2>LIBRARY - 6 GROUPS</h2><div style='display:grid;grid-template-columns:1fr 1fr;gap:10px'><div style='border:1px solid #8aff6a;padding:14px'>FOREX [6 PAIRS]<br>78% win<br><br>-> ENTER</div><div style='border:1px solid #8aff6a;padding:14px'>CRYPTO [6 PAIRS]<br>82% win<br><br>-> ENTER</div><div style='border:1px solid #8aff6a;padding:14px'>METALS [2 PAIRS]<br>75% win</div><div style='border:1px solid #8aff6a;padding:14px'>INDICES [2]</div><div style='border:1px solid #8aff6a;padding:14px'>COMMODITIES [2]</div><div style='border:1px solid #8aff6a;padding:14px'>STOCKS [3]</div></div><h3>CALENDAR: 00:42:00 COUNTDOWN USD CPI HIGH</h3><h3>NEWS: WAR - Israel-Iran LIVE | INFLATION - US CPI 3.4%</h3></body></html>")
@app.get("/health")
def health():
    return {"ok": True}
