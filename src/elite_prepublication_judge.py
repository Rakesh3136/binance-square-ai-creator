"""Elite Pre-Publication Judge 1.1.
Hard editorial gate: publication must earn its way through evidence, originality,
reader value, specificity and integrity. Scoring is deterministic and semantic,
so useful posts are not rejected merely because they lack one exact keyword.
"""
from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT/'data/live/original_research.json'; REPORT_DIR=ROOT/'data/reports'; PUB=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/elite_prepublication_judge.json'
BAD_QUESTIONS={'what do you think','thoughts','agree or disagree','bullish or bearish','bullish, bearish, or wait','which coin are you watching','which asset are you watching'}
GENERIC={'this is the crypto story im watching right now','quick market check','the headline is only half the story','big things are coming','the market is watching'}
ENTITY_TERMS=('token','coin','asset','protocol','network','chain','stablecoin','bitcoin','ethereum','solana','binance','defi','layer 2','l2','exchange','wallet','users','developers','fees','revenue','tvl','liquidity','volume','supply','fdv','market cap','unlock','funding','flows','addresses')
MECHANISM_TERMS=('because','mechanism','driven by','explains why','the reason','connects','through','as a result','which means','leads to','causes','due to','means that','translates into','shows up in','flows into')
INVALIDATION_TERMS=('unless','if ','would change','would invalidate','invalidat','confirm','confirmation','fails if','what would','only if','watch for','signal')
def latest():
    xs=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True);return xs[0] if xs else None
def load(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return {}
def has_any(text,terms): return any(k in text for k in terms)
def semantic_specificity(text,facts):
    low=text.lower(); upper_tokens=set(re.findall(r'\b[A-Z][A-Z0-9]{1,9}\b',text))
    dollar_tokens=set(re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b',text))
    entities=sum(1 for k in ENTITY_TERMS if k in low)
    numeric=len(re.findall(r'\b\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?',text))
    named=min(30,len(upper_tokens|dollar_tokens)*10)
    context=min(20,entities*3)
    concrete=min(15,(facts+numeric)*5)
    return min(100,35+named+context+concrete)
def research_advantage(research,data):
    vals=[]
    for obj in (research,data):
        for key in ('information_advantage_score','research_information_advantage','originality_score','insight_score','thesis_score','opportunity_score'):
            v=obj.get(key) if isinstance(obj,dict) else None
            if isinstance(v,(int,float)): vals.append(float(v))
    return max(vals) if vals else None
def main():
    p=latest()
    if not p:raise SystemExit('Judge: no draft found')
    data=load(p); draft=data.get('draft') or {}; text=str(draft.get('post') or draft.get('text') or '').strip(); research=load(RESEARCH)
    low=text.lower(); lines=[x.strip() for x in text.splitlines() if x.strip()]; hook=lines[0].lower() if lines else ''
    questions=re.findall(r'[^\n.!?]*\?',text)
    facts=len(re.findall(r'\$[A-Z][A-Z0-9]{1,14}|\b\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?',text))
    mechanism=has_any(low,MECHANISM_TERMS)
    invalidation=has_any(low,INVALIDATION_TERMS)
    watch=has_any(low,('watch','next','signal','evidence','confirm','changes my view','what would'))
    attribution=has_any(low,('source:','reported','according to','announced','data from','according'))
    generic_q=any(q.strip().lower() in BAD_QUESTIONS for q in questions)
    generic_hook=hook in GENERIC or len(hook.split())<5
    evidence=min(100,35+facts*15+(20 if attribution else 0))
    specificity=semantic_specificity(text,facts)
    reader_value=min(100,45+(20 if mechanism else 0)+(15 if invalidation else 0)+(15 if watch else 0))
    adv=research_advantage(research,data)
    originality=min(100,45+(25 if adv is not None and adv>=50 else 0)+(15 if mechanism else 0)+(10 if invalidation else 0)+(5 if len(set(re.findall(r'\b[A-Z][A-Z0-9]{1,9}\b',text)))>=2 else 0))
    hook_score=max(0,90-(35 if generic_hook else 0)-(25 if len(hook.split())<8 else 0))
    conversation=max(0,90-(35 if generic_q else 0)) if len(questions)==1 else 20
    compliance=100 if not any(x in low for x in ('guaranteed profit','risk-free','guaranteed return','100% win')) else 0
    structure=min(100,50+(10 if len(lines)>=4 else 0)+(15 if mechanism else 0)+(15 if invalidation else 0))
    overall=round(evidence*.20+reader_value*.20+originality*.15+specificity*.15+hook_score*.08+structure*.08+conversation*.04+compliance*.10,1)
    failures=[]
    if not text:failures.append('empty_post')
    if len(questions)!=1:failures.append('must_have_exactly_one_question')
    if generic_q:failures.append('generic_engagement_question')
    if evidence<80:failures.append('evidence_below_80')
    if reader_value<80:failures.append('reader_value_below_80')
    if specificity<80:failures.append('specificity_below_80')
    if originality<78:failures.append('originality_below_78')
    if hook_score<82:failures.append('hook_below_82')
    if not mechanism:failures.append('missing_mechanism_or_reasoning')
    if not invalidation:failures.append('missing_invalidation_or_confirmation')
    if overall<85:failures.append('overall_below_85')
    if compliance<100:failures.append('policy_language_failure')
    result={'version':'1.1','generated_at':datetime.now(timezone.utc).isoformat(),'publish':not failures,'overall':overall,'scores':{'evidence_density':evidence,'reader_value':reader_value,'originality':originality,'specificity':specificity,'hook':hook_score,'structure':structure,'conversation_quality':conversation,'compliance':compliance},'checks':{'exactly_one_question':len(questions)==1,'mechanism_present':mechanism,'invalidation_or_confirmation_present':invalidation,'watch_next_present':watch,'attribution_present':attribution,'generic_question':generic_q,'generic_hook':generic_hook},'research_information_advantage':adv,'failures':failures,'decision':'PUBLISH' if not failures else 'REGENERATE_OR_WAIT'}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False))
    if failures:raise SystemExit(1)
if __name__=='__main__':main()
