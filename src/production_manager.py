"""Final publication authority for Creator 4.2.

Accepts either a single TradingView chart or a clean TradingView pair image,
and lets the editorial brain choose image-post vs article mode.
"""
from __future__ import annotations
import json, os, re, subprocess, sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT_DIR=ROOT/'data/reports'; STATUS_PATH=ROOT/'data/live/creator_status.json'; PREFLIGHT_PATH=ROOT/'data/live/editorial_preflight.json'; INTEL_PATH=ROOT/'data/live/creator_intelligence_2.json'; GATE_PATH=ROOT/'data/live/engagement_gate.json'; VISUAL_META=ROOT/'data/live/visual_metadata.json'; VISUAL=ROOT/'data/live/visual.png'; AUDIT_PATH=Path('/tmp/publish_gate.json')
QUALITY_THRESHOLD=68.0; OPPORTUNITY_THRESHOLD=60.0; RESCUE_QUALITY_THRESHOLD=75.0; MAX_AGE_SECONDS=20*60

def load(path,default=None):
    if not Path(path).exists(): return {} if default is None else default
    try:
        x=json.loads(Path(path).read_text(encoding='utf-8')); return x if isinstance(x,type(default or {})) else ({} if default is None else default)
    except Exception:return {} if default is None else default

def fresh_report():
    reports=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if not reports:return None
    p=reports[0]; return p if datetime.now().timestamp()-p.stat().st_mtime<=MAX_AGE_SECONDS else None

def output(publish,mode='image'):
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:f.write(f"publish={'true' if publish else 'false'}\nmode={mode}\n")

def opportunity_score(data):
    pre=load(PREFLIGHT_PATH); vals=[]
    for obj,keys in ((data.get('research') or {},('opportunity_score','adjusted_score','engagement_score')),(data.get('critique') or {},('revised_opportunity_score','opportunity_score','adjusted_score','engagement_score')),(data.get('selected_editorial_lane') or {},('adjusted_score','raw_score','engagement_score')),(pre.get('selected_opportunity') or {},('adjusted_score','raw_score','content_signal_score','engagement_score'))):
        if isinstance(obj,dict):
            for k in keys:
                try:v=float(obj.get(k) or 0)
                except:v=0
                if v>0:vals.append(v)
    return max(vals,default=0.0)

def authoritative_symbol(data):
    pre=load(PREFLIGHT_PATH); s=pre.get('selected_opportunity') or {}
    for value in (s.get('symbol'),s.get('topic'),(pre.get('content_director_4') or {}).get('primary_story',{}).get('symbol'),(data.get('draft') or {}).get('symbol')):
        x=re.sub(r'USDT$','',str(value or '').upper().replace('$','').strip())
        if re.fullmatch(r'[A-Z0-9]{2,15}',x):return x
    return ''

def visual_is_verified(expected_symbol=''):
    meta=load(VISUAL_META); mode=str(meta.get('visual_mode') or '')
    ok=(meta.get('provider')=='TradingView' and meta.get('status')=='TRADINGVIEW_CREATED' and mode in {'TRADINGVIEW_CHART_ONLY','TRADINGVIEW_CHART_PAIR'} and meta.get('overlays') is False and VISUAL.exists() and VISUAL.stat().st_size>=1000)
    if not ok:return False
    expected=f"BINANCE:{expected_symbol.upper().replace('USDT','')}USDT" if expected_symbol else ''
    actuals=[str(x).upper() for x in (meta.get('tradingview_symbols') or [])]
    if expected and actuals and expected not in actuals:
        print(f'Production manager: primary chart {expected!r} missing from {actuals!r}'); return False
    return True

def content_is_coherent(post,expected_symbol):
    return bool(post and expected_symbol and '$.' not in post and f'${expected_symbol}' in post.upper() and post.count('?')==1)

def choose_mode():
    ctx=load(ROOT/'data/live/publication_context.json'); mode=str(ctx.get('publication_mode') or '').lower()
    if mode in {'article','image'}:return mode
    cat=str(ctx.get('category') or '').lower(); return 'article' if cat in {'breaking_news','news_and_macro','macro'} else 'image'

def evaluate(report):
    data=load(report); draft=data.get('draft') or {}; post=str(draft.get('post') or draft.get('text') or '').strip(); rescue=data.get('publish_rescue') is True
    expected=authoritative_symbol(data); pre=load(PREFLIGHT_PATH); visual=dict(data.get('visual_plan') or {}); visual.update({'type':'candlestick_chart','use_visual':True,'provider':'TradingView'})
    try:
        from engagement_quality_gate import evaluate as gate
        interaction=gate(post,visual)
    except Exception as exc: interaction={'score':0,'publish':False,'reasons':[f'quality_gate_error:{type(exc).__name__}']}
    try:quality=float(draft.get('quality_score') or interaction.get('score') or 0)
    except:quality=float(interaction.get('score') or 0)
    intelligence=load(INTEL_PATH); intelligence_ok=intelligence.get('publish_recommendation') is True; opportunity=opportunity_score(data); chart_ok=visual_is_verified(expected); coherent=content_is_coherent(post,expected)
    threshold=RESCUE_QUALITY_THRESHOLD if rescue else QUALITY_THRESHOLD
    eligible=bool(post) and coherent and quality>=threshold and opportunity>=OPPORTUNITY_THRESHOLD and interaction.get('publish') is True and chart_ok and (rescue or (intelligence_ok and data.get('status')=='DRAFT_ONLY_NOT_PUBLISHED'))
    mode=choose_mode()
    audit={'draft':str(report),'publish':eligible,'mode':mode,'quality_score':quality,'quality_threshold':threshold,'opportunity_score':opportunity,'creator_intelligence_2':intelligence,'interaction_gate':interaction,'tradingview_required':True,'tradingview_verified':chart_ok,'chart_expected_symbol':expected,'visual_mode':load(VISUAL_META).get('visual_mode'),'content_coherent':coherent,'rescue':rescue,'reason':'publish_eligible' if eligible else 'gate_rejected'}
    AUDIT_PATH.write_text(json.dumps(audit,indent=2,ensure_ascii=False)); GATE_PATH.write_text(json.dumps(interaction,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(audit,indent=2,ensure_ascii=False)); return eligible,mode

def rescue_status():
    STATUS_PATH.parent.mkdir(parents=True,exist_ok=True); STATUS_PATH.write_text(json.dumps({'status':'LOCAL_FALLBACK_SUCCESS','generation_mode':'LOCAL_FALLBACK','reason':'Bounded deterministic rescue'},indent=2),encoding='utf-8')

def main():
    report=fresh_report()
    if not report:output(False);return 0
    publish,mode=evaluate(report)
    if publish:output(True,mode);return 0
    print('Production manager: normal gate rejected; running one bounded rescue.')
    rc=subprocess.run([sys.executable,str(ROOT/'src/publish_rescue.py')],cwd=ROOT,check=False).returncode
    if rc!=0:output(False);return 0
    rescue_status(); report=fresh_report()
    if not report:output(False);return 0
    publish,mode=evaluate(report); output(publish,mode); return 0
if __name__=='__main__':raise SystemExit(main())
