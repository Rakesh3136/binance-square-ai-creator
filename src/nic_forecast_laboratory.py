"""NIC Forecast Laboratory: competing hypotheses, historical analogues, regime detection and predictive-signal auditing."""
from __future__ import annotations
import json,math,urllib.parse,urllib.request,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/"data/live"
PRED=LIVE/"nic_prediction_engine.json"; OUT=LIVE/"nic_forecast_laboratory.json"; REPORT=ROOT/"data/intelligence/nic_forecast_laboratory_report.json"
BASES=("https://data-api.binance.vision","https://api-gcp.binance.com","https://api1.binance.com","https://api2.binance.com")
MIN=30; H=(6,12,24)
def n(v,d=0.0):
    try:x=float(v); return x if math.isfinite(x) else d
    except:return d
def load(p,d=None):
    try:v=json.loads(p.read_text()); return v if isinstance(v,type(d if d is not None else {})) else (d if d is not None else {})
    except:return d if d is not None else {}
def sym(v): return str(v or "").upper().replace("BINANCE:","").replace("USDT","").strip()
def candles(s):
    q=urllib.parse.urlencode({"symbol":sym(s)+"USDT","interval":"1h","limit":720}); last=None
    for b in BASES:
        try:
            r=urllib.request.urlopen(urllib.request.Request(b+"/api/v3/klines?"+q,headers={"User-Agent":"binance-square-ai-creator/nic-forecast-lab"}),timeout=15)
            raw=json.loads(r.read()); return [{"t":int(x[0]),"h":n(x[2]),"l":n(x[3]),"c":n(x[4]),"v":n(x[7])} for x in raw if isinstance(x,list) and len(x)>=8]
        except Exception as e:last=e
    raise RuntimeError(str(last))
def ema(v,p):
    if not v:return 0
    a=2/(p+1);e=v[0]
    for x in v[1:]:e=a*x+(1-a)*e
    return e
def rsi(v,p=14):
    if len(v)<=p:return 50
    g=[];l=[]
    for a,b in zip(v[-p-1:-1],v[-p:]):
        d=b-a;g.append(max(d,0));l.append(max(-d,0))
    ag=sum(g)/p;al=sum(l)/p
    return 100 if al==0 else 100-100/(1+ag/al)
def feat(rows,i):
    if i<60:return None
    c=[x["c"] for x in rows[:i+1]]; e20=ema(c[-40:],20);e50=ema(c[-60:],50);av=sum(x["v"] for x in rows[i-20:i])/20
    return {"trend":1 if e20>e50 else -1,"momentum":(c[-1]/c[-7]-1)*100,"rsi":rsi(c),"volume_ratio":rows[i]["v"]/av if av else 1,"distance_ema20":(c[-1]/e20-1)*100,"range_position":(c[-1]-min(x["l"] for x in rows[i-20:i+1]))/max(max(x["h"] for x in rows[i-20:i+1])-min(x["l"] for x in rows[i-20:i+1]),1e-12)}
def regime(f):
    if not f:return "UNKNOWN"
    if f["rsi"]>=70 and f["momentum"]>=5:return "TREND_UP_EXTENDED"
    if f["rsi"]<=30 and f["momentum"]<=-5:return "TREND_DOWN_EXTENDED"
    if f["trend"]>0 and f["momentum"]>1:return "TREND_UP"
    if f["trend"]<0 and f["momentum"]<-1:return "TREND_DOWN"
    if f["volume_ratio"]>=2:return "HIGH_FLOW"
    return "RANGE"
def dist(a,b):
    sc={"trend":1,"momentum":5,"rsi":15,"volume_ratio":1.5,"distance_ema20":5,"range_position":.3}
    return math.sqrt(sum(((a[k]-b[k])/sc[k])**2 for k in sc))
def ret(rows,i,h): return None if i+h>=len(rows) else (rows[i+h]["c"]/rows[i]["c"]-1)*100
def run(cand,rows):
    if len(rows)<120:return {"status":"INSUFFICIENT_HISTORY","symbol":sym(cand.get("symbol"))}
    ci=len(rows)-1;cur=feat(rows,ci);reg=regime(cur); pool=[]
    for i in range(60,ci-24):
        f=feat(rows,i);r=ret(rows,i,24)
        if f and r is not None: pool.append((dist(cur,f)*(1.25 if regime(f)!=reg else 1),i,f))
    pool.sort();pool=pool[:80]
    hyps={}
    for side in ("BULLISH","BEARISH"):
        hs={}
        for h in H:
            vals=[ret(rows,i,h) for _,i,_ in pool]; vals=[(x if side=="BULLISH" else -x) for x in vals if x is not None]
            hs[str(h)]={"samples":len(vals),"mean_signed_return":round(sum(vals)/len(vals),4) if vals else None,"hit_rate":round(sum(x>0 for x in vals)/len(vals),4) if vals else None}
        base=[];cond=[]
        for i in range(60,ci-24):
            f=feat(rows,i);x=ret(rows,i,24)
            if not f or x is None:continue
            x=x if side=="BULLISH" else -x;base.append(x)
            if (f["momentum"]>0 if side=="BULLISH" else f["momentum"]<0) and f["volume_ratio"]>=1.2:cond.append(x)
        bh=sum(x>0 for x in base)/len(base) if base else 0;ch=sum(x>0 for x in cond)/len(cond) if cond else 0
        hs["predictivity"]={"eligible":len(cond)>=MIN,"base_samples":len(base),"signal_samples":len(cond),"base_hit_rate":round(bh,4),"signal_hit_rate":round(ch,4),"lift":round(ch-bh,4),"predictive":len(cond)>=MIN and ch>bh+.05}
        hyps[side]={"analogues":len(pool),"forward":hs}
    return {"status":"READY","symbol":sym(cand.get("symbol")),"regime":reg,"current_features":cur,"hypotheses":hyps,"decision_rule":"prefer only hypotheses with >=30 conditional events and >5pp out-of-sample base-rate lift; otherwise WAIT"}
def main():
    cs=load(PRED).get("candidates") or [];res=[];fails=[]
    for c in cs[:12]:
        try:res.append(run(c,candles(c.get("symbol"))))
        except Exception as e:fails.append({"symbol":sym(c.get("symbol")),"error":type(e).__name__+":"+str(e)})
        time.sleep(.05)
    data={"schema":"NIC-FORECAST-LAB-1.0","generated_at":datetime.now(timezone.utc).isoformat(),"results":res,"failures":fails,"policy":{"competing_hypotheses":True,"historical_analogues_out_of_sample":True,"regime_matching":True,"base_rate_lift_required":True,"minimum_analogue_events":MIN,"no_guaranteed_forecast":True,"publication_gate_immutable":True}}
    OUT.write_text(json.dumps(data,indent=2));REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text(json.dumps({"schema":"NIC-FORECAST-LAB-1.0","generated_at":data["generated_at"],"ready":sum(x["status"]=="READY" for x in res),"failures":len(fails),"predictive_claims":sum(1 for x in res if x["status"]=="READY" for h in x["hypotheses"].values() if h["forward"]["predictivity"]["predictive"]),"policy":"Predictive requires >=30 conditional events and >5pp lift over neutral base rate."},indent=2));print(json.dumps({"ready":len(res),"failures":len(fails)}))
if __name__=="__main__":main()
