"""Human analyst-style Binance Square chart renderer v6.

Presentation-only. Prices and candles come exclusively from the frozen snapshot.
The design avoids dashboard cards and machine-like setup dumps: chart first,
quiet annotations, compact levels, and one contextual observation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data/live/historical_setup_snapshot.json"
OUT = ROOT / "data/live/visual.png"
META = ROOT / "data/live/visual_metadata.json"
W, H = 1080, 1350

BG="#070b10"; PANEL="#0b1118"; GRID="#1b2631"; TEXT="#eef2f6"; MUTED="#7f8b96"
UP="#45d39a"; DOWN="#ff6675"; LEVEL="#d8b15d"; TARGET="#77a9e8"

def f(size,bold=False):
    p=Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(p,size) if p.exists() else ImageFont.load_default()

def n(v):
    try:return float(v)
    except:return None

def fmt(v):
    x=n(v)
    if x is None:return "—"
    if abs(x)>=1000:return f"{x:,.0f}"
    if abs(x)>=100:return f"{x:,.2f}"
    if abs(x)>=1:return f"{x:.4f}".rstrip("0").rstrip(".")
    if abs(x)>=.01:return f"{x:.6f}".rstrip("0").rstrip(".")
    return f"{x:.8f}".rstrip("0").rstrip(".")

def pct(a,b):
    return None if a in (None,0) or b is None else (b/a-1)*100

def line(d,x1,y,x2,col,width=2,dash=12,gap=9):
    x=int(x1)
    while x<int(x2):
        d.line((x,y,min(x+dash,int(x2)),y),fill=col,width=width); x+=dash+gap

def main():
    s=json.loads(SNAP.read_text(encoding="utf-8"))
    if s.get("status")!="FROZEN" or s.get("lookahead_protection") is not True: raise SystemExit("snapshot is not frozen")
    candles=(s.get("candles_1h") or [])[-48:]
    if len(candles)<12: raise SystemExit("too few historical candles")
    p=s.get("prediction") or {}; side=str(p.get("direction") or "").upper(); symbol=str(s.get("symbol") or "").upper()
    signal=n(s.get("signal_price")); entry=n(p.get("entry_trigger")); tp1=n(p.get("tp1")); tp2=n(p.get("tp2")); sl=n(p.get("sl"))
    if side not in {"LONG","SHORT"} or any(x is None for x in (signal,entry,tp1,tp2,sl)): raise SystemExit("frozen prediction contract incomplete")
    vals=[]
    rows=[]
    for c in candles:
        o,h,l,cl=[n(c.get(k)) for k in ("open","high","low","close")]; v=n(c.get("volume")) or 0
        if None not in (o,h,l,cl): rows.append((o,h,l,cl,v))
    if len(rows)<12: raise SystemExit("historical candle data incomplete")
    last=rows[-1][3]; prior=rows[-2][3]; move=pct(rows[-7][3],last)
    recent=rows[-8:]; recent_hi=max(r[1] for r in recent); recent_lo=min(r[2] for r in recent); maxv=max(r[4] for r in rows) or 1
    vals=[x for r in rows for x in r[1:3]]+[signal,entry,tp1,tp2,sl]; lo=min(vals); hi=max(vals); pad=max((hi-lo)*.06,abs(hi)*.002,1e-12); lo-=pad; hi+=pad

    im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im)
    title=f(40,True); head=f(22,True); body=f(21); small=f(17); tiny=f(14)
    d.text((56,34),f"${symbol}  ·  1H",font=title,fill=TEXT)
    side_col=UP if side=="LONG" else DOWN
    d.text((W-56-d.textbbox((0,0),side,font=head)[2],42),side,font=head,fill=side_col)
    d.text((56,84),"Decision map · completed candles",font=small,fill=MUTED)
    context=f"6-candle {move:+.1f}%" if move is not None else "completed-candle context"
    d.text((W-56-d.textbbox((0,0),context,font=small)[2],84),context,font=small,fill=MUTED)

    L,R,T,B=56,1024,132,955; V0,V1=985,1088; ch=B-T; cw=R-L
    d.rounded_rectangle((L,T,R,V1),18,fill=PANEL,outline="#1e2a35",width=1)
    def py(x): return B-(x-lo)/(hi-lo)*ch
    for i in range(6):
        y=T+i*ch/5; val=hi-(hi-lo)*i/5
        d.line((L+16,y,R-16,y),fill=GRID,width=1); d.text((R-105,y-8),fmt(val),font=tiny,fill=MUTED)
    rh,rl=py(recent_hi),py(recent_lo); d.rectangle((L+16,min(rh,rl),R-16,max(rh,rl)),fill="#0f171f")
    d.text((L+26,min(rh,rl)+9),"RECENT RANGE",font=tiny,fill="#586675")

    step=(cw-42)/len(rows); bodyw=max(7,int(step*.5))
    for i,(o,h,l,cl,v) in enumerate(rows):
        x=L+21+(i+.5)*step; yo,yh,yl,yc=map(py,(o,h,l,cl)); col=UP if cl>=o else DOWN
        d.line((x,yh,x,yl),fill=col,width=2); a,b=sorted((yo,yc)); d.rectangle((x-bodyw/2,a,x+bodyw/2,max(b,a+3)),fill=col)
        bar=76*v/maxv; d.rectangle((x-bodyw/2,V1-bar,x+bodyw/2,V1),fill=col)
    d.text((L+22,V0+2),"VOLUME",font=tiny,fill=MUTED)

    # Quiet analyst levels: no large cards, no arrows, no dashboard boxes.
    levels=[("TP2",tp2,TARGET),("TP1",tp1,UP),("DECISION",entry,LEVEL),("INVALIDATION",sl,DOWN)]
    for lab,val,col in levels:
        y=py(val)
        if T<=y<=B:
            line(d,L+18,y,R-132,col,2 if lab=="DECISION" else 1)
            d.text((R-118,max(T,min(B-18,y-8)),),f"{lab}  {fmt(val)}",font=tiny,fill=col)
    sy=py(signal)
    if T<=sy<=B:
        d.ellipse((L+18,sy-4,L+26,sy+4),fill=TEXT); d.text((L+34,sy-8),f"last {fmt(signal)}",font=tiny,fill=TEXT)

    # Context below chart is intentionally conversational, derived only from the snapshot.
    relation=pct(last,entry)
    if side=="LONG":
        sentence=f"The setup only becomes interesting if 1H can reclaim {fmt(entry)} and hold it."
    else:
        sentence=f"The setup only becomes interesting if 1H rejects {fmt(entry)} and fails to reclaim it."
    d.text((56,1130),sentence,font=body,fill=TEXT)
    rel=(f"Last close is {abs(relation):.1f}% {'below' if relation<0 else 'above'} the decision level." if relation is not None else "Decision level is taken from the frozen contract.")
    d.text((56,1170),rel,font=small,fill=MUTED)
    d.text((56,1212),f"Range {fmt(recent_lo)} — {fmt(recent_hi)}  ·  snapshot {fmt(signal)}",font=small,fill=MUTED)
    d.text((56,1260),"Conditional setup · invalidation matters · no guarantee",font=tiny,fill=MUTED)
    d.text((56,1292),"Source: frozen 1H Binance OHLCV snapshot",font=tiny,fill="#56616c")

    OUT.parent.mkdir(parents=True,exist_ok=True); im.save(OUT,"PNG",optimize=True)
    rr=abs(tp2-entry)/abs(sl-entry) if sl!=entry else None
    meta={"status":"HISTORICAL_SNAPSHOT_CREATED","renderer":"analyst_square_chart_renderer_v7",
        "signal_created_at":s.get("signal_created_at"),
        "signal_created_at_ms":s.get("signal_created_at_ms"),
        "data_cutoff":s.get("data_cutoff"),
        "snapshot_frozen_at":s.get("frozen_at"),"provider":"Local historical OHLCV renderer","base_symbol":symbol,"timeframe":"1H","candle_count":len(rows),"candle_policy":"completed_candles_only","lookahead_protection":True,"visual_style":"human_analyst_chart_first","prediction_markings":{"direction":side,"entry_trigger":entry,"tp1":tp1,"tp2":tp2,"sl":sl,"signal_price":signal,"risk_reward":rr},"derived_context":{"recent_high":recent_hi,"recent_low":recent_lo,"last_close":last,"six_candle_move_pct":move},"generated_at":datetime.now(timezone.utc).isoformat()}
    META.write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8"); print(json.dumps(meta,indent=2))

if __name__=="__main__": main()
