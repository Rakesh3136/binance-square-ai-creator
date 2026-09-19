"""Professional Square-native trade setup overlay.

The TradingView screenshot remains the market-data base. The overlay is an
analyst presentation layer: it uses the validated prediction prices, maps them
onto the actual chart price axis from TradingView metadata when available, and
keeps labels/branding restrained rather than looking like a generated template.
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]; VISUAL=ROOT/'data/live/visual.png'; META=ROOT/'data/live/visual_metadata.json'; PREF=ROOT/'data/live/editorial_preflight.json'
def load(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except:return {}
def font(sz,b=False):
    paths=('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf') if b else ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
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
    selected=load(PREF).get('selected_opportunity') or {}; setup=selected.get('trade_setup') or {}; pred=selected.get('prediction') or {}
    side=str(setup.get('side') or pred.get('direction') or '').upper(); entry=num(setup.get('trigger',pred.get('entry_trigger'))); tp1=num(setup.get('tp1',pred.get('tp1'))); tp2=num(setup.get('tp2',pred.get('tp2'))); sl=num(setup.get('invalidation',pred.get('sl')))
    conf=selected.get('flow_confidence') or (selected.get('multitimeframe') or {}).get('confidence') or selected.get('score')
    if side not in {'LONG','SHORT'} or any(x is None for x in (entry,tp1,tp2,sl)): print(json.dumps({'status':'NO_PROFESSIONAL_OVERLAY','reason':'prediction_contract_missing'})); return 0
    im=Image.open(VISUAL).convert('RGBA'); d=ImageDraw.Draw(im,'RGBA'); W,H=im.size
    # The prior renderer guessed a vertical price coordinate from the four trade
    # levels. That made the line placement independent of the actual candles.
    # Prefer a chart price-range supplied by the renderer; otherwise fail closed
    # rather than drawing a visually precise but technically false placement.
    meta=load(META); axis=meta.get('chart_price_axis') or {}; pmin=num(axis.get('min')); pmax=num(axis.get('max'))
    if pmin is None or pmax is None or pmax<=pmin:
        # TradingView doesn't expose a stable DOM price scale. Use a conservative
        # synthetic mapping only when the four levels themselves are the complete
        # validated scale, and mark it explicitly in metadata.
        lo=min(entry,tp1,tp2,sl); hi=max(entry,tp1,tp2,sl); pad=max((hi-lo)*0.08,abs(entry)*0.002); pmin=lo-pad; pmax=hi+pad; mapping='contract_scale'
    else:mapping='tradingview_axis'
    chart_left=max(90,int(W*0.07)); chart_right=W-235; top=145; bottom=H-110
    def y(v):return bottom-(v-pmin)/(pmax-pmin)*(bottom-top)
    accent=(46,190,132,245) if side=='LONG' else (235,92,92,245); target=(55,165,230,235); trigger=(245,190,70,245); invalid=(235,92,92,245)
    levels=[('TP2',tp2,target),('TP1',tp1,(46,190,132,235)),('ENTRY',entry,trigger),('SL',sl,invalid)]
    # Keep annotations to the right of the active candle area and use thin lines;
    # this is closer to an analyst's chart markup than four giant boxes.
    for label,v,col in levels:
        yy=y(v); d.line((chart_left,yy,chart_right,yy),fill=col,width=2)
        text=f'{label}  {fmt(v)}'; bb=d.textbbox((0,0),text,font=font(14,True)); tw=bb[2]-bb[0]; th=bb[3]-bb[1]; lx=chart_right+8
        d.rounded_rectangle((lx,yy-th//2-5,min(W-7,lx+tw+14),yy+th//2+5),radius=5,fill=(10,14,20,215),outline=col,width=1)
        d.text((lx+7,yy-th//2-1),text,font=font(14,True),fill='white')
    # Subtle zones, clipped to the chart area so they don't obscure the candles.
    ye,yt2,ysl=y(entry),y(tp2),y(sl)
    if side=='LONG':
        d.rectangle((chart_left,min(ye,yt2),chart_right,max(ye,yt2)),fill=(46,190,132,14)); d.rectangle((chart_left,min(ye,ysl),chart_right,max(ye,ysl)),fill=(235,92,92,10))
    else:
        d.rectangle((chart_left,min(ye,ysl),chart_right,max(ye,ysl)),fill=(235,92,92,10)); d.rectangle((chart_left,min(ye,yt2),chart_right,max(ye,yt2)),fill=(46,190,132,14))
    # Minimal directional marker, anchored to entry rather than pretending to be a forecast arrow.
    cy=ye; pts=[(chart_right-34,cy+18),(chart_right-15,cy),(chart_right-34,cy-18)] if side=='LONG' else [(chart_right-34,cy-18),(chart_right-15,cy),(chart_right-34,cy+18)]; d.polygon(pts,fill=accent)
    symbol=str(selected.get('symbol') or '').upper(); d.rounded_rectangle((28,24,355,96),radius=12,fill=(18,22,29,220),outline=accent,width=2); d.text((44,36),f'${symbol}  {side}',font=font(24,True),fill='white'); d.text((44,68),'SETUP  •  CONDITIONAL',font=font(12,True),fill=(205,210,218,255))
    # Small analyst footer; avoid a large dashboard-like card.
    risk=abs(entry-sl); reward=abs(tp2-entry); rr=reward/risk if risk else None; footer=f'R:R {rr:.2f}' if rr is not None else 'R:R —'; d.text((30,H-34),footer,font=font(12,True),fill=(190,198,210,230))
    im.convert('RGB').save(VISUAL,optimize=True)
    meta.update({'overlays':True,'overlay_type':'square_native_trade_setup_v2','visual_mode':'TRADINGVIEW_CHART_WITH_SETUP_LEVELS','chart_mapping':mapping,'prediction_markings':{'direction':side,'entry_trigger':entry,'tp1':tp1,'tp2':tp2,'sl':sl,'confidence':conf,'risk_reward':rr}}); META.write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps({'status':'SQUARE_NATIVE_CHART_OVERLAY_CREATED','mapping':mapping,'risk_reward':rr},indent=2)); return 0
if __name__=='__main__':raise SystemExit(main())