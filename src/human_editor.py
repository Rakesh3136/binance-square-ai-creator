"""Creator 5.3 final editorial layer."""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NEWS=ROOT/'data/live/news_snapshot.json'
CONTEXT=ROOT/'data/live/publication_context.json'
OUT=ROOT/'data/live/editorial_polish.json'
STYLE_QUESTIONS={
 'NEWS':['Is the market confirming this catalyst, or fading it?','Would you wait for price confirmation before treating the headline as bullish?','Is this a real repricing event or temporary headline noise?','Which asset is giving the clearest confirmation?'],
 'CHART':['Breakout or fakeout?','Which level would you watch first?','Would you wait for confirmation on the next candle?'],
 'VOLUME':['Is volume confirming the move?','Would you wait for follow-through?'],
 'CHOICE':['Chase, pullback, or wait?','What would change your view?'],
 'BREAKOUT':['Breakout or fakeout?','Would you wait for another candle?'],
 'DATA':['Does this data change your read?','Which signal would you trust most here?'],
 'UPDATE':['Did this change your read?','What signal would you watch next?']}
def load(path,default=None):
    if default is None: default={}
    try:
        x=json.loads(path.read_text(encoding='utf-8')); return x if isinstance(x,type(default)) else default
    except Exception:return default
def clean(v): return re.sub(r'[ \t]+',' ',str(v or '')).strip()
def normalize_symbol(v):
    s=str(v or '').upper().replace('$','').replace('BINANCE:','').strip(); s=re.sub(r'USDT$','',s)
    return s if re.fullmatch(r'[A-Z0-9]{1,15}',s) else ''
def get_symbol(draft,text,context):
    for v in (context.get('symbol'),draft.get('symbol'),draft.get('primary_symbol')):
        s=normalize_symbol(v)
        if s:return s
    m=re.search(r'\$([A-Z][A-Z0-9]{0,14})\b',text.upper()); return m.group(1) if m else ''
def choose_style(draft,selected):
    raw=str(draft.get('experiment_format') or draft.get('editorial_style') or selected.get('category') or '').upper()
    if selected.get('news_title') or 'NEWS' in raw or 'HEADLINE' in raw:return 'NEWS'
    if 'VOLUME' in raw:return 'VOLUME'
    if 'BREAKOUT' in raw or 'FAKEOUT' in raw:return 'BREAKOUT'
    if 'DATA' in raw:return 'DATA'
    if 'UPDATE' in raw or 'FOLLOW' in raw:return 'UPDATE'
    if 'CHOICE' in raw:return 'CHOICE'
    return 'CHART' if 'CHART' in raw else 'CHOICE'
def find_selected_news(selected,context):
    wanted=clean(selected.get('news_title') or context.get('news_title'))
    for article in load(NEWS,{}).get('articles') or []:
        if not isinstance(article,dict):continue
        title=clean(article.get('title') or article.get('headline'))
        if title and (not wanted or title==wanted):
            return {'source':clean(article.get('source')),'title':title[:240],'url':clean(article.get('url')),'published_at':clean(article.get('published_at'))}
    return {}
def sanitize_cashtags(lines,allowed):
    out=[]
    for line in lines:
        tags={m.upper() for m in re.findall(r'\$([A-Z][A-Z0-9]{0,14})\b',line.upper())}
        if tags and any(t not in allowed for t in tags):continue
        out.append(line)
    return out
def polish_repetitions(text):
    text=re.sub(r'\bSpot volume is (\$[0-9][^,.\n]*?) spot volume\b',r'Spot volume is \1',text,flags=re.I)
    text=re.sub(r'\b(\$[0-9][0-9.,]*[KMB]?)\s+\1\b',r'\1',text,flags=re.I)
    text=re.sub(r'\b(the market market|price price|volume volume)\b',lambda m:m.group(1).split()[0],text,flags=re.I)
    return re.sub(r'\n{3,}','\n\n',text).strip()
def make_post(draft,report):
    context=load(CONTEXT,{}); selected=report.get('selected_editorial_lane') or report.get('selected_opportunity') or {}; original=clean(draft.get('post') or draft.get('text') or '')
    if not original:raise SystemExit('Draft has no post text')
    symbol=get_symbol(draft,original,context)
    if not symbol:raise SystemExit('Editorial layer: primary symbol missing')
    style=choose_style(draft,selected); news=find_selected_news(selected,context)
    lines=[clean(x) for x in original.splitlines() if clean(x)]
    lines=[x for x in lines if x.lower() not in {'key levels:','key scenario levels:','fresh check:','quick market check:','this is the crypto story i\'m watching right now:','this is the crypto story i’m watching right now:'}]
    allowed={symbol}
    # News stories are single-asset by default. Never trust arbitrary symbol lists from news metadata.
    if style != 'NEWS':
        for raw in selected.get('news_symbols') or []:
            s=normalize_symbol(raw)
            if s:allowed.add(s)
        for raw in context.get('news_symbols') or []:
            s=normalize_symbol(raw)
            if s:allowed.add(s)
    title=clean(selected.get('news_title') or context.get('news_title'))
    if style != 'NEWS':
        if 'gold' in title.lower():allowed.add('XAUUSD')
        if 'silver' in title.lower():allowed.add('XAGUSD')
    lines=sanitize_cashtags(lines,allowed)
    if style=='NEWS' and news:
        body_lines=['🚨 '+news['title']]
        if news.get('source'):body_lines.append('Source: '+news['source'])
        for line in lines:
            if line.lower() in {news['title'].lower(),('source: '+news['source']).lower()}:continue
            if len(line)>=18:body_lines.append(line)
        body_lines=body_lines[:9]
    else:body_lines=lines[:7] or ['$'+symbol+' is giving the market a signal worth watching.']
    pool=STYLE_QUESTIONS.get(style,STYLE_QUESTIONS['CHOICE']); hour=datetime.now(timezone.utc).strftime('%Y-%m-%d-%H'); q=pool[sum(ord(c) for c in symbol+style+hour)%len(pool)]
    if style=='NEWS' and '$'+symbol not in q:q=q.rstrip('?')+' for $'+symbol+'?'
    body='\n\n'.join(body_lines); body=re.sub(r'\?+','.',body).strip(' .'); text=polish_repetitions(body+'\n\n'+q)
    if text.count('?')!=1:text=re.sub(r'\?+','.',text).rstrip('.')+'\n\n'+q
    return text[:2200],style,q,news
def main():
    draft_path=Path(os.environ.get('DRAFT_PATH',''))
    if not draft_path.exists():raise SystemExit('DRAFT_PATH is missing')
    report=load(draft_path,{}); draft=report.setdefault('draft',{}); text,style,q,news=make_post(draft,report)
    draft.update({'post':text,'text':text,'editorial_style':style.lower(),'human_editor':{'status':'POLISHED','version':'human-editor-v13','style':style,'question':q,'fresh_news_used':bool(news),'question_count':1,'fact_policy':'preserve supplied evidence only','repetition_cleanup':True,'unsupported_cashtag_filter':True,'news_single_asset_lock':style=='NEWS'}})
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps({'status':'HUMAN_EDITOR_APPLIED','version':'human-editor-v13','style':style,'characters':len(text),'question':q,'fresh_news':bool(news),'unsupported_cashtag_filter':True},indent=2,ensure_ascii=False),encoding='utf-8')
    draft_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'HUMAN_EDITOR_APPLIED','version':'human-editor-v13','characters':len(text),'style':style,'fresh_news':bool(news)}))
if __name__=='__main__':main()
