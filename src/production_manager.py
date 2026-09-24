"""Final publication authority for the autonomous creator."""
from __future__ import annotations
import json,os,re,subprocess,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPORT_DIR=ROOT/'data/reports';STATUS_PATH=ROOT/'data/live/creator_status.json';PREFLIGHT_PATH=ROOT/'data/live/editorial_preflight.json';CONTEXT_PATH=ROOT/'data/live/publication_context.json';INTEL_PATH=ROOT/'data/live/creator_intelligence_2.json';GATE_PATH=ROOT/'data/live/engagement_gate.json';VISUAL_META=ROOT/'data/live/visual_metadata.json';VISUAL=ROOT/'data/live/visual.png';FROZEN_PATH=ROOT/'data/live/authoritative_opportunity.json';CADENCE_PATH=ROOT/'data/live/autonomous_cadence_6.json';ELITE_PATH=ROOT/'data/live/elite_prepublication_judge.json';ASSET_LOCK=ROOT/'src/final_asset_lock.py';AUDIT_PATH=Path('/tmp/publish_gate.json');DECISION_PATH=ROOT/'data/live/production_decision.json'
QUALITY_THRESHOLD=72.0;OPPORTUNITY_THRESHOLD=60.0;RESCUE_QUALITY_THRESHOLD=82.0;MAX_AGE_SECONDS=20*60;NONCHART={'crypto_meme','market_meme','trader_humor','education','commentary','community','result_followup'}
GENERIC_PHRASES=('follow-through matters','the next reaction matters','the interesting part starts after','this is interesting','watch what traders do','quick market check','fresh check','here is what matters','here\'s what matters','the market is watching','now watch','bull case:','bear case:','not a promise about the next candle','what specific reaction on')
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
    ctx=load(CONTEXT_PATH);frozen=load(FROZEN_PATH);pre=load(PREFLIGHT_PATH);return str(ctx.get('category') or frozen.get('category') or (pre.get('selected_opportunity') or {}).get('category') or '').lower()
def opportunity_score(data):
    pre=load(PREFLIGHT_PATH);frozen=load(FROZEN_PATH);cadence=load(CADENCE_PATH);vals=[]
    if category()=='result_followup':return 100.0
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
    meta=load(VISUAL_META);provider=str(meta.get('provider') or '');status=str(meta.get('status') or '')
    if not VISUAL.exists() or VISUAL.stat().st_size < 1000:return False
    if provider=='Local historical OHLCV renderer' and status=='HISTORICAL_SNAPSHOT_CREATED':
        snap=load(ROOT/'data/live/historical_setup_snapshot.json');ctx=load(CONTEXT_PATH);current=clean_symbol(ctx.get('symbol') or expected)
        if snap.get('status')!='FROZEN' or snap.get('lookahead_protection') is not True:return False
        snap_symbol=clean_symbol(snap.get('symbol'))
        if current and snap_symbol != current:return False
        if expected and snap_symbol != clean_symbol(expected):return False
        if clean_symbol(meta.get('base_symbol')) != snap_symbol:return False
        if str(meta.get('signal_created_at') or '')!=str(snap.get('signal_created_at') or ''):return False
        if str(meta.get('data_cutoff') or '')!=str(snap.get('data_cutoff') or ''):return False
        pred=snap.get('prediction') if isinstance(snap.get('prediction'),dict) else {};marks=meta.get('prediction_markings') if isinstance(meta.get('prediction_markings'),dict) else {}
        for key in ('direction','entry_trigger','tp1','tp2','sl'):
            if marks.get(key) != pred.get(key):return False
        return True
    mode=str(meta.get('visual_mode') or '');valid_modes={'TRADINGVIEW_CHART_ONLY','TRADINGVIEW_CHART_PAIR','TRADINGVIEW_CHART_ANNOTATED','TRADINGVIEW_CHART_WITH_SETUP_LEVELS'}
    ok=provider=='TradingView' and status=='TRADINGVIEW_CREATED' and mode in valid_modes
    if not ok:return False
    actuals=[str(x).upper() for x in (meta.get('tradingview_symbols') or [])]
    return not expected or not actuals or f'BINANCE:{clean_symbol(expected)}USDT' in actuals or f'BINANCE:{clean_symbol(expected)}USDT.P' in actuals
def ensure_signal_contract_text(post, cat, contract):
    """Bind the immutable frozen setup into the final draft when labels were
    lost by a prose/normalization stage. Values come only from the frozen
    contract; this never creates new levels or changes the setup."""
    if cat not in {'flow','capital_flow_long','capital_flow_short','creator_signal_outcome','follow_up','technical_setup'}:
        return str(post or '')
    required=('direction','entry_trigger','tp1','tp2','sl')
    if not all(contract.get(k) is not None and str(contract.get(k)).strip() for k in required):
        return str(post or '')
    text=str(post or '').strip()
    low=text.lower()
    direction=str(contract['direction']).upper().replace('_BIAS','')
    missing=[]
    if direction not in low and direction not in {'LONG','SHORT'}:
        missing.append(f"Direction: {direction}")
    elif direction not in low:
        missing.append(f"Direction: {direction}")
    labels=(
        ('entry_trigger','Entry trigger'),
        ('tp1','TP1'),
        ('tp2','TP2'),
        ('sl','SL / invalidation'),
    )
    for key,label in labels:
        if label.lower() not in low:
            missing.append(f"{label}: {contract[key]}")
    if not missing:
        return text
    block=' | '.join(missing)
    return (text.rstrip() + '\\n\\n' + block).strip()

def human_content_audit(post,expected,cat):
    text=re.sub(r'\s+',' ',str(post or '').strip());low=text.lower();fails=[];score=100
    if not text:fails.append('empty_post');return score,fails
    if text.count('?')!=1:fails.append('question_count');score-=20
    if len(text)<280:fails.append('too_short_for_analysis');score-=18
    if len(text)>900:fails.append('too_long');score-=12
    if expected and f'${expected}' not in text.upper():fails.append('missing_primary_cashtag');score-=25
    hits=[p for p in GENERIC_PHRASES if p in low]
    if hits:fails.append('generic_template_language:'+','.join(hits[:4]));score-=12*min(3,len(hits))
    if re.match(r'^[🔥🚀📈📉💥\s]*\$?[A-Z0-9]{1,15}\s+(just\s+)?moved\s+[+-]?\d',text,re.I):fails.append('ticker_percent_hook');score-=15
    mechanism_terms=('because','which means','driven by','implies','suggests','versus','relative to','liquidity','volume acceleration','volume pressure','rejection','acceptance','open interest','funding','catalyst','supply','flow')
    if not any(x in low for x in mechanism_terms):fails.append('no_mechanism_or_relationship');score-=18
    if len(re.findall(r'\$?\d+(?:\.\d+)?%?',text))>9:fails.append('number_dump');score-=10
    if cat not in NONCHART and not any(x in low for x in ('confirm','invalidate','break','hold','reject','reclaim','support','resistance')):fails.append('no_testable_condition');score-=15
    return max(0,score),fails
def content_is_coherent(post,expected,cat):
    if not post or post.count('?')!=1:return False
    if cat in NONCHART:return True
    return bool(expected and '$.' not in post and f'${expected}' in post.upper())
def choose_mode():
    ctx=load(CONTEXT_PATH);mode=str(ctx.get('publication_mode') or '').lower();cat=category();return mode if mode in {'article','image'} else ('article' if cat in {'breaking_news','news_and_macro','macro'} else 'image')
def final_asset_ok(report):
    env=dict(os.environ);env['DRAFT_PATH']=str(report);return subprocess.run([sys.executable,str(ASSET_LOCK)],cwd=ROOT,env=env,check=False).returncode==0
def write_decision(audit):
    DECISION_PATH.parent.mkdir(parents=True,exist_ok=True);DECISION_PATH.write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
def jev_gate(data,post,cat,expected,contract,quality,opportunity,deterministic_ok):
    try:
        from jev_decision_gate import evaluate
        return evaluate(symbol=expected,category=cat,post=post,direction=str(contract.get('direction') or ''),entry=contract.get('entry_trigger'),tp1=contract.get('tp1'),tp2=contract.get('tp2'),sl=contract.get('sl'),opportunity_score=opportunity,quality_score=quality,evidence=[f'deterministic_gate:{deterministic_ok}',f'opportunity_score:{opportunity}',f'quality_score:{quality}',f'category:{cat}'],deterministic_ok=deterministic_ok)
    except Exception as exc:
        return {'enabled':False,'status':f'error:{type(exc).__name__}','publish':deterministic_ok,'confidence':0.0}
def evaluate(report):
    data=load(report);draft=data.get('draft') or {};post=str(draft.get('post') or draft.get('text') or '').strip();rescue=data.get('publish_rescue') is True;ctx=load(CONTEXT_PATH);cat=category();expected=authoritative_symbol(data);asset_ok=final_asset_ok(report)
    try:
        from engagement_quality_gate import evaluate as gate;interaction=gate(post,{'type':'none','use_visual':False} if cat in NONCHART else {'type':'candlestick_chart','use_visual':True,'provider':'TradingView','publication_mode':choose_mode()})
    except Exception as exc:interaction={'score':0,'publish':False,'reasons':[f'quality_gate_error:{type(exc).__name__}']}
    try:quality=float(draft.get('quality_score') or interaction.get('score') or 0)
    except:quality=float(interaction.get('score') or 0)
    human_score,human_failures=human_content_audit(post,expected,cat);signal_lanes={'flow','capital_flow_long','capital_flow_short','creator_signal_outcome','follow_up','technical_setup'};frozen=load(FROZEN_PATH);prediction=frozen.get('prediction') if isinstance(frozen.get('prediction'),dict) else {};contract={'direction':frozen.get('direction') or prediction.get('direction'),'entry_trigger':frozen.get('entry_trigger') or prediction.get('entry_trigger'),'tp1':frozen.get('tp1') or prediction.get('tp1'),'tp2':frozen.get('tp2') or prediction.get('tp2'),'sl':frozen.get('sl') or prediction.get('sl')}
    repaired_post=ensure_signal_contract_text(post,cat,contract)
    if repaired_post != post:
        draft['post']=repaired_post; draft['text']=repaired_post; post=repaired_post
        Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
        print('Production manager: restored frozen signal contract labels from authoritative snapshot')
    if cat in signal_lanes and all(v is not None and str(v).strip() for v in contract.values()):
        for marker in (str(contract['direction']).upper(),'Entry trigger:','TP1:','TP2:','SL / invalidation:'):
            if marker.lower() not in post.lower():human_failures.append('signal_contract_missing:'+marker)
        human_score=min(human_score,90 if not any(x.startswith('signal_contract_missing:') for x in human_failures) else 68)
    quality=min(quality,human_score);intelligence=load(INTEL_PATH);elite=load(ELITE_PATH);intelligence_ok=(cat=='result_followup') or intelligence.get('publish_recommendation') is True;opportunity=opportunity_score(data);chart_ok=cat in NONCHART or visual_is_verified(expected);coherent=content_is_coherent(post,expected,cat);failures=list(elite.get('failures') or []) if isinstance(elite,dict) else [];failures.extend(human_failures);hard_prefixes=('quality_gate_error','policy_language_failure','malformed_statistics_phrase','repetitive_feed_template','repeats_recent_published_sentence');hard_exact={'empty_post','missing_primary_cashtag'};hard_block=bool(any(any(x==p or x.startswith(p+':') for p in hard_prefixes) for x in failures) or any(x in hard_exact for x in failures));threshold=RESCUE_QUALITY_THRESHOLD if rescue else QUALITY_THRESHOLD;deterministic_ok=bool(post) and asset_ok and coherent and quality>=threshold and opportunity>=OPPORTUNITY_THRESHOLD and interaction.get('publish') is True and chart_ok and (rescue or (intelligence_ok and (data.get('status')=='DRAFT_ONLY_NOT_PUBLISHED' or cat=='result_followup'))) and not hard_block
    mode=choose_mode();jev=jev_gate(data,post,cat,expected,contract,quality,opportunity,deterministic_ok);jev_enabled=bool(jev.get('enabled'));eligible=bool(deterministic_ok and (not jev_enabled or jev.get('publish') is True));audit={'version':'6.4-jev-decision-layer','draft':str(report),'publish':eligible,'mode':mode,'category':cat,'quality_score':quality,'human_content_score':human_score,'quality_threshold':threshold,'opportunity_score':opportunity,'interaction_gate':interaction,'human_content_failures':human_failures,'final_asset_lock':asset_ok,'tradingview_required':cat not in NONCHART,'tradingview_verified':chart_ok,'chart_expected_symbol':expected,'publication_context_symbol':ctx.get('symbol',''),'content_coherent':coherent,'rescue':rescue,'elite_failures':failures,'hard_block':hard_block,'rescue_allowed':not hard_block,'deterministic_publish':deterministic_ok,'jev':{k:v for k,v in jev.items() if k!='raw'},'reason':'publish_eligible' if eligible else ('jev_review_or_block' if deterministic_ok and jev_enabled else 'gate_rejected')};AUDIT_PATH.write_text(json.dumps(audit,indent=2,ensure_ascii=False));GATE_PATH.write_text(json.dumps(interaction,indent=2),encoding='utf-8');write_decision(audit);print(json.dumps(audit,indent=2,ensure_ascii=False));return eligible,mode
def rescue_status():STATUS_PATH.parent.mkdir(parents=True,exist_ok=True);STATUS_PATH.write_text(json.dumps({'status':'LOCAL_FALLBACK_SUCCESS','generation_mode':'LOCAL_FALLBACK','reason':'Bounded deterministic rescue'},indent=2),encoding='utf-8')
def main():
    report=fresh_report()
    if not report:output(False);return 0
    publish,mode=evaluate(report)
    if publish:output(True,mode);return 0
    audit=load(DECISION_PATH,{})
    if category()=='result_followup' or bool(audit.get('hard_block')):output(False,mode);print('Production manager: rescue blocked by hard integrity/policy failure.');return 0
    print('Production manager: normal gate rejected; running one bounded rescue for repairable content/format failures.')
    rc=subprocess.run([sys.executable,str(ROOT/'src/publish_rescue.py')],cwd=ROOT,check=False).returncode
    if rc!=0:output(False,mode);return 0
    rescue_status();report=fresh_report()
    if not report:output(False);return 0
    publish,mode=evaluate(report);output(publish,mode);return 0
if __name__=='__main__':raise SystemExit(main())
