"""Creator 4.2 final human editorial layer.

Preserves the AI's researched angle, enforces mobile readability and one question,
and prevents the final editor from collapsing every post into the same template.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path

NEWS=Path('data/live/news_snapshot.json')
OUT=Path('data/live/editorial_polish.json')

STYLE_QUESTIONS={
 'NEWS':['Is the market confirming this catalyst, or fading it?','Does this headline change your crypto outlook today?','Bullish repricing or temporary headline noise?','Would you trade the headline or wait for price confirmation?'],
 'CHART':['Breakout or fakeout?','Which level would you watch first?','Would you wait for confirmation on the next candle?'],
 'VOLUME':['Is volume confirming the move?','Would you wait for follow-through?'],
 'CHOICE':['Chase, pullback, or wait?','What would change your view?'],
 'BREAKOUT':['Breakout or fakeout?','Would you wait for another candle?'],
 'DATA':['Did you notice this signal?','Does this data change your read?'],
 'UPDATE':['Did this change your read?','What signal would you watch next?']}
NEWS_HOOKS=[
 '📰 Fresh headline, real market reaction: ${symbol} is where I’m looking next.',
 '🚨 The news just changed the backdrop. Now watch how ${symbol} responds.',
 'The headline is interesting. The ${symbol} reaction is what makes it tradeable.',
 '⚡ New information is hitting crypto — and ${symbol} is giving us the first clue.',
 'One fresh crypto headline is getting attention. Here is why ${symbol} matters now.'
]


def load(path, default=None):
    if default is None: default={}
    if not path.exists(): return default
    try:
        x=json.loads(path.read_text(encoding='utf-8'))
        return x if isinstance(x,type(default)) else default
    except Exception:return default

def clean(x):return re.sub(r'[ \t]+',' ',str(x or '')).strip()

def get_symbol(draft,text):
    for v in (draft.get('symbol'),draft.get('primary_symbol')):
        s=re.sub(r'USDT$','',str(v or '').upper().replace('$','').strip())
        if re.fullmatch(r'[A-Z0-9]{2,15}',s):return s
    m=re.search(r'\$([A-Z][A-Z0-9]{1,14})\b',text.upper())
    return m.group(1) if m else ''

def choose_style(draft):
    raw=str(draft.get('experiment_format') or draft.get('editorial_style') or '').upper()
    if 'NEWS' in raw or 'HEADLINE' in raw:return 'NEWS'
    if 'VOLUME' in raw:return 'VOLUME'
    if 'BREAKOUT' in raw or 'FAKEOUT' in raw:return 'BREAKOUT'
    if 'DATA' in raw:return 'DATA'
    if 'UPDATE' in raw or 'FOLLOW' in raw:return 'UPDATE'
    if 'CHOICE' in raw:return 'CHOICE'
    return 'CHART' if ('CHART' in raw or draft.get('visual_plan')) else 'CHOICE'

def fresh_news(selected=None):
    data=load(NEWS,{})
    articles=data.get('articles') or []
    if not articles:return {}
    selected_title=clean((selected or {}).get('news_title'))
    if selected_title:
        for a in articles:
            if isinstance(a,dict) and clean(a.get('title') or a.get('headline'))==selected_title:
                return {'source':clean(a.get('source') or ''),'title':selected_title[:240],'url':clean(a.get('url') or ''),'published_at':clean(a.get('published_at') or '')}
    for a in articles:
        if isinstance(a,dict):
            title=clean(a.get('title') or a.get('headline'))
            if title:return {'source':clean(a.get('source') or ''),'title':title[:240],'url':clean(a.get('url') or ''),'published_at':clean(a.get('published_at') or '')}
    return {}

def fmt(v):
    try:return f'{float(v):.8g}'
    except Exception:return str(v)

def chart_levels(draft,data):
    src=draft.get('technical_levels') or (data.get('research') or {}).get('chart_levels') or {}
    return src if isinstance(src,dict) else {}

def make_post(draft,data):
    original=clean(draft.get('post') or draft.get('text') or '')
    if not original:raise SystemExit('Draft has no post text')
    symbol=get_symbol(draft,original)
    if not symbol:raise SystemExit('Editorial layer: primary symbol missing')
    style=choose_style(draft); selected=data.get('selected_editorial_lane') or data.get('selected_opportunity') or {}
    news=fresh_news(selected)
    lines=[clean(x) for x in original.splitlines() if clean(x)]
    lines=[x for x in lines if x.lower() not in {'key levels:','key scenario levels:','fresh check:','quick market check:','this is the crypto story i’m watching right now:','this is the crypto story i\'m watching right now:'}]

    if style=='NEWS' and news:
        # The final editor must keep the actual news event at the top. It may polish
        # the hook, but it must never replace a news post with a generic price recap.
        raw_hook=lines[0] if lines else ''
        generic=('headline is only half the story' in raw_hook.lower() or 'watching right now' in raw_hook.lower() or len(raw_hook)<18)
        if generic:
            idx=(sum(ord(c) for c in (symbol+news['title'])) % len(NEWS_HOOKS))
            hook=NEWS_HOOKS[idx].replace('${symbol}',f'${symbol}')
        else:
            hook=raw_hook
        event=f"📰 {news['source']}: {news['title']}" if news.get('source') else f"📰 {news['title']}"
        body_lines=[hook,event]
        # Keep useful AI evidence/interpretation, but do not duplicate the raw headline.
        for line in lines[1:]:
            if news['title'].lower() not in line.lower() and len(line)>=18:
                body_lines.append(line)
        body_lines=body_lines[:7]
    else:
        hook=lines[0] if lines else f'${symbol} is giving the market a signal worth watching.'
        body_lines=[hook]
        body_lines.extend([x for x in lines[1:] if len(x)>=18][:5])

    lv=chart_levels(draft,data)
    if lv:
        p=[]
        for key,label in [('current_price','price'),('support','support'),('resistance','resistance'),('tp1','TP1'),('target','target'),('invalidation','invalidation')]:
            if lv.get(key) is not None:p.append(f'{label} ${fmt(lv[key])}')
        if p:body_lines.append('📍 '+' • '.join(p))
        direction=str(lv.get('direction') or '').lower()
        if 'long' in direction:body_lines.append('Bull case: a sustained move above resistance strengthens the upside scenario; losing support weakens it.')
        elif 'short' in direction:body_lines.append('Bear case: a failed reclaim keeps downside risk active; invalidation is the level to watch.')
        body_lines.append('These are chart-derived scenarios, not guarantees.')

    # Exactly one question, selected from a small rotating family rather than a fixed daily line.
    questions=STYLE_QUESTIONS[style]
    qidx=(sum(ord(c) for c in (symbol+style+datetime.now(timezone.utc).strftime('%Y-%m-%d-%H'))) % len(questions))
    question=questions[qidx]
    if '$' not in question and style=='NEWS' and symbol: question=question.rstrip('?')+f' for ${symbol}?'
    body='\n\n'.join(body_lines)
    body=re.sub(r'\?','.',body).strip(' .')
    text=(body+'\n\n'+question)[:900]
    if text.count('?')!=1:text=re.sub(r'\?','.',text).rstrip('.')+'\n\n'+question
    return text,style,question,news

def main():
    path=Path(os.environ.get('DRAFT_PATH',''))
    if not path.exists():raise SystemExit('DRAFT_PATH is missing')
    data=load(path,{ }); draft=data.setdefault('draft',{})
    text,style,question,news=make_post(draft,data)
    draft.update({'post':text,'text':text,'editorial_style':style.lower(),'human_editor':{'status':'POLISHED','version':'human-editor-v7','style':style,'question':question,'fresh_news_used':bool(news),'question_count':1,'fact_policy':'preserve supplied evidence only'}})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'status':'HUMAN_EDITOR_APPLIED','version':'human-editor-v7','style':style,'characters':len(text),'question':question,'fresh_news':bool(news)},indent=2,ensure_ascii=False),encoding='utf-8')
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'HUMAN_EDITOR_APPLIED','version':'human-editor-v7','characters':len(text),'style':style,'question':question,'fresh_news':bool(news)}))
if __name__=='__main__':main()
