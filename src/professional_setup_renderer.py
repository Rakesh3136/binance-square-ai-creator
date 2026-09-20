"""Professional historical Signal-First setup chart renderer.

The visual presentation is intentionally richer, while all market data remains
bound to the immutable historical snapshot. No live prices are queried here.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/'data/live/historical_setup_snapshot.json'
OUT=ROOT/'data/live/visual.png'
META=ROOT/'data/live/visual_metadata.json'
W,H=1800,1000
L,R,T,B=105,90,150,145
CW,CH=W-L-R,600


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
    s=json.loads(SNAP.read_text())
    if s.get('status')!='FROZEN' or s.get('lookahead_protection') is not True: raise SystemExit('snapshot is not frozen')
    cs=s.get('candles_1h') or []
    if len(cs)<3: raise SystemExit('too few historical candles')
    cs=cs[-48:]
    p=s.get('prediction') or {}; side=str(p.get('direction') or '').upper(); sym=str(s.get('symbol') or '').upper()
    signal=float(s['signal_price']); entry=p.get('entry_trigger'); tp1=p.get('tp1'); tp2=p.get('tp2'); sl=p.get('sl')
    vals=[float(c['low']) for c in cs]+[float(c['high']) for c in cs]+[signal]
    for v in (entry,tp1,tp2,sl):
        if v is not None: vals.append(float(v))
    lo,hi=min(vals),max(vals); pad=max((hi-lo)*.10,abs(hi)*.004,1e-12); lo-=pad; hi+=pad
    img=Image.new('RGB',(W,H),'#0d1117'); d=ImageDraw.Draw(img)
    title=ft(38,True); h2=ft(24,True); body=ft(20); sm=ft(17); tiny=ft(15)
    # Header / analyst-style hierarchy
    d.text((L,30),f'{sym}USDT',font=title,fill='#f1f5f9')
    d.text((L,82),'1H  •  HISTORICAL SETUP',font=h2,fill='#94a3b8')
    badge=f'  {"LONG" if side=="LONG" else "SHORT"}  '
    bw=d.textbbox((0,0),badge,font=h2)[2]+24
    d.rounded_rectangle((W-R-bw,35,W-R,78),radius=10,fill='#153b2c' if side=='LONG' else '#4a2027')
    d.text((W-R-bw+12,43),badge,font=h2,fill='#62e6a4' if side=='LONG' else '#ff7180')
    created=s.get('signal_created_at','')
    d.text((L,116),f'Signal snapshot  {created.replace("+00:00"," UTC")}',font=tiny,fill='#64748b')
    # chart frame
    x0,x1=L,W-R; y0,y1=T,T+CH
    d.rounded_rectangle((x0-18,y0-15,x1+10,y1+15),radius=10,outline='#263241',width=2)
    def py(v): return y1-(float(v)-lo)/(hi-lo)*CH
    for i in range(7):
        y=y0+i*CH/6; val=hi-(hi-lo)*i/6
        d.line((x0,y,x1,y),fill='#1d2733',width=1); d.text((x1+12,y-9),fmt(val),font=tiny,fill='#64748b')
    n=len(cs); step=CW/n; bwc=max(7,int(step*.52)); maxvol=max(float(c.get('volume',0)) for c in cs) or 1
    vol_top=y1+32; vol_h=80
    for i,c in enumerate(cs):
        cx=x0+(i+.5)*step; yo,yc,yh,yl=map(py,[c['open'],c['close'],c['high'],c['low']]); up=float(c['close'])>=float(c['open'])
        wick='#39d98a' if up else '#ff5c6c'; d.line((cx,yh,cx,yl),fill=wick,width=3); top,bot=sorted((yo,yc)); d.rectangle((cx-bwc/2,top,cx+bwc/2,max(bot,top+2)),fill=wick)
        vh=float(c.get('volume',0))/maxvol*vol_h; d.rectangle((cx-bwc/2,vol_top+vol_h-vh,cx+bwc/2,vol_top+vol_h),fill='#334155')
    # soft setup zones
    def zone(a,b,fill):
        if a is None or b is None:return
        ya,yb=py(a),py(b); d.rectangle((x0,min(ya,yb),x1,max(ya,yb)),fill=fill)
    if entry is not None and tp1 is not None: zone(entry,tp1,'#112c24')
    if sl is not None and entry is not None: zone(sl,entry,'#30191e')
    # redraw candles above zones for crispness
    for i,c in enumerate(cs):
        cx=x0+(i+.5)*step; yo,yc,yh,yl=map(py,[c['open'],c['close'],c['high'],c['low']]); up=float(c['close'])>=float(c['open']); wick='#39d98a' if up else '#ff5c6c'; d.line((cx,yh,cx,yl),fill=wick,width=3); top,bot=sorted((yo,yc)); d.rectangle((cx-bwc/2,top,cx+bwc/2,max(bot,top+2)),fill=wick)
    # setup lines + right-side labels
    levels=[('ENTRY',entry,'#5aa9ff',3),('TP1',tp1,'#39d98a',2),('TP2',tp2,'#39d98a',2),('SL',sl,'#ff5c6c',3)]
    for name,v,stroke,w in levels:
        if v is None:continue
        y=max(y0,min(y1,py(v))); d.line((x0,y,x1,y),fill=stroke,width=w)
        text=f'{name}  {fmt(v)}'; tw=d.textbbox((0,0),text,font=sm)[2]; d.rounded_rectangle((x1-tw-24,y-14,x1+2,y+14),radius=5,fill='#0d1117'); d.text((x1-tw-12,y-10),text,font=sm,fill=stroke)
    # signal marker
    sy=py(signal); d.ellipse((x0-7,sy-7,x0+7,sy+7),fill='#f8fafc'); d.text((x0+18,sy-12),f'Snapshot price  {fmt(signal)}',font=sm,fill='#cbd5e1')
    # compact trade card
    card_x,card_y,card_w,card_h=L,825,760,105
    d.rounded_rectangle((card_x,card_y,card_x+card_w,card_y+card_h),radius=12,fill='#111827',outline='#263241',width=2)
    labels=[('ENTRY',entry),('TP1',tp1),('TP2',tp2),('SL',sl)]
    for i,(k,v) in enumerate(labels):
        xx=card_x+25+i*185; d.text((xx,845),k,font=tiny,fill='#64748b'); d.text((xx,870),fmt(v),font=body,fill='#e5e7eb')
    d.text((card_x+790,846),'CONDITIONAL',font=tiny,fill='#64748b'); d.text((card_x+790,870),'Not a guarantee',font=sm,fill='#cbd5e1')
    d.text((L,H-32),'Historical snapshot • completed candles only • outcome evaluated separately',font=tiny,fill='#64748b')
    OUT.parent.mkdir(parents=True,exist_ok=True); img.save(OUT,'PNG')
    meta={'status':'HISTORICAL_SNAPSHOT_CREATED','provider':'Local historical OHLCV renderer','renderer':'professional_setup_renderer_v2','base_symbol':sym,'tradingview_symbol':None,'market_type':'BINANCE_HISTORICAL_OHLCV','timeframe':'1H','signal_created_at':created,'data_cutoff':s.get('data_cutoff'),'candle_count':len(cs),'candle_policy':'completed_candles_only','lookahead_protection':True,'prediction_markings':{'direction':side,'entry_trigger':entry,'tp1':tp1,'tp2':tp2,'sl':sl,'signal_price':signal},'output':str(OUT),'bytes':OUT.stat().st_size}
    META.write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps(meta,indent=2))
if __name__=='__main__': main()
