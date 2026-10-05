"""NIC Elite Pre-Publication Judge 1.6."""
from __future__ import annotations
import json,re,os
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT/'data/live/original_research.json'; REPORT_DIR=ROOT/'data/reports'; PUBLICATION_LOG=ROOT/'analytics/publication_log.jsonl'; OUT=ROOT/'data/live/elite_prepublication_judge.json'
BAD_QUESTIONS={'what do you think','thoughts','agree or disagree','bullish or bearish','bullish, bearish, or wait','which coin are you watching','which asset are you watching'}
GENERIC={'this is the crypto story im watching right now','quick market check','the headline is only half the story','big things are coming','the market is watching'}
ENTITY_TERMS=('token','coin','asset','protocol','network','chain','stablecoin','bitcoin','ethereum','solana','binance','defi','layer 2','l2','exchange','wallet','users','developers','fees','revenue','tvl','liquidity','volume','supply','fdv','market cap','unlock','funding','flows','addresses')
MECHANISM_TERMS=('because','mechanism','driven by','explains why','the reason','connects','through','as a result','which means','leads to','causes','due to','means that','translates into','shows up in','flows into','results in','comes from','depends on','hinges on','works through','is linked to','matters because','suggests that','implies that','so the effect','this matters because','in turn','which can make','which can leave')
INVALIDATION_TERMS=('unless','if ','would change','would invalidate','invalidat','confirm','confirmation','fails if','what would','only if','watch for','signal')
CAUSAL_OR_RELATIONAL_TERMS=('because','while','versus','vs','relative to','compared with','despite','instead of','rather than','but','yet','therefore','so','which means','as a result','in turn','linked to','flows into','depends on','hinges on','translates into')
TEMPLATE_PATTERNS=(r'\$[a-z0-9]+\s+just dropped\s+[\d.]+%\s*[—-]\s*now the reaction matters',r'spot volume is\s+\$?[\d,.]+[kmb]?\s+spot volume',r'bear case:\s+.*bull case:\s+.*would you (watch|wait)',r'sellers keep control below support\.?\s*bull case:',r'buyers keep control above support\.?\s*bear case:')
# Canonicalized after punctuation removal. This disclaimer is mandatory/reusable.
REUSABLE_DISCLAIMER_SENTENCES={'levels are chartderived scenarios not guarantees'}

def resolve_report():
 p=Path(os.getenv('DRAFT_PATH','').strip()) if os.getenv('DRAFT_PATH','').strip() else None
 if p:return p if p.exists() else (_ for _ in ()).throw(SystemExit(f'Judge: DRAFT_PATH does not exist: {p}'))
 xs=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda x:x.stat().st_mtime,reverse=True); return xs[0] if xs else None

def load(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8'))
 except Exception:return {}
def has_any(t,terms):return any(k in t for k in terms)
def symbols(t):
 s=set(re.findall(r'\$([A-Z][A-Z0-9]{1,14})\b',t.upper()));s|=set(x.upper() for x in re.findall(r'\b([A-Z][A-Z0-9]{1,14})USDT\b',t.upper()));return s
def normalize_sentence(s):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]','',s.lower())).strip()
_REUSABLE_NORMALIZED={normalize_sentence(s) for s in REUSABLE_DISCLAIMER_SENTENCES}
def normalized_sentences(t):
 out=set()
 for s in re.split(r'[.!?]+',t):
  if len(s.split())>=6:
   n=normalize_sentence(s)
   if n and n not in _REUSABLE_NORMALIZED:out.add(n)
 return out
def recent_similarity(t):
 if not PUBLICATION_LOG.exists():return []
 cur=normalized_sentences(t);matches=[]
 for row in PUBLICATION_LOG.read_text(encoding='utf-8').splitlines()[-12:]:
  try:o=json.loads(row)
  except Exception:continue
  matches.extend(sorted(cur & normalized_sentences(str(o.get('text') or o.get('post') or o.get('content') or ''))))
 return matches[:6]
def specificity(t,f,a=None):
 lo=t.lower();ent=sum(k in lo for k in ENTITY_TERMS);num=len(re.findall(r'\b\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?',t)); names=set(re.findall(r'\b[A-Z][A-Z0-9]{1,9}\b',t))|set(re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b',t));return min(100,35+(15 if symbols(t) else 0)+min(20,len(names)*8)+min(20,ent*3)+min(20,(f+num)*5)+(10 if isinstance(a,(int,float)) and a>=50 else 0))
def research_adv(r,d,t):
 vals=[];sy=symbols(t)
 for obj in (r,d):
  if not isinstance(obj,dict):continue
  for k in ('information_advantage_score','research_information_advantage','originality_score','insight_score','thesis_score','opportunity_score'):
   v=obj.get(k)
   if isinstance(v,(int,float)):vals.append(float(v))
 for g in r.get('potential_gems') or []:
  if not isinstance(g,dict):continue
  if str(g.get('symbol') or '').upper().replace('USDT','') in sy:
   for k in ('information_advantage_score','undercoverage_score','thesis_score','opportunity_score'):
    if isinstance(g.get(k),(int,float)):vals.append(float(g[k]))
 return max(vals) if vals else None
def originality(t,f,attr,mech,inv,a):
 lo=t.lower();sy=symbols(t);names=set(re.findall(r'\b[A-Z][A-Z0-9]{1,9}\b',t))|set(re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b',t));causal=sum(x in lo for x in CAUSAL_OR_RELATIONAL_TERMS);sent=max(1,len([x for x in re.split(r'[.!?]+',t) if x.strip()]));words=re.findall(r"[A-Za-z][A-Za-z'-]+",lo);div=len(set(words))/max(1,len(words));b={'base_editorial_synthesis':40,'asset_specific_research':15 if a is not None and a>=50 else 0,'mechanism':10 if mech else 0,'invalidation_or_confirmation':10 if inv else 0,'source_attribution':5 if attr else 0,'multi_entity_relationship':8 if len(sy)>=2 or len(names)>=3 else 0,'causal_or_contrast_language':7 if causal>=2 else (4 if causal else 0),'concrete_evidence_mix':5 if f>=3 else (3 if f==2 else 0),'lexical_novelty':5 if div>=.58 and sent>=3 else (3 if div>=.50 else 0)};return min(100,sum(b.values())),b
def main():
 p=resolve_report()
 if not p:raise SystemExit('Judge: no draft found')
 data=load(p);draft=data.get('draft') or {};t=str(draft.get('post') or draft.get('text') or '').strip();r=load(RESEARCH);lo=t.lower();lines=[x.strip() for x in t.splitlines() if x.strip()];hook=lines[0].lower() if lines else '';qs=re.findall(r'[^\n.!?]*\?',t);facts=len(re.findall(r'\$[A-Z][A-Z0-9]{1,14}|\b\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?',t));mech=has_any(lo,MECHANISM_TERMS);inv=has_any(lo,INVALIDATION_TERMS);watch=has_any(lo,('watch','next','signal','evidence','confirm','changes my view','what would'));attr=has_any(lo,('source:','reported','according to','announced','data from','according'));generic_q=any(q.strip().lower() in BAD_QUESTIONS for q in qs);generic_hook=hook in GENERIC or len(hook.split())<5;malformed=bool(re.search(r'\bspot volume is\s+\$?[\d,.]+[kmb]?\s+spot volume\b',lo));tpl=[x for x in TEMPLATE_PATTERNS if re.search(x,re.sub(r'\s+',' ',lo),re.I|re.S)];tplphr=sum(x in lo for x in ('reaction matters','bear case:','bull case:','reclaims the range','keep control below support','keep control above support'));rep=recent_similarity(t);evidence=min(100,35+facts*15+(20 if attr else 0));adv=research_adv(r,data,t);spec=specificity(t,facts,adv);reader=min(100,45+(20 if mech else 0)+(15 if inv else 0)+(15 if watch else 0));orig,ob=originality(t,facts,attr,mech,inv,adv);hook_score=max(0,90-(35 if generic_hook else 0)-(25 if len(hook.split())<8 else 0));conversation=max(0,90-(35 if generic_q else 0)) if len(qs)==1 else 20;compliance=100 if not any(x in lo for x in ('guaranteed profit','risk-free','guaranteed return','100% win')) else 0;structure=min(100,50+(10 if len(lines)>=4 else 0)+(15 if mech else 0)+(15 if inv else 0));overall=round(evidence*.20+reader*.20+orig*.15+spec*.15+hook_score*.08+structure*.08+conversation*.04+compliance*.10,1)
 failures=[]
 if not t:failures+=['empty_post']
 if len(qs)!=1:failures+=['must_have_exactly_one_question']
 if generic_q:failures+=['generic_engagement_question']
 if evidence<80:failures+=['evidence_below_80']
 if reader<80:failures+=['reader_value_below_80']
 if spec<80:failures+=['specificity_below_80']
 if orig<78:failures+=['originality_below_78']
 if hook_score<82:failures+=['hook_below_82']
 if not mech:failures+=['missing_mechanism_or_reasoning']
 if not inv:failures+=['missing_invalidation_or_confirmation']
 if overall<85:failures+=['overall_below_85']
 if compliance<100:failures+=['policy_language_failure']
 if malformed:failures+=['malformed_statistics_phrase']
 if tpl:failures+=['repetitive_feed_template']
 if tplphr>=3:failures+=['template_phrase_density']
 if rep:failures+=['repeats_recent_published_sentence']
 result={'version':'1.6','generated_at':datetime.now(timezone.utc).isoformat(),'draft_path':str(p),'publish':not failures,'overall':overall,'scores':{'evidence_density':evidence,'reader_value':reader,'originality':orig,'specificity':spec,'hook':hook_score,'structure':structure,'conversation_quality':conversation,'compliance':compliance},'checks':{'exactly_one_question':len(qs)==1,'mechanism_present':mech,'invalidation_or_confirmation_present':inv,'watch_next_present':watch,'attribution_present':attr,'generic_question':generic_q,'generic_hook':generic_hook,'malformed_statistics_phrase':malformed,'repetitive_feed_template':bool(tpl),'recent_sentence_repetition':bool(rep)},'originality_breakdown':ob,'research_information_advantage':adv,'research_advantage_scope':'asset_specific_when_available','template_artifacts':tpl,'template_phrase_hits':tplphr,'recent_repeated_sentences':rep,'failures':failures,'decision':'PUBLISH' if not failures else 'REGENERATE_OR_WAIT'}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False));
 if failures:raise SystemExit(1)
if __name__=='__main__':main()
