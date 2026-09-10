import json, os, re, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
BASES=["https://www.binance.com/bapi/composite/v3/friendly/pgc/content/article/list","https://www.binance.com/bapi/composite/v1/friendly/pgc/content/article/list"]
OUT=Path("analytics/square_performance.jsonl"); STATE=Path("analytics/square_performance_state.json"); PUB=Path("analytics/publication_log.jsonl")

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode("utf-8"))

def load(path,default):
    if not path.exists():return default
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return default

def publications():
    rows=[]
    if PUB.exists():
        for line in PUB.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict):rows.append(x)
            except Exception:pass
    return rows

def post_id(row):
    for k in ("post_id","id","content_id","contentId","publication_id"):
        v=row.get(k)
        if v is not None and str(v).strip():return str(v)
    link=str(row.get("link") or row.get("url") or row.get("webLink") or "")
    m=re.search(r"(?:post|content|cpos)/([A-Za-z0-9_-]+)",link);return m.group(1) if m else ""

def fetch_recent(max_pages=30):
    found={}
    for base in BASES:
        for page in range(1,max_pages+1):
            url=f"{base}?pageIndex={page}&pageSize=50&type=2"
            try:data=get_json(url)
            except Exception:break
            payload=data.get("data") if isinstance(data,dict) else {}
            items=(payload.get("list") if isinstance(payload,dict) else None) or (payload.get("rows") if isinstance(payload,dict) else None) or []
            if not isinstance(items,list) or not items:break
            for item in items:
                if isinstance(item,dict) and post_id(item):found[post_id(item)]=item
            if len(items)<50:break
            time.sleep(.2)
        if found:break
    return found

def metric(item,*keys):
    for key in keys:
        v=item.get(key)
        if v is not None and v!='':
            try:return float(v)
            except Exception:pass
    return 0.0

def main():
    state=load(STATE,{"last_run":"","seen":{}});pubs=publications();recent=fetch_recent();now=datetime.now(timezone.utc).isoformat();matches=[]
    for pub in pubs:
        pid=post_id(pub)
        if not pid or pid not in recent:continue
        item=recent[pid];metrics={"views":metric(item,'viewCount','views','view_num'),'likes':metric(item,'likeCount','likes','like_num'),'comments':metric(item,'commentCount','comments','replyCount'),'shares':metric(item,'shareCount','shares'),'quotes':metric(item,'quoteCount','quotes')}
        record={"collected_at":now,"post_id":pid,"metrics":metrics,"author_name":item.get('authorName'),'web_link':item.get('webLink') or item.get('url'),'card_type':item.get('cardType'),'source':'Binance Square public content feed'};matches.append(record)
    seen=state.get('seen',{}) if isinstance(state.get('seen',{}),dict) else {}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('a',encoding='utf-8') as f:
        for r in matches:
            # Keep each hourly observation; this is what allows the learning engine to see growth curves.
            key=f"{r['post_id']}:{r['collected_at'][:13]}"
            if key in seen:continue
            seen[key]=r;f.write(json.dumps(r,ensure_ascii=False)+'\n')
    STATE.write_text(json.dumps({'last_run':now,'seen':seen,'last_match_count':len(matches)},indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','published_records':len(pubs),'feed_records':len(recent),'collected':len(matches),'source':'Binance Square public feed','output':str(OUT)},indent=2))
if __name__=='__main__':main()
