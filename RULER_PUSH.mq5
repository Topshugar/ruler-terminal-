//+------------------------------------------------------------------+
//| RulerTerminalPush.mq5 |
//| Pushes live prices to https://ruler-terminal.onrender.com |
//| Triple-Confluence Engine: 21 EMA / 21 BB / 21 RSI / 200 SMA |
//+------------------------------------------------------------------+
#property strict

input string InpUrl = "https://ruler-terminal.onrender.com/api/mt5/prices";
input int InpTimerSec = 3; // push every 3 sec

string Symbols[] = {
 "XAUUSD","XAGUSD",
 "BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD",
 "EURUSD","GBPUSD","AUDUSD","USDCAD",
 "USOIL","UKOIL",
 "US500","GER40",
 "US10Y","US02Y","DE10Y","UK10Y"
};

//+------------------------------------------------------------------+
int OnInit()
{
 EventSetTimer(InpTimerSec);
 Print("RULER TERMINAL PUSHER STARTED -> ", InpUrl);
 PushPrices();
 return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
 EventKillTimer();
}

void OnTimer()
{
 PushPrices();
}

//+------------------------------------------------------------------+
void PushPrices()
{
 string json = "[";
 int count=0;
 for(int i=0; i<ArraySize(Symbols); i++)
 {
  string sym = Symbols[i];
  // Try to get symbol with broker suffix - search
  string found = FindSymbol(sym);
  if(found=="") continue;

  double bid = SymbolInfoDouble(found, SYMBOL_BID);
  double ask = SymbolInfoDouble(found, SYMBOL_ASK);
  if(bid==0 || ask==0) continue;

  if(count>0) json+=",";
  json += StringFormat("{\"symbol\":\"%s\",\"bid\":%.5f,\"ask\":%.5f}", sym, bid, ask);
  count++;
 }
 json += "]";

 if(count==0)
 {
  Print("RULER: No symbols found. Check Market Watch");
  return;
 }

 char data[];
 StringToCharArray(json, data, 0, StringLen(json), CP_UTF8);
 ArrayResize(data, StringLen(json));

 char result[];
 string headers = "Content-Type: application/json\r\n";
 string res_headers;
 int res = WebRequest("POST", InpUrl, headers, 10000, data, result, res_headers);

 if(res==200)
  Print("RULER PUSH OK: ", count, " pairs");
 else
  Print("RULER PUSH FAILED: ", res, " - ", CharArrayToString(result));
}

// Find symbol with suffix like XAUUSD.a, XAUUSDm, BTCUSD.s etc
string FindSymbol(string base)
{
 if(SymbolSelect(base, true)) return base;
 for(int i=0; i<SymbolsTotal(false); i++)
 {
  string name = SymbolName(i,false);
  if(StringFind(name, base)==0) // starts with base
  {
   SymbolSelect(name,true);
   return name;
  }
 }
 return "";
}
