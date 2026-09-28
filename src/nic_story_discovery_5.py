"""NIC Story Discovery 5.0 — choose the information product before drafting."""
from __future__ import annotations
import json, re
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/nic_story_discovery.json'

def load(name):
    p=ROOT/'data/live'/name
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}

def txt(x): return str(x or '').strip()

def facts(research, strategy, context):
    vals=[]
    for src,label in [(research,'research'),(strategy,'strategy'),(context,'context')]:
        for k in ('information_advantage','why_now','mechanism','primary_observation','thesis','narrative','summary','key_finding'):
            v=src.get(k)
            if txt(v): vals.append({'source':label,'field':k,'text':txt(v)[:500]})
    return vals

def main():
    research=load('original_research.json'); strategy=load('agent_strategy.json'); context=load('publication_context.json'); os=load('nic_monetization_contract.json'); portfolio=load('content_portfolio_plan.json')
    sym=txt(context.get('symbol') or strategy.get('symbol')).upper().replace('USDT','').replace('$','')
    evidence=facts(research,strategy,context)
    news=load('news_snapshot.json').get('articles') or []
    news=[a for a in news if isinstance(a,dict) and (a.get('title') or a.get('summary'))][:12]
    observations=[]
    for e in evidence: observations.append(e)
    for a in news[:5]: observations.append({'source':'news','field':'event','text':txt(a.get('title') or a.get('summary'))[:500]})
    lanes=[('data_investigation','surprise_in_the_data'),('breaking_news','verified_event'),('world_macro','macro_transmission'),('research_lesson','evidence_finding'),('contrarian_thesis','alternative_explanation'),('follow_up','changed_since_last'),('market_setup','conditional_setup')]
    if not observations: raise SystemExit('Story discovery: insufficient evidence')
    # Deterministic discovery: prefer information-rich evidence and avoid defaulting to setup.
    scored=[]
    for lane,kind in lanes:
        score=0
        if lane==str(os.get('content_lane') or ''): score+=2
        if lane!='market_setup': score+=1
        if kind=='verified_event' and news: score+=3
        if kind=='macro_transmission' and any(w in ' '.join(x['text'].lower() for x in observations) for w in ('fed','rates','inflation','dollar','liquidity','macro')): score+=3
        if kind=='evidence_finding' and research: score+=3
        if kind=='surprise_in_the_data' and len(observations)>=3: score+=3
        if kind=='alternative_explanation': score+=2
        if kind=='changed_since_last': score+=2
        if kind=='conditional_setup' and strategy.get('prediction_ready'): score+=2
        scored.append({'lane':lane,'score':score})
    scored.sort(key=lambda x:(x['score'],x['lane']),reverse=True)
    selected=scored[0]
    discovery={'version':'5.0','status':'DISCOVERED','asset':sym,'selected_lane':selected['lane'],'story_kind':selected['lane'],'story_question':'What is the most useful verified insight here that a reader would not get from a routine price-level post?','evidence_count':len(observations),'evidence':observations[:10],'ranked_story_types':scored,'selected_treatment':os.get('content_lane') or portfolio.get('selected_treatment'),'discovery_rule':'information-first; technical_setup is eligible only when the supplied evidence makes the setup itself the story','created_at':datetime.now(timezone.utc).isoformat()}
    OUT.write_text(json.dumps(discovery,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); print(json.dumps(discovery,indent=2))
if __name__=='__main__': main()
