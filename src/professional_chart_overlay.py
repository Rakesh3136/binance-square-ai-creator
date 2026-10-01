"""Professional Square-native trade setup + pattern overlay."""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]; VISUAL=ROOT/'data/live/visual.png'; META=ROOT/'data/live/visual_metadata.json'; PREF=ROOT/'data/live/editorial_preflight.json'; FROZEN=ROOT/'data/live/authoritative_opportunity.json'; PATTERN=ROOT/'data/live/nic_pattern_visual_engine_18.json'
def load(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {}
def font(sz,b=False):
    paths=('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf') if b else ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    for p in paths:
        if Path(p).exists():return ImageFont.truetype(p,sz)
    return ImageFont.load_default()
def num(v):
    try:return float(v)
    except Exception:return None
def fmt(v):
    x=num(v)
    if x is None:return str(v)
    if abs(x)>=100:return f'{x:,.2f}'
    if abs(x)>=1:return f'{x:,.4f}'.rstrip('0').rstrip('.')
    return f'{x:.8f}'.rstrip('0').rstrip('.')
def dashed_line(d,x1,y,x2,fill,width=2,dash=10,gap=7):
    x=int(x1); x2=int(x2)
    while x<x2:
        d.line((x,y,min(x+dash,x2),y),fill=fill,width=width); x+=dash+gap
def main():
    if not VISUAL.exists():raise SystemExit('TradingView visual missing')
    selected=load(PREF).get('selected_opportunity') or {}; frozen=load(FROZEN); setup=selected.get('trade_setup') or frozen.get('trade_setup') or {}; pred=selected.get('prediction') or frozen.get('prediction') or {}; evidence=selected.get('evidence') or frozen.get('evidence') or {}
    reports=sorted((ROOT/'data/reports').glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime_ns,reverse=True)
    if not (setup and pred) and reports:
        draft=(load(reports[0]).get('draft') or {}); levels=draft.get('technical_levels') if isinstance(draft.get('technical_levels'),dict) else {}
        if levels:
            side=str(levels.get('direction') or '').upper().replace('_BIAS',''); setup={'side':side,'trigger':levels.get('current_price'),'tp1':levels.get('tp1'),'tp2':levels.get('target'),'invalidation':levels.get('invalidation')}; pred={'direction':side,'entry_trigger':levels.get('current_price'),'tp1':levels.get('tp1'),'tp2':levels.get('target'),'sl':levels.get('invalidation')}; evidence={'last_price':levels.get('current_price'),'recent_low':levels.get('support'),'recent_high':levels.get('resistance')}
    side=str(setup.get('side') or pred.get('direction') or '').upper(); entry=num(setup.get('trigger',pred.get('entry_trigger'))); tp1=num(setup.get('tp1',pred.get('tp1'))); tp2=num(setup.get('tp2',pred.get('tp2'))); sl=num(setup.get('invalidation',pred.get('sl'))); conf=selected.get('flow_confidence') or (selected.get('multitimeframe') or {}).get('confidence') or pred.get('confidence') or selected.get('score')
    if side not in {'LONG','SHORT'} or any(x is None for x in (entry,tp1,tp2,sl)):
        print(json.dumps({'status':'NO_PROFESSIONAL_OVERLAY','reason':'prediction_contract_missing'})); return 0
    im=Image.open(VISUAL).convert('RGBA'); d=ImageDraw.Draw(im,'RGBA'); W,H=im.size; meta=load(META); pattern=load(PATTERN).get('pattern') or {}; pattern_levels=load(PATTERN).get('levels') or {}
    last=num(evidence.get('last_price')); recent_low=num(evidence.get('recent_low')); recent_high=num(evidence.get('recent_high')); axis=meta.get('chart_price_axis') or {}; pmin=num(axis.get('min')); pmax=num(axis.get('max')); mapping='tradingview_axis'
    if pmin is None or pmax is None or pmax<=pmin:
        if recent_low is not None and recent_high is not None and recent_high>recent_low:pmin=recent_low;pmax=recent_high;mapping='verified_ohlcv_range'; pad=max(abs(pmax-pmin)*.06,abs(last or entry)*.002);pmin-=pad;pmax+=pad
        else:lo=min(entry,tp1,tp2,sl);hi=max(entry,tp1,tp2,sl);pad=max((hi-lo)*.08,abs(entry)*.002);pmin=lo-pad;pmax=hi+pad;mapping='contract_fallback'
    chart_left=max(90,int(W*.07)); chart_right=W-220; top=92; bottom=int(H*.80)
    def y(v):return bottom-(v-pmin)/(pmax-pmin)*(bottom-top)
    # Pattern layer: only draw evidence returned by NIC 18. No random shapes.
    ptype=str(pattern.get('type') or 'STRUCTURE_NEUTRAL'); plabel=str(pattern.get('label') or 'STRUCTURE'); ph=num(pattern_levels.get('prior_high')); pl=num(pattern_levels.get('prior_low'))
    pattern_col=(170,130,245,210)
    if ph is not None and top<=y(ph)<=bottom:dashed_line(d,chart_left,y(ph),chart_right,pattern_col,width=2,dash=16,gap=9)
    if pl is not None and top<=y(pl)<=bottom:dashed_line(d,chart_left,y(pl),chart_right,pattern_col,width=2,dash=16,gap=9)
    # Highlight a confirmed close-through-range event with a vertical breakout marker.
    if ptype in {'BREAKOUT_UP','BREAKDOWN'}:
        level=num(pattern.get('level'))
        if level is not None and top<=y(level)<=bottom:
            xx=int(chart_left+(chart_right-chart_left)*.86); yy=y(level)
            d.line((xx,yy-48,xx,yy+48),fill=(245,190,70,235),width=3)
            d.text((xx-52,max(top,yy-72)),plabel,font=font(13,True),fill=(245,190,70,255))
    # Structure label for every detected pattern.
    d.rounded_rectangle((W-210,20,W-24,60),radius=7,fill=(17,21,28,225),outline=pattern_col,width=1)
    d.text((W-198,29),plabel,font=font(14,True),fill='white')
    tp_col=(66,176,226,235); tp1_col=(46,190,132,230); trigger_col=(245,190,70,238); sl_col=(235,92,92,238)
    for label,v,col in [('TP2',tp2,tp_col),('TP1',tp1,tp1_col),('ENTRY',entry,trigger_col),('SL',sl,sl_col)]:
        yy=y(v)
        if yy<top-2 or yy>bottom+2:continue
        dashed_line(d,chart_left,yy,chart_right,col,width=2); text=f'{label}  {fmt(v)}'; bb=d.textbbox((0,0),text,font=font(13,True)); tw=bb[2]-bb[0]; th=bb[3]-bb[1]; lx=min(W-tw-14,chart_right+7); ly=max(top+2,min(bottom-th-8,yy-th//2-4)); d.rounded_rectangle((lx,ly,lx+tw+12,ly+th+8),radius=4,fill=(9,13,18,220),outline=col,width=1); d.text((lx+6,ly+3),text,font=font(13,True),fill='white')
    ye=y(entry)
    if top<=ye<=bottom:
        pts=[(chart_right-18,ye),(chart_right-30,ye-9),(chart_right-30,ye+9)] if side=='LONG' else [(chart_right-30,ye),(chart_right-18,ye-9),(chart_right-18,ye+9)]
        d.polygon(pts,fill=(46,190,132,225) if side=='LONG' else (235,92,92,225))
    symbol=str(selected.get('symbol') or frozen.get('symbol') or '').upper(); d.rounded_rectangle((24,20,310,78),radius=10,fill=(17,21,28,220),outline=(155,163,176,110),width=1); d.text((38,29),'$'+symbol+f'  {side}',font=font(22,True),fill='white'); conf_text='—' if conf is None else str(int(float(conf))); d.text((38,55),f'1H  •  {plabel}  •  {conf_text}% confidence',font=font(10),fill=(195,201,210,235))
    risk=abs(entry-sl); reward=abs(tp2-entry); rr=reward/risk if risk else None
    if rr is not None:d.text((30,H-28),f'R:R {rr:.2f}',font=font(11,True),fill=(195,201,210,210))
    im.convert('RGB').save(VISUAL,optimize=True); meta.update({'overlays':True,'overlay_type':'square_native_trade_setup_pattern_v4','visual_mode':'TRADINGVIEW_CHART_WITH_SETUP_AND_PATTERN','chart_mapping':mapping,'prediction_markings':{'direction':side,'entry_trigger':entry,'tp1':tp1,'tp2':tp2,'sl':sl,'confidence':conf,'risk_reward':rr},'pattern_annotation':{'type':ptype,'label':plabel,'level':pattern.get('level'),'prior_high':ph,'prior_low':pl}}); META.write_text(json.dumps(meta,indent=2),encoding='utf-8'); print(json.dumps({'status':'SQUARE_NATIVE_CHART_PATTERN_OVERLAY_CREATED','pattern':ptype,'mapping':mapping,'risk_reward':rr},indent=2)); return 0
if __name__=='__main__':raise SystemExit(main())
