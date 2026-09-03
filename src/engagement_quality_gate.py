"""Pre-publication gate for interaction quality and visual storytelling.
Mode-aware: short image posts stay mobile-first, while article mode can carry deeper news analysis.
"""
from __future__ import annotations
import json,re
from pathlib import Path

OUT=Path('data/live/engagement_gate.json')

BAD_PATTERNS=[r'what do you think\??$',r'key takeaway',r'notable factor',r'clear shift',r'overhead liquidity',r'market participants']
ARTICLE_MAX=2200
POST_MAX=750

def evaluate(post, visual=None):
    text=str(post or '').strip()
    visual=visual or {}
    mode=str(visual.get('publication_mode') or 'image').lower()
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    questions=text.count('?')
    score=100
    reasons=[]

    if mode=='article':
        if len(text)>ARTICLE_MAX:
            score-=20; reasons.append('article_too_long')
        if len(lines)>18:
            score-=10; reasons.append('article_too_many_lines')
    else:
        if len(text)>POST_MAX:
            score-=20; reasons.append('too_long')
        if len(text)>550:
            score-=10; reasons.append('long_for_mobile')
        if len(lines)>10:
            score-=10; reasons.append('too_many_lines')

    if questions!=1:
        score-=18; reasons.append('must_have_exactly_one_question')
    if any(re.search(p,text,re.I) for p in BAD_PATTERNS):
        score-=15; reasons.append('analyst_filler')
    if re.search(r'\b(TP|SL|take profit|stop loss|entry)\b',text,re.I):
        score-=8; reasons.append('signal_heavy')
    if visual.get('use_visual') is True and visual.get('type')=='none':
        score-=20; reasons.append('visual_requested_but_missing')
    if not any(x in text.lower() for x in ['breakout','fakeout','hold','retest','choose','watch','why','which','bullish','bearish','wait','catalyst','news','bank','launch']):
        score-=5; reasons.append('weak_conversation_trigger')
    return {'score':max(0,score),'publish':score>=72,'reasons':reasons,'mode':mode,'character_count':len(text)}

def main():
    import sys
    payload=json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    result=evaluate(payload.get('post',''),payload.get('visual_plan'))
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
