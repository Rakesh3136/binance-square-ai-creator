"""Creator 4.1 human editorial layer.

Keeps researched facts while producing a stronger mobile-first Binance Square
post with varied hooks, evidence, chart-derived levels and one real question.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path

NEWS=Path('data/live/news_snapshot.json')
OUT=Path('data/live/editorial_polish.json')
STYLE={
 'NEWS':('📰',['Does the chart confirm the headline?','Bullish reaction or headline fade?']),
 'CHART':('📊',['Breakout or fakeout?','Which level would you watch first?']),
 'VOLUME':('🔥',['Is volume confirming the move?','Would you wait for follow-through?']),
 'CHOICE':('👀',['Chase, pullback, or wait?','What would change your view?']),
 'BREAKOUT':('⚡',['Breakout or fakeout?','Would you wait for another candle?']),
 'DATA':('🔎',['Did you notice this signal?','Does this data change your read?']),
 'UPDATE':('🔄',['Did this change your read?','What signal would you watch next?'])}

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

def fresh_news():
    data=load(NEWS,{})
    try: age=(datetime.now(timezone.utc)-datetime.fromisoformat(str(data.get('generated_at','')).replace('Z','+00:00'))).total_seconds()
    except Exception:return {}
    if age<0 or age>48*3600:return {}
    for a in data.get('articles') or []:
        if isinstance(a,dict):
            title=clean(a.get('title') or a.get('headline'))
            if title:return {'source':clean(a.get('source') or ''),'title':title[:220]}
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
    style=choose_style(draft); emoji,questions=STYLE[style]; question=questions[datetime.now(timezone.utc).day%len(questions)]
    lines=[clean(x) for x in original.splitlines() if clean(x) and '?' not in x]
    banned={'key levels:','key scenario levels:','fresh check:','quick market check:','this is the crypto story i’m watching right now:','this is the crypto story i\'m watching right now:'}
    lines=[x for x in lines if x.lower() not in banned]
    evidence=[]
    for line in lines:
        if line.lower().startswith(('$'+symbol.lower(),'current price')):continue
        if len(line)>=18:evidence.append(line)
    evidence=evidence[:5]
    if not evidence:evidence=[f'${symbol} is active on the verified market snapshot, so the next reaction matters more than the first spike.']
    hooks={
      'NEWS':f'{emoji} The headline is only half the story. ${symbol} has to confirm it on price.',
      'CHART':f'{emoji} The ${symbol} chart is at a level worth watching — here is what matters next.',
      'VOLUME':f'{emoji} Price got attention. The participation behind ${symbol} is what I’m watching.',
      'CHOICE':f'{emoji} I’m not chasing the first candle on ${symbol}. I want to see what happens next.',
      'BREAKOUT':f'{emoji} ${symbol} is testing a decisive zone. This is where breakout and fakeout separate.',
      'DATA':f'{emoji} One number on ${symbol} matters more than the headline percentage.',
      'UPDATE':f'{emoji} Update on ${symbol}: the market gave us another clue.'}
    body=hooks[style]+'\n\n'+'\n'.join(evidence)
    lv=chart_levels(draft,data)
    if lv:
        p=[]
        for key,label in [('current_price','price'),('support','support'),('resistance','resistance'),('tp1','TP1'),('target','target'),('invalidation','invalidation')]:
            if lv.get(key) is not None:p.append(f'{label} ${fmt(lv[key])}')
        if p:body+='\n\n📍 '+' • '.join(p)
        direction=str(lv.get('direction') or '').lower()
        if 'long' in direction:body+='\nBull case: a sustained move above resistance strengthens the upside scenario; losing support weakens it.'
        elif 'short' in direction:body+='\nBear case: a failed reclaim keeps downside risk active; invalidation is the level to watch.'
        body+='\nThese are chart-derived scenarios, not guarantees.'
    news=fresh_news()
    if style=='NEWS' and news:body+='\n\n📰 '+((news['source']+': ') if news.get('source') else '')+news['title']
    if 'level' in question.lower():question=question[:-1]+f' on ${symbol}?'
    body=re.sub(r'\?','.',body).rstrip(' .')
    text=(body+'\n\n'+question)[:900]
    if text.count('?')!=1:text=re.sub(r'\?','.',text).rstrip('.')+'\n\n'+question
    return text,style,emoji,question,news

def main():
    path=Path(os.environ.get('DRAFT_PATH',''))
    if not path.exists():raise SystemExit('DRAFT_PATH is missing')
    data=load(path,{ }); draft=data.setdefault('draft',{})
    text,style,emoji,question,news=make_post(draft,data)
    draft.update({'post':text,'text':text,'editorial_style':style.lower(),'human_editor':{'status':'POLISHED','version':'human-editor-v6','style':style,'emoji':emoji,'question':question,'fresh_news_used':bool(news),'question_count':1,'fact_policy':'preserve supplied evidence only'}})
    data['editorial_style_version']='human-editor-v6'; data['news_context']=news
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'status':'HUMAN_EDITOR_APPLIED','version':'human-editor-v6','style':style,'characters':len(text),'question':question,'fresh_news':bool(news)},indent=2,ensure_ascii=False),encoding='utf-8')
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'HUMAN_EDITOR_APPLIED','version':'human-editor-v6','characters':len(text),'style':style,'question':question,'fresh_news':bool(news)}))
if __name__=='__main__':main()
