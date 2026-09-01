"""Bounded production manager for Binance Square Creator 4.1.

Final publication authority: only a fresh, coherent draft with a verified
TradingView chart and a valid primary cashtag can be published.
"""
from __future__ import annotations
import json, os, subprocess, sys, re
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT_DIR=ROOT/'data/reports'; STATUS_PATH=ROOT/'data/live/creator_status.json'; PREFLIGHT_PATH=ROOT/'data/live/editorial_preflight.json'; INTEL_PATH=ROOT/'data/live/creator_intelligence_2.json'; GATE_PATH=ROOT/'data/live/engagement_gate.json'; VISUAL_META=ROOT/'data/live/visual_metadata.json'; VISUAL=ROOT/'data/live/visual.png'; AUDIT_PATH=Path('/tmp/publish_gate.json')
QUALITY_THRESHOLD=68.0; OPPORTUNITY_THRESHOLD=60.0; RESCUE_QUALITY_THRESHOLD=75.0; MAX_AGE_SECONDS=20*60

def load(path:Path,default=None):
    if not path.exists(): return default if default is not None else {}
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return default if default is not None else {}

def fresh_report():
    reports=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if not reports:return None
    report=reports[0]
    return report if datetime.now().timestamp()-report.stat().st_mtime<=MAX_AGE_SECONDS else None

def output(publish:bool,mode='image'):
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:out.write(f"publish={'true' if publish else 'false'}\nmode={mode}\n")

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
                if v>0:vals.append(v)
    return max(vals,default=0.0)

def authoritative_symbol(data):
    pre=load(PREFLIGHT_PATH,{ }); selected=pre.get('selected_opportunity') or {}
    values=[selected.get('symbol'),selected.get('topic'),(pre.get('content_director_4') or {}).get('primary_story',{}).get('symbol'),(data.get('draft') or {}).get('symbol')]
    for value in values:
        s=re.sub(r'USDT$','',str(value or '').upper().replace('$','').strip())
        if re.fullmatch(r'[A-Z0-9]{2,15}',s):return s
    return ''

def visual_is_verified(expected_symbol=''):
    meta=load(VISUAL_META,{})
    ok=(meta.get('provider')=='TradingView' and meta.get('status')=='TRADINGVIEW_CREATED' and meta.get('visual_mode')=='TRADINGVIEW_CHART_ONLY' and meta.get('overlays') is False and VISUAL.exists() and VISUAL.stat().st_size>=1000)
    if not ok:return False
    if expected_symbol:
        expected=f"BINANCE:{expected_symbol.upper().replace('USDT','')}USDT"
        actual=str(meta.get('tradingview_symbol') or meta.get('symbol') or '').upper()
        if actual!=expected:
            print(f"Production manager: chart is {actual!r}, expected {expected!r}.");return False
    return True

def content_is_coherent(post, expected_symbol):
    if not post or not expected_symbol:return False
    if '$.' in post or re.search(r'\$\s*(?:is|has|setup|moved)',post,re.I):return False
    if f'${expected_symbol}' not in post.upper():return False
    if post.count('?')!=1:return False
    return True

def evaluate(report:Path):
    data=load(report,{ }); draft=data.get('draft') or {}; visual=dict(data.get('visual_plan') or {}); post=str(draft.get('post') or draft.get('text') or '').strip(); rescue=data.get('publish_rescue') is True
    expected_symbol=authoritative_symbol(data)
    pre=load(PREFLIGHT_PATH,{ }); selected=pre.get('selected_opportunity') or data.get('selected_editorial_lane') or {}
    visual.update({'type':'candlestick_chart','use_visual':True,'provider':'TradingView'})
    try:
        from engagement_quality_gate import evaluate as interaction_evaluate
        interaction=interaction_evaluate(post,visual)
    except Exception as exc:
        interaction={'score':0,'publish':False,'reasons':[f'quality_gate_error:{type(exc).__name__}']}
    try:quality=float(draft.get('quality_score') or interaction.get('score') or 0)
    except:quality=float(interaction.get('score') or 0)
    opportunity=opportunity_score(data); intelligence=load(INTEL_PATH,{ }); intelligence_ok=intelligence.get('publish_recommendation') is True
    chart_ok=visual_is_verified(expected_symbol); coherent=content_is_coherent(post,expected_symbol)
    if rescue:
        eligible=bool(post) and coherent and quality>=RESCUE_QUALITY_THRESHOLD and opportunity>=OPPORTUNITY_THRESHOLD and interaction.get('publish') is True and chart_ok
    else:
        eligible=bool(post) and coherent and quality>=QUALITY_THRESHOLD and opportunity>=OPPORTUNITY_THRESHOLD and interaction.get('publish') is True and intelligence_ok and data.get('status')=='DRAFT_ONLY_NOT_PUBLISHED' and chart_ok
    mode='image'
    audit={'draft':str(report),'publish':eligible,'attempt':'rescue' if rescue else 'normal','quality_score':quality,'quality_threshold':RESCUE_QUALITY_THRESHOLD if rescue else QUALITY_THRESHOLD,'opportunity_score':opportunity,'opportunity_threshold':OPPORTUNITY_THRESHOLD,'creator_status':load(STATUS_PATH,{}).get('status'),'creator_intelligence_2':intelligence,'interaction_gate':interaction,'mode':mode,'tradingview_required':True,'tradingview_verified':chart_ok,'chart_expected_symbol':expected_symbol,'content_coherent':coherent,'rescue':rescue,'reason':'publish_eligible' if eligible else 'gate_rejected'}
    AUDIT_PATH.write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8'); GATE_PATH.parent.mkdir(parents=True,exist_ok=True); GATE_PATH.write_text(json.dumps(interaction,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(audit,indent=2,ensure_ascii=False));return eligible,mode

def main():
    report=fresh_report()
    if not report:output(False);print(json.dumps({'publish':False,'reason':'no fresh draft within 20 minutes'}));return 0
    publish,mode=evaluate(report)
    if publish:output(True,mode);print('Production manager: coherent draft and chart-only TradingView evidence verified.');return 0
    print('Production manager: normal gate rejected; running one bounded rescue.')
    rescue=subprocess.run([sys.executable,str(ROOT/'src/publish_rescue.py')],cwd=ROOT,check=False)
    if rescue.returncode!=0:output(False);print('Production manager: rescue failed; no publication.');return 0
    set_fallback_status();report=fresh_report()
    if not report:output(False);print('Production manager: rescue produced no fresh report; no publication.');return 0
    publish,mode=evaluate(report)
    if publish:output(True,mode);print('Production manager: rescue passed with coherent content and verified chart-only TradingView evidence.');return 0
    output(False);print('Production manager: final evidence checks failed; no publication.');return 0
if __name__=='__main__':raise SystemExit(main())
