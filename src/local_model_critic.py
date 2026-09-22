"""Optional local multi-model critic.

Uses Ollama when available, with Qwen3 and Gemma3 as independent critics.
No API key is required. The critic never creates or changes market levels;
it reviews the frozen contract and existing evidence only.
"""
from __future__ import annotations
import json, os, urllib.request
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data/live'; OUT=LIVE/'local_model_critic.json'
HOST=os.getenv('OLLAMA_HOST','http://127.0.0.1:11434').rstrip('/')
MODELS=[x.strip() for x in os.getenv('LOCAL_CRITIC_MODELS','qwen3:1.7b,gemma3:1b').split(',') if x.strip()]

def load(name):
    try:
        x=json.loads((LIVE/name).read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception: return {}

def ask(model,prompt):
    payload=json.dumps({'model':model,'stream':False,'messages':[{'role':'system','content':'You are an independent crypto-trade critic. Review only supplied evidence. Never invent market data, prices, levels, news or guarantees. Return compact JSON with decision PASS, REVIEW or BLOCK, confidence 0-1, and reasons.'},{'role':'user','content':prompt}]}).encode()
    req=urllib.request.Request(HOST+'/api/chat',data=payload,headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=45) as r: return json.loads(r.read().decode()).get('message',{}).get('content','')

def main():
    frozen=load('authoritative_opportunity.json'); signal=load('signal_first_routing.json'); adv=load('adversarial_decision.json'); cf=load('counterfactual_analysis.json'); research=load('research_intelligence.json')
    prompt=json.dumps({'frozen':frozen,'signal':signal,'adversarial':adv,'counterfactual':cf,'research_summary':{k:research.get(k) for k in ('status','decision','reason','confidence') if k in research}},ensure_ascii=False)[:18000]
    votes=[]
    for model in MODELS:
        try:
            raw=ask(model,prompt)
            try:
                parsed=json.loads(raw)
            except Exception:
                parsed={'decision':'REVIEW','confidence':0.0,'reasons':[raw[:500]],'parse_error':True}
            decision=str(parsed.get('decision') or 'REVIEW').upper()
            if decision not in {'PASS','REVIEW','BLOCK'}: decision='REVIEW'
            votes.append({'model':model,'decision':decision,'confidence':float(parsed.get('confidence') or 0),'reasons':parsed.get('reasons') or parsed.get('reason') or []})
        except Exception as e:
            votes.append({'model':model,'decision':'UNAVAILABLE','confidence':0,'reason':str(e)[:300]})
    usable=[v for v in votes if v['decision'] in {'PASS','REVIEW','BLOCK'}]
    blocks=sum(v['decision']=='BLOCK' for v in usable); reviews=sum(v['decision']=='REVIEW' for v in usable); passes=sum(v['decision']=='PASS' for v in usable)
    decision='REVIEW' if blocks or reviews else ('PASS' if passes else 'UNAVAILABLE')
    result={'version':'1.0','generated_at':datetime.now(timezone.utc).isoformat(),'symbol':frozen.get('symbol'),'decision':decision,'publish_authorized':decision=='PASS','votes':votes,'available_models':len(usable),'disagreement':len({v['decision'] for v in usable})>1,'policy':'Local models are independent critics only. Deterministic Binance evidence and the frozen contract remain authoritative.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0
if __name__=='__main__': raise SystemExit(main())
