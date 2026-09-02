"""TradingView eligibility gate for Creator 4.2.
Checks candidate symbols against TradingView's public symbol pages before the
asset becomes authoritative. Unsupported symbols are removed from selection;
the gate never invents a replacement.
"""
from __future__ import annotations
import json,re,urllib.request,urllib.error
from pathlib import Path

PREFLIGHT=Path("data/live/editorial_preflight.json")
OUT=Path("data/live/tradingview_asset_gate.json")

def base_symbol(value):
    s=re.sub(r"USDT(?:\.P)?$","",str(value or "").upper().replace("$","").strip())
    return s if re.fullmatch(r"[A-Z0-9]{1,15}",s) else ""

def check_tradingview(symbol):
    if symbol in {"XAUUSD","XAGUSD"}:
        url=f"https://www.tradingview.com/symbols/{symbol}/"
    else:
        url=f"https://www.tradingview.com/symbols/{symbol}USDT/?exchange=BINANCE"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 Creator4.2 TradingView eligibility check"})
        with urllib.request.urlopen(req,timeout=12) as r:
            body=r.read(180000).decode("utf-8","ignore").upper()
        wanted=symbol if symbol in {"XAUUSD","XAGUSD"} else symbol+"USDT"
        ok=(wanted in body and "TRADINGVIEW" in body)
        return {"ok":ok,"url":url,"reason":"symbol_page_confirmed" if ok else "symbol_page_did_not_confirm_symbol"}
    except Exception as exc:
        return {"ok":False,"url":url,"reason":f"request_failed:{type(exc).__name__}"}

def main():
    data=json.loads(PREFLIGHT.read_text(encoding="utf-8")) if PREFLIGHT.exists() else {}
    selected=data.get("selected_opportunity") or {}
    pool=data.get("candidate_pool") or []
    candidates=[]
    if isinstance(selected,dict):
        candidates.append(selected)
    for item in pool:
        if isinstance(item,dict):
            candidates.append(item)
    seen=set();checked=[];chosen=None
    for item in candidates:
        raw=item.get("symbol") or item.get("topic")
        sym=base_symbol(raw)
        if not sym or sym in seen: continue
        seen.add(sym)
        result=check_tradingview(sym)
        checked.append({"symbol":sym,**result})
        if result["ok"] and chosen is None:
            chosen=item
    if chosen and base_symbol(chosen.get("symbol") or chosen.get("topic")) != base_symbol(selected.get("symbol") or selected.get("topic")):
        data["selected_opportunity"]=chosen
        data["reason"]="tradingview_supported_candidate_after_asset_gate"
    elif not chosen:
        data["selected_opportunity"]=None
        data["run_ai"]=False
        data["reason"]="no_tradingview_supported_candidate"
    data["tradingview_asset_gate"]={"version":"4.2","checked":checked,"selected_symbol":base_symbol((data.get("selected_opportunity") or {}).get("symbol") or (data.get("selected_opportunity") or {}).get("topic"))}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data["tradingview_asset_gate"],indent=2,ensure_ascii=False),encoding="utf-8")
    PREFLIGHT.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(data["tradingview_asset_gate"],indent=2,ensure_ascii=False))
    if not chosen: raise SystemExit(2)

if __name__=="__main__": raise SystemExit(main())
