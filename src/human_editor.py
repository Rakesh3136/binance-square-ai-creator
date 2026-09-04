"""Creator 5.5 final editorial layer with coherent multi-asset news handling."""
from __future__ import annotations
import json,os,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; NEWS=ROOT/'data/live/news_snapshot.json'; CONTEXT=ROOT/'data/live/publication_context.json'; OUT=ROOT/'data/live/editorial_polish.json'
ALIASES={'bitcoin':'BTC','btc':'BTC','ether':'ETH','ethereum':'ETH','eth':'ETH','binance coin':'BNB','bnb':'BNB','solana':'SOL','sol':'SOL','xrp':'XRP','ripple':'XRP','dogecoin':'DOGE','doge':'DOGE','cardano':'ADA','ada':'ADA','avalanche':'AVAX','avax':'AVAX','chainlink':'LINK','link':'LINK','zcash':'ZEC','zec':'ZEC','tron':'TRX','trx':'TRX','polkadot':'DOT','dot':'DOT','shiba inu':'SHIB','shib':'SHIB','sui':'SUI','toncoin':'TON','ton':'TON','pepe':'PEPE','floki':'FLOKI'}
STYLE_QUESTIONS={'NEWS':['Is the market confirming this catalyst, or fading it?','Would you wait for price confirmation before treating the headline as bullish?','Is this a real repricing event or temporary headline noise?','Which asset is giving the clearest confirmation?'],'CHART':['Breakout or fakeout?','Which level would you watch first?','Would you wait for confirmation on the next candle?'],'VOLUME':['Is volume confirming the move?','Would you wait for follow-through?'],'CHOICE':['Chase, pullback, or wait?','What would change your view?'],'BREAKOUT':['Breakout or fakeout?','Would you wait for another candle?'],'DATA':['Does this data change your read?','Which signal would you trust most here?'],'UPDATE':['Did this change your read?','What signal would you watch next?']}
def load(path,default=None):
 if default is None:default={}
 try:
  x=json.loads(path.read_text(encoding='utf-8'));return x if isinstance(x,type(default)) else default
 except Exception:return default
def clean(v):return re.sub(r'[ \t]+',' ',str(v or '')).strip()
def normalize(v):
 s=str(v or '').upper().replace('$','').replace('BINANCE:','').strip();s=re.sub(r'USDT$','',s);return s if re.fullmatch(r'[A-Z0-9]{1,15}',s) else ''
def title_assets(title):
 t=str(title or '').lower();found=[]
 for name,sym in sorted(ALIASES.items(),key=lambda x:-len(x[0])):
  if re.search(r'(?<![a-z0-9])'+re.escape(name)+r'(?![a-z0-9])',t) and sym not in found:found.append(sym)
 return found
def is_news(context,selected,draft):return bool(context.get('news_title') or selected.get('news_title') or draft.get('news_title') or selected.get('category') in {'breaking_news','news_and_macro','macro'})
def find_news(selected,context):
 wanted=clean(selected.get('news_title') or context.get('news_title'))
 for a in load(NEWS,{}).get('articles') or []:
  if not isinstance(a,dict):continue
  t=clean(a.get('title') or a.get('headline'))
  if t and (not wanted or t==wanted):return {'title':t[:240],'source':clean(a.get('source')),'summary':clean(a.get('summary') or a.get('description'))}
 return {}
def strip_tags(text,allowed):
 def repl(m):return '$'+m.group(1) if m.group(1).upper() in allowed else ''
 return re.sub(r'\$([A-Z][A-Z0-9]{0,14})\b',repl,text,flags=re.I)
def polish(text):
 text=re.sub(r'\bSpot volume is (\$[0-9][^,.\n]*?) spot volume\b',r'Spot volume is \1',text,flags=re.I)
 text=re.sub(r'\b(the market market|price price|volume volume)\b',lambda m:m.group(1).split()[0],text,flags=re.I)
 return re.sub(r'\n{3,}','\n\n',text).strip()
def make_post(draft,report):
 context=load(CONTEXT,{});selected=report.get('selected_editorial_lane') or report.get('selected_opportunity') or {};original=clean(draft.get('post') or draft.get('text') or '')
 if not original:raise SystemExit('Draft has no post text')
 primary=normalize(context.get('symbol') or draft.get('symbol') or draft.get('primary_symbol'))
 if not primary:raise SystemExit('Editorial layer: primary symbol missing')
 news_story=is_news(context,selected,draft);title=clean(selected.get('news_title') or context.get('news_title'));headline_assets=title_assets(title) if news_story else []
 allowed={primary}
 if news_story:
  allowed.update(headline_assets)
 lines=[clean(x) for x in original.splitlines() if clean(x)]
 lines=[x for x in lines if x.lower() not in {'key levels:','key scenario levels:','fresh check:','quick market check:'}]
 lines=[strip_tags(x,allowed) for x in lines]
 # If the verified headline names a secondary asset, preserve that asset as a real part of the story.
 # This fixes headline/body mismatches without inventing a new price or target.
 if news_story and len(headline_assets)>1:
  secondary=[s for s in headline_assets if s!=primary]
  existing=' '.join(lines).upper()
  for s in secondary:
   if ('$'+s not in existing) and (s not in existing):
    name=next((n for n,v in ALIASES.items() if v==s and len(n)>2),s)
    lines.append(f'Also highlighted: ${s} ({name.title()}) is part of the same reported market move.')
 title_line='🚨 '+title if title else '🚨 '+('$'+primary+' market update')
 body_lines=[title_line]
 news=find_news(selected,context)
 if news.get('source'):body_lines.append('Source: '+news['source'])
 for line in lines:
  if line.lower() in {title.lower(),('source: '+news.get('source','')).lower()}:continue
  if len(line)>=18:body_lines.append(line)
 body_lines=body_lines[:10]
 style='NEWS' if news_story else str(draft.get('editorial_style') or 'choice').upper()
 pool=STYLE_QUESTIONS.get(style,STYLE_QUESTIONS['CHOICE']);hour=datetime.now(timezone.utc).strftime('%Y-%m-%d-%H');q=pool[sum(ord(c) for c in primary+style+hour)%len(pool)]
 body='\n\n'.join(body_lines);body=re.sub(r'\?+','.',body).strip(' .');text=polish(body+'\n\n'+q)
 if text.count('?')!=1:text=re.sub(r'\?+','.',text).rstrip('.')+'\n\n'+q
 return text[:2200],style,q,bool(news),headline_assets
def main():
 path=Path(os.environ.get('DRAFT_PATH',''))
 if not path.exists():raise SystemExit('DRAFT_PATH is missing')
 report=load(path,{});draft=report.setdefault('draft',{});text,style,q,has_news,headline_assets=make_post(draft,report)
 draft.update({'post':text,'text':text,'editorial_style':style.lower(),'human_editor':{'status':'POLISHED','version':'human-editor-v15','style':style,'question':q,'fresh_news_used':has_news,'question_count':1,'fact_policy':'preserve supplied evidence only','repetition_cleanup':True,'headline_asset_coherence':True,'headline_assets':headline_assets}})
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps({'status':'HUMAN_EDITOR_APPLIED','version':'human-editor-v15','style':style,'characters':len(text),'question':q,'fresh_news':has_news,'headline_assets':headline_assets},indent=2,ensure_ascii=False),encoding='utf-8');path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':'HUMAN_EDITOR_APPLIED','version':'human-editor-v15','style':style,'characters':len(text),'fresh_news':has_news,'headline_assets':headline_assets}))
if __name__=='__main__':main()
