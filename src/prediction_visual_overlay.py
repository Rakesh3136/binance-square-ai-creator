"""Add a deterministic prediction panel/markings to the validated TradingView snapshot."""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]; VISUAL=ROOT/'data/live/visual.png'; META=ROOT/'data/live/visual_metadata.json'; PREF=ROOT/'data/live/editorial_preflight.json'

def load(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {}

def font(size):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(p).exists():return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def main():
    if not VISUAL.exists():raise SystemExit('TradingView visual missing')
    pre=load(PREF); selected=pre.get('selected_opportunity') or {}; setup=selected.get('trade_setup') or {}; pred=selected.get('prediction') or {}
    side=str(setup.get('side') or pred.get('direction') or '').upper(); entry=setup.get('trigger',pred.get('entry_trigger')); tp1=setup.get('tp1',pred.get('tp1')); tp2=setup.get('tp2',pred.get('tp2')); sl=setup.get('invalidation',pred.get('sl')); conf=selected.get('flow_confidence') or (selected.get('multitimeframe') or {}).get('confidence') or selected.get('score')
    if side not in {'LONG','SHORT'} or any(v is None for v in (entry,tp1,tp2,sl)):
        print(json.dumps({'status':'NO_PREDICTION_OVERLAY','reason':'prediction_contract_missing'})); return 0
    img=Image.open(VISUAL).convert('RGB'); draw=ImageDraw.Draw(img,'RGBA'); W,H=img.size
    panel_w=min(520,W//3); x0=W-panel_w+20; y0=25; x1=W-20; y1=H-25
    draw.rounded_rectangle((x0,y0,x1,y1),radius=22,fill=(12,16,24,225),outline=(235,235,235,150),width=2)
    title=font(34); label=font(23); value=font(28); small=font(19)
    draw.text((x0+25,y0+22),f'{selected.get("symbol","")} {side} PREDICTION',font=title,fill=(255,255,255,255))
    lines=[('ENTRY / TRIGGER',entry),('TP1',tp1),('TP2',tp2),('SL / INVALIDATION',sl),('CONFIDENCE',f'{conf}%')]
    y=y0+88
    for name,val in lines:
        draw.text((x0+28,y),name,font=label,fill=(210,215,225,255)); draw.text((x0+28,y+29),str(val),font=value,fill=(255,255,255,255)); y+=102
    draw.text((x0+28,y1-50),'Conditional setup • outcome tracked',font=small,fill=(190,198,210,255))
    img.save(VISUAL,optimize=True)
    meta=load(META); meta.update({'overlays':True,'overlay_type':'prediction_levels_panel','prediction_markings':{'direction':side,'entry_trigger':entry,'tp1':tp1,'tp2':tp2,'sl':sl,'confidence':conf},'visual_mode':'TRADINGVIEW_CHART_WITH_PREDICTION_MARKINGS'}); META.write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'PREDICTION_OVERLAY_CREATED','direction':side,'entry_trigger':entry,'tp1':tp1,'tp2':tp2,'sl':sl,'confidence':conf},indent=2)); return 0
if __name__=='__main__':raise SystemExit(main())
