"""Creator 4.0 candidate generation and rewrite stage.
Uses the existing Gemini multi-agent writer as the generation backend while
forcing story-specific diversity and a final scorecard pass.
"""
from __future__ import annotations
import json, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'

def load(p):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except:return {}

def main():
 p=load(PREFLIGHT); d=p.get('content_director_4') or {}; s=p.get('script_director_4') or {}
 fmt=d.get('recommended_format','TOP MOVERS'); sym=s.get('primary_symbol') or (d.get('primary_story') or {}).get('symbol','')
 hooks=s.get('hook_candidates') or []
 prompt={
  'version':'4.0','symbol':sym,'format':fmt,
  'instruction':f'''You are the Creator 4.0 senior crypto editor. Story format: {fmt}. Primary asset: {sym}.\nGenerate 5 genuinely different COMPLETE Binance Square post candidates, not 5 hooks. Candidate styles must vary: breaking/newsroom, analytical, conversational/community, contrarian/counterpoint, and concise high-energy. Every candidate must be grounded in the supplied verified evidence. Use the TradingView chart for technical claims. Do not invent news, targets, volume, support/resistance, or creator calls. If a target or stop/invalidation is not supported by current data, omit it. Never promise profit or say a coin will definitely 10x/20x. Each candidate should have one natural question. Then select the strongest candidate and rewrite it once for mobile readability, factual precision and originality. Hook candidates to consider: {json.dumps(hooks,ensure_ascii=False)}''',
  'selection_criteria':['stop-scroll strength','specificity','evidence density','usefulness','natural interaction','originality','mobile readability','risk-aware language']
 }
 p['candidate_generation_4']=prompt; PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'status':'OK','format':fmt,'symbol':sym,'candidate_count':5},indent=2))
if __name__=='__main__':main()
