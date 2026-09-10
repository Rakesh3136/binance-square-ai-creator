"""Final publication authority for the autonomous creator.

The frozen opportunity is immutable. Trading lanes require a verified chart;
reach/editorial lanes such as crypto_meme do not. Rescue may repair presentation
failures but can never override asset, integrity, originality or truth failures.
"""
from __future__ import annotations
import json,os,re,subprocess,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPORT_DIR=ROOT/'data/reports';STATUS_PATH=ROOT/'data/live/creator_status.json';PREFLIGHT_PATH=ROOT/'data/live/editorial_preflight.json';CONTEXT_PATH=ROOT/'data/live/publication_context.json';INTEL_PATH=ROOT/'data/live/creator_intelligence_2.json';GATE_PATH=ROOT/'data/live/engagement_gate.json';VISUAL_META=ROOT/'data/live/visual_metadata.json';VISUAL=ROOT/'data/live/visual.png';FROZEN_PATH=ROOT/'data/live/authoritative_opportunity.json';CADENCE_PATH=ROOT/'data/live/autonomous_cadence_6.json';ELITE=ROOT/'data/live/elite_prepublication_judge.json';AUDIT_PATH=Path('/tmp/publish_gate.json')
QUALITY_THRESHOLD=68.0;OPPORTUNITY_THRESHOLD=60.0;RESCUE_QUALITY_THRESHOLD=75.0;MAX_AGE_SECONDS=20*60;NONCHART={'crypto_meme','market_meme','trader_humor','education','commentary','community'};TRADING={'technical_setup','high_volatility','top_gainers','top_losers','creator_signal_outcome','capital_flow','capital_flow_setup','conditional_trade'}

def load(path,default=None):
    if not Path(path).exists():return {} if default is None else default
    try:
        x=json.loads(Path(path).read_text(encoding='utf-8'));return x if isinstance(x,type(default or {})) else ({} if default is None else default)
    except Exception:return {} if default is None else default

def fresh_report():
    reports=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if not reports:return None
    p=reports[0];return p if datetime.now().timestamp()-p.stat().st_mtime<=MAX_AGE_SECONDS else None

def output(publish,mode='image'):
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:f.write(f"publish={'true' if publish else 'false'}\nmode={mode}\n")

def clean_symbol(v):
    x=re.sub(r'USDT$','',str(v or '').upper().replace('$','').strip());return x if re.fullmatch(r'[A-Z0-9]{1,15}',x) else ''

def category():
    ctx=load(CONTEXT_PATH);frozen=load(FROZEN_PATH);pre=load(PREFLIGHT_PATH)
    return str(ctx.get('category') or frozen.get('category') or (pre.get('selected_opportunity') or {}).get('category') or '').lower()

def opportunity_score(data):
    pre=load(PREFLIGHT_PATH);frozen=load(FROZEN_PATH);cadence=load(CADENCE_PATH);vals=[]
    sources=[(data.get('research') or {},('opportunity_score','adjusted_score','engagement_score')),(data.get('critique') or {},('revised_opportunity_score','opportunity_score','adjusted_score','engagement_score')),(pre.get('selected_opportunity') or {},('selected_score','adjusted_score','raw_score','content_signal_score','engagement_score','news_score')),(frozen,('selected_score','effective_score','score','adjusted_score','raw_score','engagement_score')),(cadence,('effective_score','selected_score','opportunity_score','score'))]
    for obj,keys in sources:
        for k in keys:
            try:v=float(obj.get(k) or 0)
            except:v=0
            if v>0:vals.append(v)
    return max(vals,default=0.0)

def authoritative_symbol(data):
    ctx=load(CONTEXT_PATH);frozen=load(FROZEN_PATH);pre=load(PREFLIGHT_PATH)
    for v in (ctx.get('symbol'),frozen.get('symbol'),(pre.get('selected_opportunity') or {}).get('symbol'),(data.get('draft') or {}).get('symbol')):
        x=clean_symbol(v)
        if x:return x
    return ''

def visual_is_verified(expected=''):
    meta=load(VISUAL_META);mode=str(meta.get('visual_mode') or '')
    ok=meta.get('provider')=='TradingView' and meta.get('status')=='TRADINGVIEW_CREATED' and mode in {'TRADINGVIEW_CHART_ONLY','TRADINGVIEW_CHART_PAIR','TRADINGVIEW_CHART_ANNOTATED'} and VISUAL.exists() and VISUAL.stat().st_size>=1000
    if not ok:return False
    actuals=[str(x).upper() for x in (meta.get('tradingview_symbols') or [])]
    return not expected or not actuals or f'BINANCE:{expected.upper()}USDT' in actuals or f'BINANCE:{expected.upper()}USDT.P' in actuals

def content_is_coherent(post,expected,cat):
    if not post:return False
    if post.count('?')!=1:return False
    if cat in NONCHART:return True
    return bool(expected and '$.' not in post and f'${expected}' in post.upper())

def choose_mode():
    ctx=load(CONTEXT_PATH);mode=str(ctx.get('publication_mode') or '').lower();cat=category()
    if mode in {'article','image'}:return mode
    return 'article' if cat in {'breaking_news','news_and_macro','macro'} else 'image'

def evaluate(report):
    data=load(report);draft=data.get('draft') or {};post=str(draft.get('post') or draft.get('text') or '').strip();rescue=data.get('publish_rescue') is True;ctx=load(CONTEXT_PATH);cat=category();expected=authoritative_symbol(data)
    try:
        from engagement_quality_gate import evaluate as gate;interaction=gate(post,{'type':'none','use_visual':False} if cat in NONCHART else {'type':'candlestick_chart','use_visual':True,'provider':'TradingView'})
    except Exception as exc:interaction={'score':0,'publish':False,'reasons':[f'quality_gate_error:{type(exc).__name__}']}
    try:quality=float(draft.get('quality_score') or interaction.get('score') or 0)
    except:quality=float(interaction.get('score') or 0)
    intelligence=load(INTEL_PATH);elite=load(ELITE_PATH) if False else load(ELITE);intelligence_ok=intelligence.get('publish_recommendation') is True;opportunity=opportunity_score(data);chart_ok=True if cat in NONCHART else visual_is_verified(expected);coherent=content_is_coherent(post,expected,cat)
    failures=list(elite.get('failures') or []) if isinstance(elite,dict) else []
    hard_elite={'malformed_statistics_phrase','repetitive_feed_template','template_phrase_density','repeats_recent_published_sentence','policy_language_failure'}
    rescue_forbidden=bool(set(failures)&hard_elite)
    threshold=RESCUE_QUALITY_THRESHOLD if rescue else QUALITY_THRESHOLD
    eligible=bool(post) and coherent and quality>=threshold and opportunity>=OPPORTUNITY_THRESHOLD and interaction.get('publish') is True and chart_ok and (rescue or (intelligence_ok and data.get('status')=='DRAFT_ONLY_NOT_PUBLISHED')) and not rescue_forbidden
    mode=choose_mode();audit={'version':'5.3','draft':str(report),'publish':eligible,'mode':mode,'category':cat,'quality_score':quality,'quality_threshold':threshold,'opportunity_score':opportunity,'creator_intelligence_2':intelligence,'interaction_gate':interaction,'tradingview_required':cat not in NONCHART,'tradingview_verified':chart_ok,'chart_expected_symbol':expected,'publication_context_symbol':ctx.get('symbol',''),'visual_mode':load(VISUAL_META).get('visual_mode'),'content_coherent':coherent,'rescue':rescue,'elite_failures':failures,'rescue_forbidden':rescue_forbidden,'reason':'publish_eligible' if eligible else 'gate_rejected'}
    AUDIT_PATH.write_text(json.dumps(audit,indent=2,ensure_ascii=False));GATE_PATH.write_text(json.dumps(interaction,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(audit,indent=2,ensure_ascii=False));return eligible,mode

def rescue_status():
    STATUS_PATH.parent.mkdir(parents=True,exist_ok=True);STATUS_PATH.write_text(json.dumps({'status':'LOCAL_FALLBACK_SUCCESS','generation_mode':'LOCAL_FALLBACK','reason':'Bounded deterministic rescue'},indent=2),encoding='utf-8')

def main():
    report=fresh_report()
    if not report:output(False);return 0
    publish,mode=evaluate(report)
    if publish:output(True,mode);return 0
    elite=load(ELITE);failures=set(elite.get('failures') or []) if isinstance(elite,dict) else set();hard={'malformed_statistics_phrase','repetitive_feed_template','template_phrase_density','repeats_recent_published_sentence','policy_language_failure'}
    if failures&hard:output(False,mode);print('Production manager: rescue blocked by hard editorial failure.');return 0
    print('Production manager: normal gate rejected; running one bounded rescue.')
    rc=subprocess.run([sys.executable,str(ROOT/'src/publish_rescue.py')],cwd=ROOT,check=False).returncode
    if rc!=0:output(False);return 0
    rescue_status();report=fresh_report()
    if not report:output(False);return 0
    publish,mode=evaluate(report);output(publish,mode);return 0
if __name__=='__main__':raise SystemExit(main())
