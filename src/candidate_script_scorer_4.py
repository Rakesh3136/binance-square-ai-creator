"""Creator 5.1 candidate-script scorer.
Scores candidate drafts for attention, usefulness, interaction, evidence, originality and story completeness.
This module never claims access to Binance's private ranking algorithm.
"""
from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json'; CONTEXT=ROOT/'data/live/publication_context.json'; OUT=ROOT/'data/live/script_scorecard_4.json'
def load(p):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except:return {}
def words(s):return re.findall(r"\b[\w$%.-]+\b",str(s or ''))
def score(s,fmt,context):
    t=str(s or '').strip(); low=t.lower(); w=len(words(t)); pts={'attention':0,'usefulness':0,'interaction':0,'evidence':0,'originality':0,'safety':0,'story':0}
    pts['attention']=min(25,(12 if any(x in t[:180] for x in ['🚨','🔥','👀','📊','⚠️','🚀','🆕','💥']) else 4)+(8 if len(t.splitlines())>=3 else 2)+(5 if any(x in low for x in ['why','but','question','next','watch']) else 0))
    pts['usefulness']=min(25,10+(8 if any(x in low for x in ['support','resistance','volume','catalyst','liquidation','target','invalidation','level','evidence']) else 0)+(7 if w>=90 else 3 if w>=60 else 0))
    qmarks=t.count('?')
    pts['interaction']=min(22,3+(12 if qmarks==1 else 0)+(7 if any(x in low for x in ['which','choose','a/b','bullish or bearish','breakout or fakeout','chase, fade, or wait','agree or disagree']) else 0))
    pts['evidence']=min(15,7+(8 if any(x in low for x in ['according','data','volume','chart','price','news','reported','source']) else 0))
    pts['originality']=min(10,5+(5 if not low.startswith(('bitcoin is','the crypto market','today','fresh check','quick market check')) else 0))
    pts['story']=min(12,4+(4 if any(x in low for x in ['because','why now','catalyst','instead','but','while','the catch','here’s the twist','here is the twist']) else 0)+(4 if w>=80 else 0))
    risky=any(x in low for x in ['guaranteed','risk-free','100% certain','will 10x','will 20x','easy profit'])
    pts['safety']=0 if risky else 5
    if qmarks!=1: pts['interaction']=max(0,pts['interaction']-6)
    total=min(100,sum(pts.values()))
    return {'total':total,'breakdown':pts,'risk_flag':risky,'word_count':w,'question_count':qmarks}
def completeness(s,context):
    t=str(s or '').strip(); low=t.lower(); reasons=[]
    symbol=str(context.get('symbol') or '').upper()
    if symbol and not re.search(r'\$'+re.escape(symbol)+r'\b',t,re.I): reasons.append('missing_primary_cashtag')
    if len(words(t))<45: reasons.append('too_short_to_be_a_finished_story')
    title=str(context.get('news_title') or '').strip()
    if title and not any(x in low for x in [w.lower() for w in re.findall(r"[A-Za-z0-9$%.-]{4,}",title)[:3]]): reasons.append('news_story_not_grounded_in_selected_event')
    if title and not any(x in low for x in ['source','reported','according','said','announced','per ']): reasons.append('news_source_context_missing')
    if str(context.get('story_engine','')).upper() in {'TECHNICAL_SETUP','DATA_SURPRISE','MOMENTUM_DISCOVERY'} and not any(x in low for x in ['price','volume','chart','support','resistance','range','data','breakout']): reasons.append('market_evidence_missing')
    if t.count('?')!=1: reasons.append('must_have_exactly_one_question')
    return reasons
def main():
    p=load(PREFLIGHT); ctx=load(CONTEXT); brief=p.get('script_director_4') or {}; fmt=brief.get('format',''); candidates=p.get('candidate_scripts_4') or []
    if not candidates:
        candidates=[{'hook':h,'script':h+'\n\nUse verified current data and explain what matters next.\n\nWhat are you watching?'} for h in brief.get('hook_candidates',[])]
    scored=[]
    for i,c in enumerate(candidates):
        txt=c.get('script') if isinstance(c,dict) else str(c); r=score(txt,fmt,ctx); missing=completeness(txt,ctx); r['completeness_failures']=missing; r['eligible']=not missing and not r['risk_flag']
        if missing: r['total']=max(0,r['total']-25)
        scored.append({'index':i,'script':txt,**r})
    scored.sort(key=lambda x:(x['eligible'],x['total']),reverse=True)
    winner=next((x for x in scored if x['eligible']),None)
    result={'version':'5.1','format':fmt,'story_engine':ctx.get('story_engine',''),'candidate_count':len(scored),'winner':winner,'candidates':scored,'minimum_publish_score':70,'evidence_gate':True,'policy':['Never optimize for clicks alone.','Reject unsupported certainty and fabricated claims.','Reject instruction-like placeholder drafts that are too short to be finished stories.','Require the frozen primary cashtag and exactly one specific question.','When news is selected, require grounding in the selected event and source context.','Use performance data as an experiment, not as knowledge of a private platform algorithm.']}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); p['script_scorecard_4']=result; PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','version':'5.1','winner_score':winner['total'] if winner else 0,'candidates':len(scored),'winner_eligible':bool(winner)},indent=2))
if __name__=='__main__':main()
