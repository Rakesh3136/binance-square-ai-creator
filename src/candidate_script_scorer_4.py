"""Creator 4.0 candidate-script scorer.
Scores candidate drafts for attention, usefulness, interaction, evidence and originality.
This module never claims access to Binance's private ranking algorithm.
"""
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; OUT=ROOT/'data/live/script_scorecard_4.json'

def load(p):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except:return {}
def words(s):return re.findall(r"\b[\w$%.-]+\b",str(s or ''))
def score(s,fmt):
 t=str(s or '').strip(); low=t.lower(); w=len(words(t)); pts={'attention':0,'usefulness':0,'interaction':0,'evidence':0,'originality':0,'safety':0,'story':0}
 pts['attention']=min(25,(12 if any(x in t[:180] for x in ['🚨','🔥','👀','📊','⚠️','🚀','🆕','💥']) else 4)+(8 if len(t.splitlines())>=3 else 2)+(5 if any(x in low for x in ['why','but','question','next','watch']) else 0))
 pts['usefulness']=min(25,10+(8 if any(x in low for x in ['support','resistance','volume','catalyst','liquidation','target','invalidation','level']) else 0)+(7 if w>=90 else 3 if w>=60 else 0))
 qmarks=t.count('?')
 pts['interaction']=min(22,3+(12 if qmarks==1 else 0)+(7 if any(x in low for x in ['which','choose','a/b','bullish or bearish','breakout or fakeout','chase, fade, or wait','agree or disagree']) else 0))
 pts['evidence']=min(15,7+(8 if any(x in low for x in ['according','data','volume','chart','price','news','reported']) else 0))
 pts['originality']=min(10,5+(5 if not low.startswith(('bitcoin is','the crypto market','today','fresh check','quick market check')) else 0))
 pts['story']=min(12,4+(4 if any(x in low for x in ['because','why now','catalyst','instead','but','while','the catch','here’s the twist','here is the twist']) else 0)+(4 if w>=80 else 0))
 risky=any(x in low for x in ['guaranteed','risk-free','100% certain','will 10x','will 20x','easy profit'])
 pts['safety']=0 if risky else 5
 if qmarks!=1: pts['interaction']=max(0,pts['interaction']-6)
 total=min(100,sum(pts.values()))
 return {'total':total,'breakdown':pts,'risk_flag':risky,'word_count':w,'question_count':qmarks}

def main():
 p=load(PREFLIGHT); brief=p.get('script_director_4') or {}; fmt=brief.get('format','')
 # Candidate scripts may be injected by the writer in this field. Keep hook candidates as fallback candidates.
 candidates=p.get('candidate_scripts_4') or []
 if not candidates:
  candidates=[{'hook':h,'script':h+'\n\nUse verified current data and explain what matters next.\n\nWhat are you watching?'} for h in brief.get('hook_candidates',[])]
 scored=[]
 for i,c in enumerate(candidates):
  txt=c.get('script') if isinstance(c,dict) else str(c); r=score(txt,fmt); scored.append({'index':i,'script':txt,**r})
 scored.sort(key=lambda x:x['total'],reverse=True)
 result={'version':'4.4','format':fmt,'candidate_count':len(scored),'winner':scored[0] if scored else None,'candidates':scored,'minimum_publish_score':70,'policy':['Never optimize for clicks alone.','Reject unsupported certainty and fabricated claims.','Prefer evidence-rich interaction over empty engagement bait.','Use performance data as an experiment, not as knowledge of a private platform algorithm.']}
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); p['script_scorecard_4']=result; PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'status':'OK','winner_score':scored[0]['total'] if scored else 0,'candidates':len(scored)},indent=2))
if __name__=='__main__':main()
