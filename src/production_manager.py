"""Bounded production manager for Binance Square.

The manager is final publication authority. Autonomous market posts always
require a verified TradingView visual and are never allowed to degrade to text.
"""
from __future__ import annotations
import json, os, subprocess, sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT_DIR=ROOT/'data/reports'; STATUS_PATH=ROOT/'data/live/creator_status.json'; PREFLIGHT_PATH=ROOT/'data/live/editorial_preflight.json'; INTEL_PATH=ROOT/'data/live/creator_intelligence_2.json'; GATE_PATH=ROOT/'data/live/engagement_gate.json'; VISUAL_META=ROOT/'data/live/visual_metadata.json'; VISUAL=ROOT/'data/live/visual.png'; AUDIT_PATH=Path('/tmp/publish_gate.json')
QUALITY_THRESHOLD=68.0; OPPORTUNITY_THRESHOLD=60.0; RESCUE_QUALITY_THRESHOLD=75.0; MAX_AGE_SECONDS=20*60

def load(path:Path,default=None):
    if not path.exists(): return default if default is not None else {}
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default if default is not None else {}

def fresh_report():
    reports=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if not reports:return None
    report=reports[0]
    return report if datetime.now().timestamp()-report.stat().st_mtime<=MAX_AGE_SECONDS else None

def output(publish:bool,mode='image'):
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:
        out.write(f"publish={'true' if publish else 'false'}\nmode={mode}\n")

def set_fallback_status():
    STATUS_PATH.parent.mkdir(parents=True,exist_ok=True)
    STATUS_PATH.write_text(json.dumps({'status':'LOCAL_FALLBACK_SUCCESS','generation_mode':'LOCAL_FALLBACK','reason':'Production manager deterministic rescue produced a fresh publishable draft'},indent=2),encoding='utf-8')

def opportunity_score(data):
    pre=load(PREFLIGHT_PATH,{ }); vals=[]
    for obj,keys in ((data.get('research') or {},('opportunity_score','adjusted_score','engagement_score')),(data.get('critique') or {},('revised_opportunity_score','opportunity_score','adjusted_score','engagement_score')),(data.get('selected_editorial_lane') or {},('adjusted_score','raw_score','engagement_score')),(pre.get('selected_opportunity') or {},('adjusted_score','raw_score','content_signal_score','engagement_score'))):
        if isinstance(obj,dict):
            for k in keys:
                try:v=float(obj.get(k) or 0)
                except:v=0
                if v>0: vals.append(v)
    return max(vals,default=0.0)

def visual_is_verified(expected_symbol=''):
    """Verify both chart provenance and chart/asset synchronization."""
    meta=load(VISUAL_META,{})
    if not (meta.get('provider')=='TradingView' and meta.get('status')=='TRADINGVIEW_CREATED' and VISUAL.exists() and VISUAL.stat().st_size>=1000):
        return False
    if expected_symbol:
        expected=f"BINANCE:{expected_symbol.upper().replace('USDT','')}USDT"
        actual=str(meta.get('tradingview_symbol') or meta.get('symbol') or '').upper()
        if actual != expected:
            print(f"Production manager: refusing publication because chart asset is {actual!r}, expected {expected!r}.")
            return False
    return True

def evaluate(report:Path):
    data=load(report,{ }); draft=data.get('draft') or {}; visual=dict(data.get('visual_plan') or {}); post=str(draft.get('post') or draft.get('text') or '').strip(); rescue=data.get('publish_rescue') is True
    # The authoritative asset is the frozen/preflight symbol. Never allow a
    # downstream rescue to switch the asset after TradingView rendering.
    pre=load(PREFLIGHT_PATH,{})
    selected=pre.get('selected_opportunity') or data.get('selected_editorial_lane') or {}
    expected_symbol=str(selected.get('symbol') or selected.get('topic') or draft.get('symbol') or '').upper().replace('USDT','') if isinstance(selected,dict) else str(draft.get('symbol') or '').upper().replace('USDT','')
    if not expected_symbol:
        expected_symbol=str(draft.get('symbol') or '').upper().replace('USDT','')

    # Market publication policy is stronger than the AI's optional visual plan.
    # The workflow already renders TradingView for every autonomous market run,
    # so force the verified chart into the publication decision and image mode.
    visual.update({'type':'candlestick_chart','use_visual':True,'provider':'TradingView'})
    try:
        from engagement_quality_gate import evaluate as interaction_evaluate
        interaction=interaction_evaluate(post,visual)
    except Exception as exc:
        interaction={'score':0,'publish':False,'reasons':[f'quality_gate_error:{type(exc).__name__}']}
    try:quality=float(draft.get('quality_score') or interaction.get('score') or 0)
    except:quality=float(interaction.get('score') or 0)
    opportunity=opportunity_score(data); intelligence=load(INTEL_PATH,{ }); intelligence_ok=intelligence.get('publish_recommendation') is True
    chart_ok=visual_is_verified(expected_symbol)
    if rescue:
        eligible=bool(post) and quality>=RESCUE_QUALITY_THRESHOLD and opportunity>=OPPORTUNITY_THRESHOLD and interaction.get('publish') is True and chart_ok
    else:
        eligible=bool(post) and quality>=QUALITY_THRESHOLD and opportunity>=OPPORTUNITY_THRESHOLD and interaction.get('publish') is True and intelligence_ok and data.get('status')=='DRAFT_ONLY_NOT_PUBLISHED' and chart_ok
    mode='image'
    audit={'draft':str(report),'publish':eligible,'attempt':'rescue' if rescue else 'normal','quality_score':quality,'quality_threshold':RESCUE_QUALITY_THRESHOLD if rescue else QUALITY_THRESHOLD,'opportunity_score':opportunity,'opportunity_threshold':OPPORTUNITY_THRESHOLD,'creator_status':load(STATUS_PATH,{}).get('status'),'creator_intelligence_2':intelligence,'interaction_gate':interaction,'mode':mode,'tradingview_required':True,'tradingview_verified':chart_ok,'chart_expected_symbol':expected_symbol,'rescue':rescue,'reason':'publish_eligible' if eligible else 'gate_rejected'}
    AUDIT_PATH.write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8'); GATE_PATH.parent.mkdir(parents=True,exist_ok=True); GATE_PATH.write_text(json.dumps(interaction,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(audit,indent=2,ensure_ascii=False)); return eligible,mode

def main():
    report=fresh_report()
    if not report: output(False); print(json.dumps({'publish':False,'reason':'no fresh draft within 20 minutes'})); return 0
    publish,mode=evaluate(report)
    if publish: output(True,mode); print('Production manager: draft passed and verified TradingView evidence is mandatory.'); return 0
    print('Production manager: normal gate rejected; running one bounded rescue.')
    rescue=subprocess.run([sys.executable,str(ROOT/'src/publish_rescue.py')],cwd=ROOT,check=False)
    if rescue.returncode!=0: output(False); print('Production manager: rescue failed; no publication.'); return 0
    set_fallback_status(); report=fresh_report()
    if not report: output(False); print('Production manager: rescue produced no fresh report; no publication.'); return 0
    publish,mode=evaluate(report)
    if publish: output(True,mode); print('Production manager: rescue passed with verified TradingView evidence.'); return 0
    output(False); print('Production manager: final evidence checks failed; no publication.'); return 0
if __name__=='__main__': raise SystemExit(main())
