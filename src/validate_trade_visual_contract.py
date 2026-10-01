"""Final contract for setup charts: trade levels + evidence-bound pattern annotation."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; META=ROOT/'data/live/visual_metadata.json'; PREF=ROOT/'data/live/editorial_preflight.json'; PATTERN=ROOT/'data/live/nic_pattern_visual_engine_18.json'
def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}
def main():
    meta=load(META); pre=load(PREF); selected=pre.get('selected_opportunity') or {}; category=str(selected.get('category') or '').lower()
    technical=category in {'technical_setup','capital_flow_long','capital_flow_short','high_volatility','top_gainers','top_losers','flow','follow_up','creator_signal_outcome'}
    if not technical: print({'status':'SKIP','reason':'non-setup lane'}); return 0
    markings=meta.get('prediction_markings') or {}; required=('entry_trigger','tp1','tp2','sl'); missing=[k for k in required if markings.get(k) is None]
    pattern=meta.get('pattern_annotation') or {}; pattern_type=str(pattern.get('type') or '')
    if not bool(meta.get('overlays')) or missing or not pattern_type:
        raise SystemExit(f'FINAL VISUAL CONTRACT FAILED: overlays={meta.get("overlays")} missing={missing} pattern={pattern_type!r}')
    print({'status':'PASS','overlay_type':meta.get('overlay_type'),'pattern':pattern_type,'prediction_markings':markings}); return 0
if __name__=='__main__': raise SystemExit(main())
