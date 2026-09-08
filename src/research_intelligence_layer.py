"""Research Intelligence Layer 1.0.
Turns scout candidates into structured asymmetric-opportunity and failure-risk dossiers.
This is a research/decision-support layer, not a price-prediction or investment-advice engine.
"""
from __future__ import annotations
import json, math, re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'data/live/original_research.json'
MARKET=ROOT/'data/live/market_snapshot.json'
NEWS=ROOT/'data/live/news_snapshot.json'
LEDGER=ROOT/'data/intelligence/thesis_ledger.json'
OUT=ROOT/'data/live/research_intelligence.json'
REPORT=ROOT/'data/intelligence/research_intelligence_report.json'

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def num(v):
    try:return float(v)
    except:return 0.0

def clamp(v):return round(max(0,min(100,v)),2)

def sym(v):return re.sub(r'USDT$','',str(v or '').upper().replace('$','').strip())

def mcap(r):
    for k in ('market_cap','market_cap_usdt','marketCap'):
        if num(r.get(k))>0:return num(r[k])
    return 0.0

def supply(r):
    for k in ('circulating_supply','circulatingSupply'):
        if num(r.get(k))>0:return num(r[k])
    return 0.0

def dossier(r, news, ledger):
    s=sym(r.get('symbol')); price=num(r.get('price')); current=mcap(r); circ=supply(r)
    move=num(r.get('move_pct')); vol=num(r.get('quote_volume_usdt')); risk=num(r.get('risk_red_flag_score')); ev=num(r.get('evidence_score')); liq=num(r.get('liquidity_score')); anomaly=num(r.get('market_anomaly_score'))
    # A feasibility calculation is deliberately conditional: without market cap we do not fabricate it.
    target_caps={"10x":current*10 if current else 0,"50x":current*50 if current else 0,"100x":current*100 if current else 0}
    valuation_status='CALCULABLE' if current>0 else 'INSUFFICIENT_MARKET_CAP_DATA'
    signal=clamp(0.30*anomaly+0.25*ev+0.20*liq+0.15*(100-risk)+0.10*min(100,abs(move)*3))
    survival=clamp(100-(0.45*risk+0.20*(100-liq)+0.15*min(100,abs(move)*2)+0.20*(100-ev)))
    attention_gap=clamp(100-min(100,ev*0.5+liq*0.2+anomaly*0.3))
    prior=ledger.get(s,{}) if isinstance(ledger.get(s),dict) else {}
    return {
      'symbol':s,'price':price,'current_market_cap':current,'circulating_supply':circ,
      '10x_target_market_cap':target_caps['10x'],'50x_target_market_cap':target_caps['50x'],'100x_target_market_cap':target_caps['100x'],
      'valuation_status':valuation_status,
      'asymmetric_opportunity_score':signal,'survival_score':survival,'attention_gap_score':attention_gap,
      'risk_score':risk,'evidence_score':ev,'liquidity_score':liq,'anomaly_score':anomaly,
      'research_thesis': 'Potential asymmetric opportunity only if fundamental adoption, token economics and a credible catalyst are verified.',
      'failure_thesis':'Structural risk rises if liquidity, usage, security, governance, token supply or treasury conditions deteriorate.',
      'bull_case_checks':['measurable adoption accelerates','unit economics/fees improve where applicable','catalyst is verified by a primary source','valuation remains reasonable versus comparables','token supply pressure remains manageable'],
      'base_case_checks':['adoption grows without a material valuation expansion','tokenomics remain stable','liquidity remains adequate'],
      'bear_case_checks':['adoption stalls or reverses','large unlock/concentration creates persistent selling pressure','security/governance incident occurs','liquidity materially deteriorates','key catalyst fails'],
      'invalidation_conditions':['fundamental usage fails to improve','material adverse security/governance evidence','unfavourable dilution/unlock data','liquidity deterioration that prevents healthy market participation','primary-source evidence contradicts the thesis'],
      'deep_research_required':['primary project documentation','tokenomics and unlock schedule','holder concentration','product usage/adoption','fees/revenue or equivalent measurable economic activity','security/audits/incidents','developer/governance activity','treasury/runway when publicly disclosed','confirmed catalysts','comparable valuation','counter-evidence'],
      'epistemic_policy':'Label every statement VERIFIED_FACT, DERIVED_OBSERVATION, INTERPRETATION, HYPOTHESIS or UNKNOWN.',
      'prior_thesis':prior.get('thesis') if prior else None,
      'news_context_count':sum(1 for a in news.get('articles',[]) if s and s in [sym(v) for v in (a.get('symbols') or [])]),
      'publication_recommendation':'RESEARCH_MORE' if ev<80 else ('RISK_WATCH' if risk>=60 else ('OPPORTUNITY_WATCH' if signal>=65 else 'MONITOR'))
    }

def main():
    src=load(INPUT); news=load(NEWS); ledger=load(LEDGER); candidates=(src.get('potential_gems') or [])+(src.get('potential_risks') or [])
    unique={sym(r.get('symbol')):r for r in candidates if sym(r.get('symbol'))}
    ds=[dossier(r,news,ledger) for r in unique.values()]
    opportunities=sorted(ds,key=lambda x:(x['asymmetric_opportunity_score'],x['attention_gap_score']),reverse=True)[:10]
    risks=sorted(ds,key=lambda x:(x['risk_score'],100-x['survival_score']),reverse=True)[:10]
    now=datetime.now(timezone.utc).isoformat()
    state={'version':'1.0','generated_at':now,'status':'READY' if ds else 'NO_CANDIDATES','principle':'Research first; publish only verified, differentiated findings. Never promise returns or declare bankruptcy without authoritative evidence.','candidates':ds,'opportunity_watchlist':opportunities,'risk_watchlist':risks,'research_queue':[x['symbol'] for x in sorted(ds,key=lambda x:x['publication_recommendation']=='RESEARCH_MORE',reverse=True)[:10]],'report_types':['asymmetric opportunity dossier','100x feasibility audit','survival risk audit','tokenomics/dilution audit','narrative-vs-data review','catalyst verification','thesis change report','post-mortem'], 'publication_rule':'A candidate must survive evidence verification, adversarial review, originality review and the elite pre-publication judge before publication.'}
    OUT.parent.mkdir(parents=True,exist_ok=True);REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    REPORT.write_text(json.dumps({'module':'research_intelligence_layer','generated_at':now,'opportunities':[x['symbol'] for x in opportunities],'risks':[x['symbol'] for x in risks],'research_queue':state['research_queue']},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    # Persist a compact thesis ledger so future cycles can compare state without trusting prose history.
    ledger_out=dict(ledger) if isinstance(ledger,dict) else {}
    for d in ds:
        ledger_out[d['symbol']]={'updated_at':now,'last_research_recommendation':d['publication_recommendation'],'last_opportunity_score':d['asymmetric_opportunity_score'],'last_risk_score':d['risk_score'],'thesis':d['research_thesis'],'invalidation_conditions':d['invalidation_conditions']}
    LEDGER.parent.mkdir(parents=True,exist_ok=True);LEDGER.write_text(json.dumps(ledger_out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':state['status'],'opportunity_watchlist':[x['symbol'] for x in opportunities[:5]],'risk_watchlist':[x['symbol'] for x in risks[:5]],'research_queue':state['research_queue'][:5]},indent=2))
if __name__=='__main__':main()
