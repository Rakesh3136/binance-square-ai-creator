import json,re
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
MARKET=Path('data/live/market_snapshot.json');NEWS=Path('data/live/news_snapshot.json');MEMORY=Path('analytics/strategy_memory.json');PUBLICATIONS=Path('analytics/publication_log.jsonl');FEEDBACK=Path('data/live/feedback_strategy.json');OUTPUT=Path('data/live/editorial_preflight.json')
MIN_MARKET_SCORE=72.0;NEWS_FRESH_MINUTES=180;NEWS_MATERIAL_SCORE=45.0;MEMORY_REPEAT_PENALTY=18.0;MEMORY_HARD_BLOCK_COUNT=3;CATEGORY_REPEAT_PENALTY=14.0;ASSET_COOLDOWN_HOURS=12

def load(p):
    if not p.exists():return {}
    try:
        x=json.loads(p.read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}
def rows(v):return v if isinstance(v,list) else []
def extract_symbols(t):
    found=set(); blob=str(t or '').upper()
    for token in re.findall(r'(?<![A-Z0-9])\$?[A-Z][A-Z0-9]{0,11}(?:USDT)?(?![A-Z0-9])',blob):
        b=token.replace('$','');b=b[:-4] if b.endswith('USDT') else b
        if 1<=len(b)<=10:found.add(b)
    if 'GOLD' in blob:found.add('XAUUSD')
    if 'SILVER' in blob:found.add('XAGUSD')
    return found
def recent_publications():
    out=[];cutoff=datetime.now(timezone.utc)-timedelta(hours=24)
    if not PUBLICATIONS.exists():return out
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines():
        try:
            row=json.loads(line);dt=datetime.fromisoformat(str(row.get('published_at','')).replace('Z','+00:00'))
            if dt>=cutoff:out.append({**row,'_symbols':extract_symbols(' '.join(str(row.get(k) or '') for k in ('symbol','selected_lane_symbol','topic'))),'_dt':dt})
        except Exception:pass
    return out
def add_market(pool,cat,item,boost=0):
    if not isinstance(item,dict) or not item.get('symbol'):return
    raw=float(item.get('content_signal_score') or 0)
    if cat in {'top_gainers','top_losers'}:raw=min(100,abs(float(item.get('price_change_percent') or 0))*4.5+float(item.get('intraday_range_percent') or 0))
    elif cat=='volume_leaders':raw=min(100,raw+10)
    elif cat=='new_listings':raw=min(100,raw+max(0,25-float(item.get('days_since_listing') or 30)*3))
    pool.append({'type':'market','category':cat,'topic':str(item['symbol']).upper(),'raw_score':round(min(100,raw+boost),2),'reason':cat})
def add_news(pool,a):
    if not isinstance(a,dict):return
    title=str(a.get('title') or '').strip();pub=str(a.get('published_at') or '')
    try:age=(datetime.now(timezone.utc)-datetime.fromisoformat(pub.replace('Z','+00:00'))).total_seconds()/60
    except Exception:return
    if not title or age < -10 or age > NEWS_FRESH_MINUTES:return
    score=float(a.get('news_score') or 0)
    if score<NEWS_MATERIAL_SCORE:return
    syms=list(a.get('symbols') or []) or list(extract_symbols(title+' '+str(a.get('summary') or '')))
    if not syms:syms=['BTC']
    for s in syms[:2]:
        s=str(s).upper().replace('USDT','')
        if not re.fullmatch(r'[A-Z0-9]{1,10}',s):continue
        pool.append({'type':'news','category':'breaking_news' if score>=70 else 'news_and_macro','topic':s+'USDT' if s not in {'XAUUSD','XAGUSD'} else s,'symbol':s+'USDT' if s not in {'XAUUSD','XAGUSD'} else s,'raw_score':round(score,2),'reason':'fresh verified news catalyst','title':title[:240],'url':str(a.get('url') or ''),'source':str(a.get('source') or ''),'published_at':pub,'news_score':score,'news_symbols':syms[:2]})
def main():
    market,news,memory=load(MARKET),load(NEWS),load(MEMORY);pubs=recent_publications();pc=Counter();cc=Counter();last={}
    for r in pubs:
        for s in r.get('_symbols',set()):pc[s]+=1;last[s]=max(last.get(s,datetime.min.replace(tzinfo=timezone.utc)),r['_dt'])
        if r.get('content_category'):cc[str(r['content_category']).lower()]+=1
    mc=Counter(str(x.get('topic') or '').upper().replace('USDT','') for x in rows(memory.get('recent_performance_observations')) if isinstance(x,dict) and x.get('topic'));pool=[]
    for x in rows(market.get('top_gainers'))[:10]:add_market(pool,'top_gainers',x)
    for x in rows(market.get('top_losers'))[:10]:add_market(pool,'top_losers',x)
    for x in rows(market.get('highest_volume'))[:10]:add_market(pool,'volume_leaders',x)
    for x in rows(market.get('new_listing_market'))[:10]:add_market(pool,'new_listings',x,5)
    for x in sorted([z for z in rows(market.get('top_content_signals')) if isinstance(z,dict)],key=lambda z:float(z.get('intraday_range_percent') or 0),reverse=True)[:8]:add_market(pool,'high_volatility',x,3)
    for a in rows(news.get('articles')):add_news(pool,a)
    pool=list({(x['type'],x['category'],x['topic'],x.get('title','')):x for x in pool}.values());now=datetime.now(timezone.utc)
    for c in pool:
        b=c['topic'][:-4] if c['topic'].endswith('USDT') else c['topic'];recent=pc.get(b,0);mem=mc.get(b,0);cat=cc.get(c['category'],0);active=bool(last.get(b) and now-last[b]<timedelta(hours=ASSET_COOLDOWN_HOURS));news_override=c.get('type')=='news';penalty=0 if news_override else min(55,recent*22)+min(54,mem*MEMORY_REPEAT_PENALTY)+min(35,cat*CATEGORY_REPEAT_PENALTY)+(45 if active else 0);c.update({'recent_count':recent,'memory_count':mem,'category_recent_count':cat,'cooldown_active':active,'news_override':news_override,'adjusted_score':round(c['raw_score']-penalty,2),'repeated':False if news_override else (recent>=2 or mem>=MEMORY_HARD_BLOCK_COUNT or active)})
    fresh=[x for x in pool if x.get('type')=='news'];fresh.sort(key=lambda x:x['raw_score'],reverse=True);eligible=[x for x in pool if x.get('type')=='market' and not x['repeated']];best_market=max(eligible,key=lambda x:x['adjusted_score'],default=None);best_news=fresh[0] if fresh else None;best=best_news if best_news else best_market;run_ai=bool(best_news or (best_market and best_market['adjusted_score']>=MIN_MARKET_SCORE));reason='fresh_material_news' if best_news else ('strong_market_opportunity' if run_ai else 'no_strong_opportunity');selected=None
    if best:
        selected={'category':best['category'],'symbol':best['topic'],'reason':best['reason'],'recommended_experiment':None,'instruction':'Lead with the verified news event, name the source, explain why it matters now, then connect it to market impact. Never turn fresh news into a generic price recap.' if best.get('type')=='news' else f"Use {best['category'].replace('_',' ')} as the starting lane."}
        if best.get('type')=='news':selected.update({'news_title':best.get('title'),'news_url':best.get('url'),'news_source':best.get('source'),'news_published_at':best.get('published_at'),'news_score':best.get('news_score'),'news_symbols':best.get('news_symbols') or [best.get('symbol')]})
    result={'generated_at':now.isoformat(),'run_ai':run_ai,'reason':reason,'selected_opportunity':selected,'candidate_pool':sorted(pool,key=lambda x:x['adjusted_score'],reverse=True)[:32],'best_market_candidate':best_market,'best_news_candidate':best_news,'fresh_news_count':len(fresh),'recent_topic_counts':dict(pc),'recent_category_counts':dict(cc),'memory_topic_counts':dict(mc),'strategy_memory_loaded':bool(memory),'rules':{'min_market_score':MIN_MARKET_SCORE,'news_material_score':NEWS_MATERIAL_SCORE,'news_fresh_minutes':NEWS_FRESH_MINUTES,'asset_cooldown_hours':ASSET_COOLDOWN_HOURS,'breaking_news_override':bool(best_news)}}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True);OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False))
if __name__=='__main__':raise SystemExit(main())
