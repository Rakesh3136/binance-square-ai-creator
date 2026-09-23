"""Professional mobile-first Binance Square Signal-First setup chart.

All displayed market values remain bound to the immutable historical snapshot.
The renderer only improves presentation; it never creates market levels.
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/'data/live/historical_setup_snapshot.json'
OUT=ROOT/'data/live/visual.png'
META=ROOT/'data/live/visual_metadata.json'
W,H=1080,1350
L,R,T,B=70,70,185,235
CW,CH=W-L-R,790


def ft(size,bold=False):
    p='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(p,size) if Path(p).exists() else ImageFont.load_default()

def fmt(v):
    if v is None:return '—'
    x=float(v)
    if abs(x)>=100:return f'{x:.2f}'
    if abs(x)>=1:return f'{x:.4f}'
    if abs(x)>=.01:return f'{x:.6f}'
    return f'{x:.8f}'

def main():
    s=json.loads(SNAP.read_text(encoding='utf-8'))
    if s.get('status')!='FROZEN' or s.get('lookahead_protection') is not True: raise SystemExit('snapshot is not frozen')
    cs=s.get('candles_1h') or []
    if len(cs)<3: raise SystemExit('too few historical candles')
    cs=cs[-48:]
    p=s.get('prediction') or {}
    side=str(p.get('direction') or '').upper()
    sym=str(s.get('symbol') or '').upper()
    signal=float(s['signal_price']); entry=p.get('entry_trigger'); tp1=p.get('tp1'); tp2=p.get('tp2'); sl=p.get('sl')
    vals=[float(c['low']) for c in cs]+[float(c['high']) for c in cs]+[signal]
    for v in (entry,tp1,tp2,sl):
        if v is not None: vals.append(float(v))
    lo,hi=min(vals),max(vals); pad=max((hi-lo)*.08,abs(hi)*.003,1e-12); lo-=pad; hi+=pad

    img=Image.new('RGB',(W,H),'#0b0f14'); d=ImageDraw.Draw(img)
    title=ft(46,True); h1=ft(31,True); h2=ft(25,True); body=ft(24); sm=ft(20); tiny=ft(16); label=ft(17,True)

    # Strong Square-native header.
    d.text((L,34),f'${sym}',font=title,fill='#f8fafc')
    d.text((L,92),'1H TRADE SETUP  •  COMPLETED CANDLES',font=h2,fill='#94a3b8')
    badge=f' {"LONG" if side=="LONG" else "SHORT"} '
    bw=d.textbbox((0,0),badge,font=h1)[2]+42
    bx=W-R-bw
    badge_fill='#153b2c' if side=='LONG' else '#4a2027'
    badge_text='#62e6a4' if side=='LONG' else '#ff7180'
    d.rounded_rectangle((bx,31,W-R,86),radius=14,fill=badge_fill)
    d.text((bx+21,43),badge,font=h1,fill=badge_text)
    d.text((L,132),'Frozen setup • levels are taken only from the validated prediction contract',font=tiny,fill='#64748b')

    x0,x1=L,W-R; y0,y1=T,T+CH
    d.rounded_rectangle((x0-18,y0-18,x1+18,y1+18),radius=14,fill='#0f151c',outline='#263241',width=2)
    def py(v): return y1-(float(v)-lo)/(hi-lo)*CH
    # Grid.
    for i in range(7):
        y=y0+i*CH/6; val=hi-(hi-lo)*i/6
        d.line((x0,y,x1,y),fill='#1b2530',width=1)
        d.text((x1+8,y-9),fmt(val),font=tiny,fill='#64748b')

    # Risk/reward zones first, then candles above them.
    def zone(a,b,fill):
        if a is None or b is None:return
        ya,yb=py(a),py(b); d.rectangle((x0,min(ya,yb),x1,max(ya,yb)),fill=fill)
    if entry is not None and tp2 is not None: zone(entry,tp2,'#10261f')
    if sl is not None and entry is not None: zone(sl,entry,'#2a171b')

    n=len(cs); step=CW/n; bwc=max(8,int(step*.62))
    for i,c in enumerate(cs):
        cx=x0+(i+.5)*step
        yo,yc,yh,yl=map(py,[c['open'],c['close'],c['high'],c['low']])
        up=float(c['close'])>=float(c['open'])
        wick='#35d58a' if up else '#ff5968'
        d.line((cx,yh,cx,yl),fill=wick,width=3)
        top,bot=sorted((yo,yc))
        d.rounded_rectangle((cx-bwc/2,top,cx+bwc/2,max(bot,top+3)),radius=2,fill=wick)

    # Clear horizontal trade levels, labels and values.
    levels=[('ENTRY',entry,'#63a9ff',4),('TP1',tp1,'#35d58a',3),('TP2',tp2,'#35d58a',3),('SL / INVALIDATION',sl,'#ff5968',4)]
    for name,v,stroke,width in levels:
        if v is None:continue
        y=max(y0,min(y1,py(v)))
        d.line((x0,y,x1,y),fill=stroke,width=width)
        text=f'{name}  {fmt(v)}'
        tw=d.textbbox((0,0),text,font=sm)[2]
        tx=max(x0+8,x1-tw-18)
        d.rounded_rectangle((tx-8,y-19,x1+4,y+19),radius=7,fill='#0b0f14')
        d.text((tx,y-13),text,font=sm,fill=stroke)

    # Snapshot price marker.
    sy=max(y0,min(y1,py(signal)))
    d.ellipse((x0-7,sy-7,x0+7,sy+7),fill='#f8fafc')
    d.text((x0+18,sy-13),f'SNAPSHOT  {fmt(signal)}',font=sm,fill='#e2e8f0')

    # Dedicated bottom trade card: readable on a phone without zooming.
    card_y=y1+42; card_h=175
    d.rounded_rectangle((x0,card_y,x1,card_y+card_h),radius=16,fill='#111923',outline='#263241',width=2)
    d.text((x0+24,card_y+18),'CONDITIONAL TRADE PLAN',font=h2,fill='#f8fafc')
    labels=[('ENTRY',entry,'#63a9ff'),('TP1',tp1,'#35d58a'),('TP2',tp2,'#35d58a'),('SL',sl,'#ff5968')]
    col=(x1-x0-48)/4
    for i,(k,v,c) in enumerate(labels):
        xx=x0+24+i*col
        d.text((xx,card_y+65),k,font=label,fill=c)
        d.text((xx,card_y+96),fmt(v),font=body,fill='#f1f5f9')
    d.text((x0+24,card_y+138),'Wait for the trigger • follow-through keeps the thesis alive • invalidation ends it',font=tiny,fill='#cbd5e1')

    d.text((L,H-52),'Historical snapshot • completed 1H candles • no guaranteed outcome',font=tiny,fill='#64748b')
    OUT.parent.mkdir(parents=True,exist_ok=True); img.save(OUT,'PNG')
    meta={'status':'HISTORICAL_SNAPSHOT_CREATED','provider':'Local historical OHLCV renderer','renderer':'professional_setup_renderer_v4_square_portrait','base_symbol':sym,'market_type':'BINANCE_HISTORICAL_OHLCV','timeframe':'1H','signal_created_at':s.get('signal_created_at'),'data_cutoff':s.get('data_cutoff'),'candle_count':len(cs),'candle_policy':'completed_candles_only','lookahead_protection':True,'prediction_markings':{'direction':side,'entry_trigger':entry,'tp1':tp1,'tp2':tp2,'sl':sl,'signal_price':signal},'output':str(OUT),'bytes':OUT.stat().st_size}
    META.write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(meta,indent=2))
if __name__=='__main__': main()
