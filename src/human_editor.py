"""Creator 4.3 final editorial layer: preserve the researched story while improving readability, variety and signal clarity."""
from __future__ import annotations
import json,os,re
from datetime import datetime,timezone
from pathlib import Path
NEWS=Path('data/live/news_snapshot.json');OUT=Path('data/live/editorial_polish.json')
STYLE_QUESTIONS={'NEWS':['Is the market confirming this catalyst, or fading it?','Would you trade the headline now, or wait for price confirmation?','Is this a real repricing event or temporary headline noise?','Which asset is giving the clearest confirmation?'],'CHART':['Breakout or fakeout?','Which level would you watch first?','Would you wait for confirmation on the next candle?'],'VOLUME':['Is volume confirming the move?','Would you wait for follow-through?'],'CHOICE':['Chase, pullback, or wait?','What would change your view?'],'BREAKOUT':['Breakout or fakeout?','Would you wait for another candle?'],'DATA':['Did you notice this signal?','Does this data change your read?'],'UPDATE':['Did this change your read?','What signal would you watch next?']]}

def load(path,default=None):
    if default is None:default={}
    if not path.exists():return default
    try:x=json.loads(path.read_text(encoding='utf-8'));return x if isinstance(x,type(default)) else default
    except Exception:return default
def clean(x):return re.sub(r'[ \t]+',' ',str(x or '')).strip()
def get_symbol(draft,text):
    for v in (draft.get('symbol'),draft.get('primary_symbol')):
        s=re.sub(r'USDT$','',str(v or '').upper().replace('$','').strip())
        if re.fullmatch(r'[A-Z0-9]{1,15}',s):return s
    m=re.search(r'\$([A-Z][A-Z0-9]{1,14})\b',text.upper());return m.group(1) if m else ''
def choose_style(draft,selected):
    raw=str(draft.get('experiment_format') or draft.get('editorial_style') or selected.get('category') or '').upper()
    if selected.get('news_title') or 'NEWS' in raw or 'HEADLINE' in raw:return 'NEWS'
    if 'VOLUME' in raw:return 'VOLUME'
    if 'BREAKOUT' in raw or 'FAKEOUT' in raw:return 'BREAKOUT'
    if 'DATA' in raw:return 'DATA'
    if 'UPDATE' in raw or 'FOLLOW' in raw:return 'UPDATE'
    if 'CHOICE' in raw:return 'CHOICE'
    return 'CHART' if ('CHART' in raw or draft.get('visual_plan')) else 'CHOICE'
def fresh_news(selected):
    data=load(NEWS,{});articles=data.get('articles') or [];wanted=clean(selected.get('news_title'))
    for a in articles:
        if not isinstance(a,dict):continue
        title=clean(a.get('title') or a.get('headline'))
        if title and (not wanted or title==wanted):return {'source':clean(a.get('source')),'title':title[:240],'url':clean(a.get('url')),'published_at':clean(a.get('published_at'))}
    return {}
def fmt(v):
    try:return f'{float(v):.8g}'
    except Exception:return str(v)
def chart_levels(draft,data):
    src=draft.get('technical_levels') or (data.get('research') or {}).get('chart_levels') or {};return src if isinstance(src,dict) else {}
def polish_repetitions(text):
    """Remove obvious duplicated metric wording without rewriting researched facts."""
    text=re.sub(r'\bSpot volume is (\$[0-9][^,.\n]*?) spot volume\b',r'Spot volume is \1',text,flags=re.I)
    text=re.sub(r'\b(\$[0-9][0-9.,]*[KMB]?)\s+\1\b',r'\1',text,flags=re.I)
    text=re.sub(r'\b(the market market|price price|volume volume)\b',lambda m:m.group(1).split()[0],text,flags=re.I)
    return re.sub(r'\n{3,}','\n\n',text).strip()
def make_post(draft,data):
    original=clean(draft.get('post') or draft.get('text') or '')
    if not original:raise SystemExit('Draft has no post text')
    symbol=get_symbol(draft,original);selected=data.get('selected_editorial_lane') or data.get('selected_opportunity') or {};style=choose_style(draft,selected);news=fresh_news(selected)
    if not symbol and news.get('title') and 'gold' in news['title'].lower():symbol='XAUUSD'
    if not symbol:raise SystemExit('Editorial layer: primary symbol missing')
    lines=[clean(x) for x in original.splitlines() if clean(x)]
    lines=[x for x in lines if x.lower() not in {'key levels:','key scenario levels:','fresh check:','quick market check:','this is the crypto story i’m watching right now:','this is the crypto story i\'m watching right now:'}]
    if style=='NEWS' and news:
        hook=f"🚨 {news['title']}"
        source_line=f"Source: {news['source']}" if news.get('source') else ''
        body_lines=[hook]+([source_line] if source_line else [])
        for line in lines:
            if news['title'].lower() not in line.lower() and line.lower()!=source_line.lower() and len(line)>=18:body_lines.append(line)
        body_lines=body_lines[:8]
    else:
        body_lines=[lines[0] if lines else f'${symbol} is giving the market a signal worth watching.']+[x for x in lines[1:] if len(x)>=18][:6]
    lv=chart_levels(draft,data)
    if lv:
        p=[]
        for key,label in [('current_price','price'),('support','support'),('resistance','resistance'),('tp1','TP1'),('target','target'),('invalidation','invalidation')]:
            if lv.get(key) is not None:p.append(f'{label} ${fmt(lv[key])}')
        if p:body_lines.append('📍 '+' • '.join(p))
        direction=str(lv.get('direction') or '').lower()
        if 'long' in direction:body_lines.append('Bull case: sustained acceptance above resistance strengthens the upside scenario; losing support weakens it.')
        elif 'short' in direction:body_lines.append('Bear case: a failed reclaim keeps downside risk active; invalidation is the level to watch.')
    questions=STYLE_QUESTIONS[style];qidx=sum(ord(c) for c in (symbol+style+datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')))%len(questions);question=questions[qidx]
    if style=='NEWS' and symbol and '$' not in question:question=question.rstrip('?')+f' for ${symbol}?'
    body='\n\n'.join(body_lines);body=re.sub(r'\?','.',body).strip(' .');text=polish_repetitions((body+'\n\n'+question)[:1200])
    if text.count('?')!=1:text=re.sub(r'\?','.',text).rstrip('.')+'\n\n'+question
    return text,style,question,news
def main():
    path=Path(os.environ.get('DRAFT_PATH',''))
    if not path.exists():raise SystemExit('DRAFT_PATH is missing')
    data=load(path,{});draft=data.setdefault('draft',{});text,style,question,news=make_post(draft,data)
    draft.update({'post':text,'text':text,'editorial_style':style.lower(),'human_editor':{'status':'POLISHED','version':'human-editor-v9','style':style,'question':question,'fresh_news_used':bool(news),'question_count':1,'fact_policy':'preserve supplied evidence only','repetition_cleanup':True}})
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps({'status':'HUMAN_EDITOR_APPLIED','version':'human-editor-v9','style':style,'characters':len(text),'question':question,'fresh_news':bool(news),'repetition_cleanup':True},indent=2,ensure_ascii=False),encoding='utf-8');path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'HUMAN_EDITOR_APPLIED','version':'human-editor-v9','characters':len(text),'style':style,'question':question,'fresh_news':bool(news)}))
if __name__=='__main__':main()
