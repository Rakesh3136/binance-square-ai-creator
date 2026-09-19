"""Square-native trade chart annotation layer.

Keeps the real TradingView candles as the base and adds an original analyst-style
setup overlay: entry, TP1, TP2, invalidation, directional marker and compact
labels. Prices are read only from the validated prediction contract.
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
VISUAL=ROOT/'data/live/visual.png'
META=ROOT/'data/live/visual_metadata.json'
PREF=ROOT/'data/live/editorial_preflight.json'

def load(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except:return {}

def font(sz,b=False):
    paths=(
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
        if b else
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    )
    for p in paths:
        if Path(p).exists():return ImageFont.truetype(p,sz)
    return ImageFont.load_default()

def num(v):
    try:return float(v)
    except:return None

def fmt(v):
    x=num(v)
    if x is None:return str(v)
    if abs(x)>=100:return f'{x:,.2f}'
    if abs(x)>=1:return f'{x:,.4f}'.rstrip('0').rstrip('.')
    return f'{x:.8f}'.rstrip('0').rstrip('.')

def main():
    if not VISUAL.exists():raise SystemExit('TradingView visual missing')
    selected=load(PREF).get('selected_opportunity') or {}
    setup=selected.get('trade_setup') or {}
    pred=selected.get('prediction') or {}
    side=str(setup.get('side') or pred.get('direction') or '').upper()
    entry=num(setup.get('trigger',pred.get('entry_trigger')))
    tp1=num(setup.get('tp1',pred.get('tp1')))
    tp2=num(setup.get('tp2',pred.get('tp2')))
    sl=num(setup.get('invalidation',pred.get('sl')))
    conf=selected.get('flow_confidence') or (selected.get('multitimeframe') or {}).get('confidence') or selected.get('score')
    if side not in {'LONG','SHORT'} or any(x is None for x in (entry,tp1,tp2,sl)):
        print(json.dumps({'status':'NO_PROFESSIONAL_OVERLAY','reason':'prediction_contract_missing'}));return 0

    im=Image.open(VISUAL).convert('RGB')
    d=ImageDraw.Draw(im,'RGBA'); W,H=im.size
    # Leave the TradingView chart visible; use a compact, original annotation style.
    accent=(46,190,132,245) if side=='LONG' else (235,92,92,245)
    target=(55,165,230,235); trigger=(245,190,70,245); invalid=(235,92,92,245)
    left=34; right=W-34; chart_left=max(80,int(W*0.08)); chart_right=W-210
    levels=[('TP2',tp2,target),('TP1',tp1,(46,190,132,235)),('ENTRY',entry,trigger),('SL',sl,invalid)]
    lo=min(v for _,v,_ in levels); hi=max(v for _,v,_ in levels); span=hi-lo
    if span:
        top=170; bottom=H-95
        def y_of(v):return bottom-(v-lo)/span*(bottom-top)
        # Target/invalidation zones make the setup immediately readable without
        # covering the candles.  They are informational, not a forecast of fill.
        y_entry=y_of(entry); y_tp2=y_of(tp2); y_sl=y_of(sl)
        if side=='LONG':
            d.rectangle((chart_left,min(y_tp2,y_entry),chart_right,max(y_tp2,y_entry)),fill=(46,190,132,18))
            d.rectangle((chart_left,min(y_sl,y_entry),chart_right,max(y_sl,y_entry)),fill=(235,92,92,15))
        else:
            d.rectangle((chart_left,min(y_entry,y_sl),chart_right,max(y_entry,y_sl)),fill=(235,92,92,15))
            d.rectangle((chart_left,min(y_tp2,y_entry),chart_right,max(y_tp2,y_entry)),fill=(46,190,132,18))
        for label,v,col in levels:
            y=y_of(v)
            d.line((chart_left,y,chart_right,y),fill=col,width=3)
            text=f'{label} {fmt(v)}'
            bb=d.textbbox((0,0),text,font=font(16,True)); tw=bb[2]-bb[0]; th=bb[3]-bb[1]
            lx=max(10,chart_right+8)
            d.rounded_rectangle((lx,y-th//2-6,min(W-8,lx+tw+16),y+th//2+6),radius=6,fill=(12,17,24,225),outline=col,width=2)
            d.text((lx+8,y-th//2-2),text,font=font(16,True),fill='white')

        # Direction marker near the current/right edge: visually communicates the
        # setup direction without pretending that price will necessarily move there.
        cy=y_entry
        if side=='LONG':
            pts=[(chart_right-55,cy+28),(chart_right-25,cy),(chart_right-55,cy-28)]
        else:
            pts=[(chart_right-55,cy-28),(chart_right-25,cy),(chart_right-55,cy+28)]
        d.polygon(pts,fill=accent)

    # Compact header, deliberately different from any third-party creator's branding.
    header=(28,28,34,225)
    d.rounded_rectangle((28,28,395,116),radius=15,fill=header,outline=accent,width=3)
    symbol=str(selected.get('symbol') or '').upper()
    d.text((46,42),f'${symbol}  {side} SETUP',font=font(27,True),fill='white')
    d.text((46,80),'CONDITIONAL • EVIDENCE-BACKED',font=font(14,True),fill=accent)

    # Bottom strip matches the concise trade-plan information users expect from
    # Square setup charts, without obscuring the market structure.
    values=[('ENTRY',entry),('TP1',tp1),('TP2',tp2),('SL',sl)]
    box_y=H-72; box_w=max(250,(W-56)//4-8)
    for i,(label,value) in enumerate(values):
        x=28+i*(box_w+8)
        d.rounded_rectangle((x,box_y,x+box_w,H-22),radius=9,fill=(12,17,24,220),outline=(170,178,190,130),width=1)
        d.text((x+12,box_y+8),label,font=font(12,True),fill=(190,198,210,255))
        d.text((x+12,box_y+28),fmt(value),font=font(17,True),fill='white')

    risk=abs(entry-sl); reward=abs(tp2-entry); rr=reward/risk if risk else None
    im.save(VISUAL,optimize=True)
    meta=load(META)
    meta.update({'overlays':True,'overlay_type':'square_native_trade_setup','visual_mode':'TRADINGVIEW_CHART_WITH_SETUP_LEVELS','prediction_markings':{'direction':side,'entry_trigger':entry,'tp1':tp1,'tp2':tp2,'sl':sl,'confidence':conf,'risk_reward':rr}})
    META.write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps({'status':'SQUARE_NATIVE_CHART_OVERLAY_CREATED','risk_reward':rr},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
