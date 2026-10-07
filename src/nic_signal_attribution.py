"""NIC Counterfactual Signal Attribution: walk-forward ablation of forecast signal families."""
from __future__ import annotations
import json,math,urllib.parse,urllib.request
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/"data/live"; INT=ROOT/"data/intelligence"
PRED=LIVE/"nic_prediction_engine.json"; OUT=INT/"nic_signal_attribution.json"
BASES=("https://data-api.binance.vision","https://api-gcp.binance.com","https://api1.binance.com","https://api2.binance.com")
FEATURES=("trend_aligned","momentum_aligned","volume_expansion","rsi_not_extreme","near_ema20")
MIN=30; HORIZON=24
def n(v,d=0.0):
    try:x=float(v); return x if math.isfinite(x) else d
    except:return d
def sym(v): return str(v or "").upper().replace("BINANCE:","").replace("USDT","").strip()
def candles(s,limit=720):
    q=urllib.parse.urlencode({"symbol":sym(s)+"USDT","interval":"1h","limit":limit}); last=None
    for b in BASES:
        try:
            r=urllib.request.urlopen(urllib.request.Request(b+"/api/v3/klines?"+q,headers={"User-Agent":"binance-square-ai-creator/nic-attribution"}),timeout=15)
            raw=json.loads(r.read())
            return [{"c":n(x[4]),"v":n(x[7]),"h":n(x[2]),"l":n(x[3])} for x in raw if isinstance(x,list) and len(x)>=8]
        except Exception as e:last=e
    raise RuntimeError(str(last))
def ema(v,p):
    if not v:return 0
    a=2/(p+1); e=v[0]
    for x in v[1:]:e=a*x+(1-a)*e
    return e
def rsi(v,p=14):
    if len(v)<=p:return 50
    g=[];l=[]
    for a,b in zip(v[-p-1:-1],v[-p:]):
        d=b-a;g.append(max(d,0));l.append(max(-d,0))
    ag=sum(g)/p;al=sum(l)/p
    return 100 if al==0 else 100-100/(1+ag/al)
def flags(rows,i,side):
    c=[x["c"] for x in rows[:i+1]]
    e20=ema(c[-40:],20);e50=ema(c[-60:],50); av=sum(x["v"] for x in rows[i-20:i])/20
    momentum=(c[-1]/c[-7]-1)*100; rr=rsi(c); vr=rows[i]["v"]/av if av else 1
    return {
      "trend_aligned": (e20>e50 if side=="BULLISH" else e20<e50),
      "momentum_aligned": (momentum>0 if side=="BULLISH" else momentum<0),
      "volume_expansion": vr>=1.2,
      "rsi_not_extreme": (rr<70 if side=="BULLISH" else rr>30),
      "near_ema20": abs(c[-1]/e20-1)*100<=5,
    }
def score(fs,excluded=None):
    active=[v for k,v in fs.items() if k!=excluded]
    return sum(bool(x) for x in active)/len(active) if active else .5
def metrics(probs,hits):
    if not probs:return {"samples":0,"brier":None,"log_loss":None}
    eps=1e-9
    b=sum((p-y)**2 for p,y in zip(probs,hits))/len(probs)
    ll=-sum(y*math.log(max(p,eps))+(1-y)*math.log(max(1-p,eps)) for p,y in zip(probs,hits))/len(probs)
    return {"samples":len(probs),"brier":round(b,6),"log_loss":round(ll,6)}
def attribution(rows,side):
    base_p=[];hits=[]
    for i in range(120,len(rows)-HORIZON):
        f=flags(rows,i,side); future=rows[i+HORIZON]["c"]/rows[i]["c"]-1
        base_p.append(score(f)); hits.append(1 if (future>0 if side=="BULLISH" else future<0) else 0)
    baseline=metrics(base_p,hits); cells={}
    for feature in FEATURES:
        ps=[score(flags(rows,i,side),feature) for i in range(120,len(rows)-HORIZON)]
        m=metrics(ps,hits)
        db=m["brier"]-baseline["brier"]; dl=m["log_loss"]-baseline["log_loss"]
        if m["samples"]<MIN: state="UNKNOWN"; mult=.5
        elif db>0.01 or dl>0.02: state="CORE"; mult=1.0
        elif db<-0.01 or dl<-0.02: state="HARMFUL"; mult=.25
        elif abs(db)<=.003 and abs(dl)<=.006: state="REDUNDANT"; mult=.75
        else: state="SUPPORTING"; mult=.9
        cells[feature]={"feature":feature,"side":side,"samples":m["samples"],"baseline_brier":baseline["brier"],"ablated_brier":m["brier"],"brier_delta":round(db,6),"baseline_log_loss":baseline["log_loss"],"ablated_log_loss":m["log_loss"],"log_loss_delta":round(dl,6),"state":state,"trust_multiplier":mult}
    return {"side":side,"baseline":baseline,"cells":cells}
def main():
    candidates=(json.loads(PRED.read_text()).get("candidates") or [])[:12]; allcells={}; failures=[]
    for c in candidates:
        try:
            rows=candles(c.get("symbol"))
            if len(rows)<120+HORIZON: continue
            for side in ("BULLISH","BEARISH"):
                a=attribution(rows,side)
                for f,v in a["cells"].items():
                    allcells[f"{sym(c.get('symbol'))}|{side}|{f}"]={**v,"symbol":sym(c.get("symbol"))}
        except Exception as e: failures.append({"symbol":sym(c.get("symbol")),"error":type(e).__name__+":"+str(e)})
    payload={"schema":"NIC-SIGNAL-ATTRIBUTION-1.0","generated_at":datetime.now(timezone.utc).isoformat(),"minimum_events":MIN,"horizon_hours":HORIZON,"cells":allcells,"failures":failures,
             "states":["CORE","SUPPORTING","REDUNDANT","HARMFUL","UNKNOWN"],"policy":"Walk-forward ablation measures incremental predictive contribution. It is advisory, requires sufficient out-of-sample observations, and cannot bypass timing, diversity, cooldown, risk, visual truth, or publication gates."}
    OUT.write_text(json.dumps(payload,indent=2)); print(json.dumps({"cells":len(allcells),"failures":len(failures)}))
if __name__=="__main__": main()
