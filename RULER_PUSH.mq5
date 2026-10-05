#property strict
input string API_URL = "https://YOUR-APP-NAME.onrender.com/api/mt5/prices";

void OnTimer()
{
   string syms[] = {"XAUUSD","XAGUSD","EURUSD","GBPUSD","AUDUSD","USDCAD","BTCUSD","ETHUSD","SOLUSD","XRPUSD","BNBUSD","ADAUSD","DOGEUSD","AVAXUSD","USOIL","UKOIL","US500","GER40","US10Y"};
   string json="[";
   for(int i=0;i<ArraySize(syms);i++)
   {
      double bid = SymbolInfoDouble(syms[i], SYMBOL_BID);
      double ask = SymbolInfoDouble(syms[i], SYMBOL_ASK);
      if(bid==0) bid = iClose(syms[i], PERIOD_M1, 0);
      if(bid==0) continue;
      if(i>0) json+=",";
      json+="{ \"symbol\":\""+syms[i]+"\",\"bid\":"+DoubleToString(bid,5)+",\"ask\":"+DoubleToString(ask,5)+"}";
   }
   json+="]";

   char post[], result[];
   string headers="Content-Type: application/json\r\n";
   StringToCharArray(json, post, 0, StringLen(json));
   int res = WebRequest("POST", API_URL, headers, 10000, post, result, headers);
   Print("PUSH ", res, " ", json);
}

int OnInit(){ EventSetTimer(2); return(INIT_SUCCEEDED); }
void OnDeinit(const int reason){ EventKillTimer(); }
void OnTick(){}
