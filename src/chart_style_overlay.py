"""Add a bounded analyst-style overlay to the local historical chart.

This is presentation-only. It never changes the frozen prediction contract.
Derived Fibonacci/trend context is explicitly labeled as derived context.
"""
from __future__ import annotations
import json, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
STYLE=ROOT/'data/live/visual_style_plan.json'; META=ROOT/'data/live/visual_metadata.json'; SNAP=ROOT/'data/live/historical_setup_snapshot.json'; IMG=ROOT/'data/live/visual.png'

def load(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {}
def font(size,bold=False):
    p=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    return ImageFont.truetype(p,size) if p.exists() else ImageFont.load_default()
def main():
    style=load(STYLE); meta=load(META); snap=load(SNAP)
    if not IMG.exists() or not isinstance(meta,dict): return 0
    if 'analyst_square_chart_renderer' not in str(meta.get('renderer') or ''): print('Overlay skipped: non-local/TradingView renderer'); return 0
    im=Image.open(IMG).convert('RGB'); d=ImageDraw.Draw(im); W,H=im.size
    rows=[]
    for c in (snap.get('candles_1h') or [])[-48:]:
        try: rows.append((float(c['high']),float(c['low'])))
        except Exception: pass
    if len(rows)<12:return 0
    pad=60; top=130; bottom=min(960,H-220); plot_h=max(100,bottom-top); lo=min(x[1] for x in rows); hi=max(x[0] for x in rows); span=max(hi-lo,1e-12)
    def x(i): return pad+(W-2*pad)*(i/(len(rows)-1))
    def y(v): return bottom-(v-lo)/span*plot_h
    mode=str(style.get('style') or 'decision_map')
    label_font=font(15,True); small=font(13)
    # Derived range Fibonacci context, modeled after analyst charts such as the
    # supplied reference image. These levels are visual context, not trade targets.
    if mode in {'fibonacci_context','structure_fibonacci'}:
        low_i=min(range(len(rows)),key=lambda i:rows[i][1]); high_i=max(range(len(rows)),key=lambda i:rows[i][0])
        low=rows[low_i][1]; high=rows[high_i][0]
        if high_i < low_i: low,high=high,low; low_i,high_i=high_i,low_i
        for ratio in (0.236,0.382,0.5,0.618,0.786):
            v=high-(high-low)*ratio; yy=y(v)
            if top<=yy<=bottom:
                d.line((W*.55,yy,W-75,yy),fill=(210,177,93),width=1)
                d.text((W-190,yy-8),f'{ratio:.3f}  {v:.8g}',font=small,fill=(210,177,93))
        d.text((pad,top+8),'DERIVED FIBONACCI CONTEXT',font=label_font,fill=(210,177,93))
    if mode in {'structure_breakout','structure_fibonacci','trendline'}:
        # Least-squares trend guide through candle highs; presentation only.
        pts=rows[-32:]
        xs=list(range(len(pts))); ys=[p[0] for p in pts]; mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
        den=sum((q-mx)**2 for q in xs) or 1; slope=sum((q-mx)*(v-my) for q,v in zip(xs,ys))/den; intercept=my-slope*mx
        a=slope*0+intercept; b=slope*(len(pts)-1)+intercept
        d.line((x(len(rows)-len(pts)),y(a),x(len(rows)-1),y(b)),fill=(225,225,225),width=3)
        d.text((pad,top+34),'TREND GUIDE · DERIVED FROM COMPLETED CANDLES',font=small,fill=(220,220,220))
    if mode=='volume_regime':
        vols=[]
        for c in (snap.get('candles_1h') or [])[-48:]:
            try:vols.append(float(c.get('volume',0)))
            except Exception:vols.append(0)
        if vols:
            avg=sum(vols)/len(vols); recent=sum(vols[-6:])/max(1,len(vols[-6:])); ratio=recent/avg if avg else 0
            d.rounded_rectangle((pad,H-150,W-pad,H-70),12,fill=(12,18,25),outline=(45,55,65))
            d.text((pad+18,H-130),f'VOLUME REGIME  ·  recent/48h avg {ratio:.2f}x',font=small,fill=(230,230,230))
    META.write_text(json.dumps({**meta,'visual_style':mode,'overlay_applied':True,'derived_overlay':mode in {'fibonacci_context','structure_breakout','structure_fibonacci','trendline'}},indent=2)+'\n',encoding='utf-8')
    im.save(IMG,'PNG',optimize=True); print(json.dumps({'status':'OK','style':mode,'overlay_applied':True}))
    return 0
if __name__=='__main__':raise SystemExit(main())
