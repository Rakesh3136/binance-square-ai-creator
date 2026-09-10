"""Elite Pre-Publication Judge 1.6.
Hard editorial gate: publication must earn its way through evidence, originality,
reader value, specificity, integrity and human-style originality. The judge also
blocks repetitive feed templates and malformed statistics phrasing.
"""
from __future__ import annotations
import json,re,os
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT/'data/live/original_research.json'
REPORT_DIR=ROOT/'data/reports'
PUBLICATION_LOG=ROOT/'analytics/publication_log.jsonl'
OUT=ROOT/'data/live/elite_prepublication_judge.json'
BAD_QUESTIONS={'what do you think','thoughts','agree or disagree','bullish or bearish','bullish, bearish, or wait','which coin are you watching','which asset are you watching'}
GENERIC={'this is the crypto story im watching right now','quick market check','the headline is only half the story','big things are coming','the market is watching'}
ENTITY_TERMS=('token','coin','asset','protocol','network','chain','stablecoin','bitcoin','ethereum','solana','binance','defi','layer 2','l2','exchange','wallet','users','developers','fees','revenue','tvl','liquidity','volume','supply','fdv','market cap','unlock','funding','flows','addresses')
MECHANISM_TERMS=('because','mechanism','driven by','explains why','the reason','connects','through','as a result','which means','leads to','causes','due to','means that','translates into','shows up in','flows into','results in','comes from','depends on','hinges on','works through','is linked to','matters because','suggests that','implies that','so the effect','this matters because','in turn','which can make','which can leave')
INVALIDATION_TERMS=('unless','if ','would change','would invalidate','invalidat','confirm','confirmation','fails if','what would','only if','watch for','signal')
CAUSAL_OR_RELATIONAL_TERMS=('because','while','versus','vs','relative to','compared with','despite','instead of','rather than','but','yet','therefore','so','which means','as a result','in turn','linked to','flows into','depends on','hinges on','translates into')
TEMPLATE_PATTERNS=(
    r'\$[a-z0-9]+\s+just dropped\s+[\d.]+%\s*[—-]\s*now the reaction matters',
    r'spot volume is\s+\$?[\d,.]+[kmb]?\s+spot volume',
    r'bear case:\s+.*bull case:\s+.*would you (watch|wait)',
    r'sellers keep control below support\.?\s*bull case:',
    r'buyers keep control above support\.?\s*bear case:',
)

def resolve_report():
    explicit=os.getenv('DRAFT_PATH','').strip()
    if explicit:
        p=Path(explicit)
        if not p.exists(): raise SystemExit(f'Judge: DRAFT_PATH does not exist: {explicit}')
        return p
    xs=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    return xs[0] if xs else None

def load(p):
    try:return json.loads(Path(p).read_text(encoding='utf-8'))
    except Exception:return {}

def has_any(text,terms): return any(k in text for k in terms)

def semantic_specificity(text,facts,adv=None):
    low=text.lower()
    upper_tokens=set(re.findall(r'\b[A-Z][A-Z0-9]{1,9}\b',text))
    dollar_tokens=set(re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b',text))
    symbols=discussed_symbols(text)
    entities=sum(1 for k in ENTITY_TERMS if k in low)
    numeric=len(re.findall(r'\b\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?',text))
    named=min(20,len(upper_tokens|dollar_tokens)*8)
    asset_anchor=15 if symbols else 0
    context=min(20,entities*3)
    concrete=min(20,(facts+numeric)*5)
    research_anchor=10 if isinstance(adv,(int,float)) and adv>=50 else 0
    return min(100,35+asset_anchor+named+context+concrete+research_anchor)

def discussed_symbols(text):
    symbols=set(re.findall(r'\$([A-Z][A-Z0-9]{1,14})\b', text.upper()))
    symbols |= set(x.upper() for x in re.findall(r'\b([A-Z][A-Z0-9]{1,14})USDT\b', text.upper()))
    return symbols

def research_advantage(research,data,text):
    vals=[]; symbols=discussed_symbols(text)
    for gem in (research.get('potential_gems') or []):
        if not isinstance(gem,dict): continue
        sym=str(gem.get('symbol') or '').upper().replace('USDT','')
        if sym and sym in symbols:
            for key in ('information_advantage_score','undercoverage_score','thesis_score','opportunity_score'):
                v=gem.get(key)
                if isinstance(v,(int,float)): vals.append(float(v))
            nested=gem.get('information_advantage')
            if isinstance(nested,dict):
                for key in ('score','information_advantage_score'):
                    v=nested.get(key)
                    if isinstance(v,(int,float)): vals.append(float(v))
    for obj in (data,research):
        if isinstance(obj,dict):
            for key in ('information_advantage_score','research_information_advantage','originality_score','insight_score','thesis_score','opportunity_score'):
                v=obj.get(key)
                if isinstance(v,(int,float)): vals.append(float(v))
            for container_key in ('selected_opportunity','selected_editorial_lane','research','original_research'):
                sub=obj.get(container_key)
                if isinstance(sub,dict):
                    for key in ('information_advantage_score','research_information_advantage','originality_score','insight_score','thesis_score','opportunity_score'):
                        v=sub.get(key)
                        if isinstance(v,(int,float)): vals.append(float(v))
    return max(vals) if vals else None

def originality_score(text,facts,attribution,mechanism,invalidation,adv):
    low=text.lower(); symbols=discussed_symbols(text)
    named_tokens=set(re.findall(r'\b[A-Z][A-Z0-9]{1,9}\b',text)) | set(re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b',text))
    causal_hits=sum(1 for term in CAUSAL_OR_RELATIONAL_TERMS if term in low)
    sentence_count=max(1,len([s for s in re.split(r'[.!?]+',text) if s.strip()]))
    distinct_words=len(set(re.findall(r"[A-Za-z][A-Za-z'-]{2,}",low))); words=len(re.findall(r"[A-Za-z][A-Za-z'-]+",low))
    lexical_diversity=distinct_words/max(1,words)
    breakdown={'base_editorial_synthesis':40,'asset_specific_research':15 if adv is not None and adv>=50 else 0,'mechanism':10 if mechanism else 0,'invalidation_or_confirmation':10 if invalidation else 0,'source_attribution':5 if attribution else 0,'multi_entity_relationship':8 if len(symbols)>=2 or len(named_tokens)>=3 else 0,'causal_or_contrast_language':7 if causal_hits>=2 else (4 if causal_hits==1 else 0),'concrete_evidence_mix':5 if facts>=3 else (3 if facts==2 else 0),'lexical_novelty':5 if lexical_diversity>=0.58 and sentence_count>=3 else (3 if lexical_diversity>=0.50 else 0)}
    return min(100,sum(breakdown.values())),breakdown

def template_artifacts(text):
    low=re.sub(r'\s+',' ',text.lower()).strip()
    hits=[p for p in TEMPLATE_PATTERNS if re.search(p,low,re.I|re.S)]
    # Repetition of the same generic sentence family inside one post is also a failure.
    phrase_hits=sum(1 for p in ('reaction matters','bear case:','bull case:','reclaims the range','keep control below support','keep control above support') if p in low)
    return hits,phrase_hits

def recent_similarity(text):
    """Lightweight phrase-overlap check against recent published posts.
    It is intentionally conservative: only exact normalized sentence matches are
    treated as a hard repetition signal.
    """
    if not PUBLICATION_LOG.exists(): return []
    current={re.sub(r'[^a-z0-9 ]','',s.lower()).strip() for s in re.split(r'[.!?]+',text) if len(s.split())>=6}
    if not current: return []
    matches=[]
    try:
        rows=PUBLICATION_LOG.read_text(encoding='utf-8').splitlines()[-12:]
        for row in rows:
            try:o=json.loads(row)
            except Exception:continue
            old=str(o.get('text') or o.get('post') or o.get('content') or '')
            oldset={re.sub(r'[^a-z0-9 ]','',s.lower()).strip() for s in re.split(r'[.!?]+',old) if len(s.split())>=6}
            common=current & oldset
            if common: matches.extend(sorted(common))
    except Exception: pass
    return matches[:6]

def main():
    p=resolve_report()
    if not p: raise SystemExit('Judge: no draft found')
    data=load(p); draft=data.get('draft') or {}
    text=str(draft.get('post') or draft.get('text') or '').strip(); research=load(RESEARCH); low=text.lower()
    lines=[x.strip() for x in text.splitlines() if x.strip()]; hook=lines[0].lower() if lines else ''
    questions=re.findall(r'[^\n.!?]*\?',text)
    facts=len(re.findall(r'\$[A-Z][A-Z0-9]{1,14}|\b\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?',text))
    mechanism=has_any(low,MECHANISM_TERMS); invalidation=has_any(low,INVALIDATION_TERMS); watch=has_any(low,('watch','next','signal','evidence','confirm','changes my view','what would'))
    attribution=has_any(low,('source:','reported','according to','announced','data from','according'))
    generic_q=any(q.strip().lower() in BAD_QUESTIONS for q in questions); generic_hook=hook in GENERIC or len(hook.split())<5
    malformed_stats=bool(re.search(r'\bspot volume is\s+\$?[\d,.]+[kmb]?\s+spot volume\b',low))
    template_hits,template_phrase_hits=template_artifacts(text); repeated_sentences=recent_similarity(text)
    evidence=min(100,35+facts*15+(20 if attribution else 0)); adv=research_advantage(research,data,text); specificity=semantic_specificity(text,facts,adv)
    reader_value=min(100,45+(20 if mechanism else 0)+(15 if invalidation else 0)+(15 if watch else 0)); originality,originality_breakdown=originality_score(text,facts,attribution,mechanism,invalidation,adv)
    hook_score=max(0,90-(35 if generic_hook else 0)-(25 if len(hook.split())<8 else 0)); conversation=max(0,90-(35 if generic_q else 0)) if len(questions)==1 else 20
    compliance=100 if not any(x in low for x in ('guaranteed profit','risk-free','guaranteed return','100% win')) else 0
    structure=min(100,50+(10 if len(lines)>=4 else 0)+(15 if mechanism else 0)+(15 if invalidation else 0))
    overall=round(evidence*.20+reader_value*.20+originality*.15+specificity*.15+hook_score*.08+structure*.08+conversation*.04+compliance*.10,1)
    failures=[]
    if not text: failures.append('empty_post')
    if len(questions)!=1: failures.append('must_have_exactly_one_question')
    if generic_q: failures.append('generic_engagement_question')
    if evidence<80: failures.append('evidence_below_80')
    if reader_value<80: failures.append('reader_value_below_80')
    if specificity<80: failures.append('specificity_below_80')
    if originality<78: failures.append('originality_below_78')
    if hook_score<82: failures.append('hook_below_82')
    if not mechanism: failures.append('missing_mechanism_or_reasoning')
    if not invalidation: failures.append('missing_invalidation_or_confirmation')
    if overall<85: failures.append('overall_below_85')
    if compliance<100: failures.append('policy_language_failure')
    if malformed_stats: failures.append('malformed_statistics_phrase')
    if template_hits: failures.append('repetitive_feed_template')
    if template_phrase_hits>=3: failures.append('template_phrase_density')
    if repeated_sentences: failures.append('repeats_recent_published_sentence')
    result={'version':'1.6','generated_at':datetime.now(timezone.utc).isoformat(),'draft_path':str(p),'publish':not failures,'overall':overall,'scores':{'evidence_density':evidence,'reader_value':reader_value,'originality':originality,'specificity':specificity,'hook':hook_score,'structure':structure,'conversation_quality':conversation,'compliance':compliance},'checks':{'exactly_one_question':len(questions)==1,'mechanism_present':mechanism,'invalidation_or_confirmation_present':invalidation,'watch_next_present':watch,'attribution_present':attribution,'generic_question':generic_q,'generic_hook':generic_hook,'malformed_statistics_phrase':malformed_stats,'repetitive_feed_template':bool(template_hits),'recent_sentence_repetition':bool(repeated_sentences)},'originality_breakdown':originality_breakdown,'research_information_advantage':adv,'research_advantage_scope':'asset_specific_when_available','template_artifacts':template_hits,'template_phrase_hits':template_phrase_hits,'recent_repeated_sentences':repeated_sentences,'failures':failures,'decision':'PUBLISH' if not failures else 'REGENERATE_OR_WAIT'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))
    if failures: raise SystemExit(1)
if __name__=='__main__': main()
