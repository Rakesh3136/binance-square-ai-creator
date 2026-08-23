import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://www.binance.com/bapi/composite/v3/friendly/pgc/content/article/list"
OUT = Path("analytics/square_performance.jsonl")
STATE = Path("analytics/square_performance_state.json")
PUB = Path("analytics/publication_log.jsonl")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def load(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default


def publications():
    rows=[]
    if not PUB.exists(): return rows
    for line in PUB.read_text(encoding="utf-8").splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): rows.append(x)
        except Exception: pass
    return rows


def post_id(row):
    for k in ("post_id","id","content_id","publication_id"):
        v=row.get(k)
        if v is not None and str(v).strip(): return str(v)
    link=str(row.get("link") or row.get("url") or row.get("webLink") or "")
    m=re.search(r"(?:post|content)/([A-Za-z0-9_-]+)",link)
    return m.group(1) if m else ""


def fetch_recent(max_pages=5):
    found={}
    for page in range(1,max_pages+1):
        url=f"{BASE}?pageIndex={page}&pageSize=20&type=2"
        try:
            data=get_json(url)
        except Exception:
            break
        items=data.get("data",{}).get("list",[]) if isinstance(data,dict) else []
        if not isinstance(items,list) or not items: break
        for item in items:
            if isinstance(item,dict) and post_id(item): found[post_id(item)]=item
        time.sleep(.5)
    return found


def main():
    state=load(STATE,{"last_run":"","seen":{}})
    pubs=publications()
    recent=fetch_recent()
    now=datetime.now(timezone.utc).isoformat()
    matches=[]
    for pub in pubs:
        pid=post_id(pub)
        if not pid or pid not in recent: continue
        item=recent[pid]
        metrics={k:item.get(k,0) for k in ("viewCount","likeCount","commentCount","replyCount","shareCount","quoteCount")}
        record={"collected_at":now,"post_id":pid,"metrics":metrics,"author_name":item.get("authorName"),"web_link":item.get("webLink"),"card_type":item.get("cardType")}
        matches.append(record)
    seen=state.get("seen",{})
    with OUT.open("a",encoding="utf-8") as f:
        for r in matches:
            key=f"{r['post_id']}:{r['collected_at'][:13]}"
            if key in seen: continue
            seen[key]=r
            f.write(json.dumps(r,ensure_ascii=False)+"\n")
    STATE.write_text(json.dumps({"last_run":now,"seen":seen},indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"status":"OK","collected":len(matches),"source":"Binance Square latest feed","output":str(OUT)},indent=2))

if __name__ == "__main__": main()
