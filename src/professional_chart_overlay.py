"""Professional analyst-style chart annotation layer.
Uses only validated levels from editorial_preflight.json and never invents prices."""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
VISUAL=ROOT/'data/live/visual.png'; META=ROOT/'data/live/visual_metadata.json'; PREF=ROOT/'data/live/editorial_preflight.json'
def load(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {}
def f(sz,b=False):
    for p in (('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf') if b else ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')):
        if Path(p).exists(): return ImageFont.truetype(p,sz)
    return ImageFont.load_default()
def n(v):
    try:return float(v)
    except:return None
def fmt(v):
    x=n(v)
    if x is None:return str(v)
    if abs(x)>=100:return f'{x:,.2f}'
    if abs(x)>=1:return f'{x:,.4f}'.rstrip('0').rstrip('.')
    return f'{x:.6f}'.rstrip('0').rstrip('.')
def main():
    if not VISUAL.exists(): raise SystemExit('TradingView visual missing')
    s=(load(PREF).get('selected_opportunity') or {}); setup=s.get('trade_setup') or {}; pred=s.get('prediction') or {}
    side=str(setup.get('side') or pred.get('direction') or '').upper(); entry=n(setup.get('trigger',pred.get('entry_trigger'))); tp1=n(setup.get('tp1',pred.get('tp1'))); tp2=n(setup.get('tp2',pred.get('tp2'))); sl=n(setup.get('invalidation',pred.get('sl'))); conf=s.get('flow_confidence') or (s.get('multitimeframe') or {}).get('confidence') or s.get('score')
    if side not in {'LONG','SHORT'} or any(x is None for x in (entry,tp1,tp2,sl)): print(json.dumps({'status':'NO_PROFESSIONAL_OVERLAY','reason':'prediction_contract_missing'})); return 0
    im=Image.open(VISUAL).convert('RGB'); d=ImageDraw.Draw(im,'RGBA'); W,H=im.size; margin=24; rail=min(410,max(340,W//4)); accent=(46,190,132,245) if side=='LONG' else (235,92,92,245)
    d.rounded_rectangle((margin,margin,margin+320,108),radius=16,fill=(10,15,22,220),outline=accent,width=3); d.text((margin+18,margin+12),f'{s.get("symbol","")} {side}',font=f(29,True),fill='white'); d.text((margin+18,margin+53),'EARLY SETUP • CONDITIONAL',font=f(15,True),fill=accent)
    levels=[('TRIGGER',entry,(245,190,70,235)),('TP1',tp1,(46,190,132,235)),('TP2',tp2,(60,160,230,235)),('INVALIDATION',sl,(235,92,92,235))]; lo=min(x[1] for x in levels); hi=max(x[1] for x in levels); span=hi-lo
    if span:
        top=135; bottom=H-40; xs=rail+margin; xe=W-250
        for label,v,col in levels:
            y=bottom-(v-lo)/span*(bottom-top); text=f'{label}  {fmt(v)}'; bb=d.textbbox((0,0),text,font=f(15,True)); tw=bb[2]; lx=max(margin,xs-tw-16); d.line((xs,y,xe,y),fill=col,width=3); d.rounded_rectangle((lx,y-14,lx+tw+12,y+14),radius=7,fill=(10,15,22,215),outline=col,width=2); d.text((lx+6,y-10),text,font=f(15,True),fill='white')
    cx=margin; cy=H-255; cw=rail; ch=231; d.rounded_rectangle((cx,cy,cx+cw,cy+ch),radius=18,fill=(10,15,22,225),outline=(170,178,190,150),width=2); d.text((cx+18,cy+15),'TRADE PLAN',font=f(21,True),fill='white'); y=cy+52
    for label,v in [('Trigger',entry),('TP1',tp1),('TP2',tp2),('Invalidation',sl)]: d.text((cx+18,y),label,font=f(15,True),fill=(188,196,208,255)); d.text((cx+145,y),fmt(v),font=f(18,True),fill='white'); y+=37
    risk=abs(entry-sl); reward=abs(tp2-entry); rr=reward/risk if risk else None; foot=f'R:R {rr:.2f} • Confidence {fmt(conf)}%' if rr is not None and n(conf) is not None else 'Outcome tracked'; d.text((cx+18,cy+ch-27),foot,font=f(14,True),fill=accent)
    im.save(VISUAL,optimize=True); meta=load(META); meta.update({'overlays':True,'overlay_type':'professional_trade_plan','visual_mode':'TRADINGVIEW_CHART_WITH_PRO_TRADE_PLAN','prediction_markings':{'direction':side,'entry_trigger':entry,'tp1':tp1,'tp2':tp2,'sl':sl,'confidence':conf,'risk_reward':rr}}); META.write_text(json.dumps(meta,indent=2),encoding='utf-8'); print(json.dumps({'status':'PROFESSIONAL_CHART_OVERLAY_CREATED','risk_reward':rr},indent=2)); return 0
if __name__=='__main__':raise SystemExit(main())
