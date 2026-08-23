from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
PERF=ROOT/'analytics/square_performance.jsonl'; PUB=ROOT/'data/live/publication_log.jsonl'; OUT=ROOT/'data/intelligence/audience_profile.json'
def read(path):
    if not path.exists(): return []
    rows=[]
    for line in path.read_text().splitlines():
        try:
            x=json.loads(line); rows.append(x if isinstance(x,dict) else {})
        except: pass
    return rows
def main():
    rows=read(PERF); profile={'version':1,'sample_size':len(rows),'signals':{},'warnings':[]}
    if not rows: profile['warnings'].append('No verified performance observations yet.')
    else:
        keys=['viewCount','likeCount','commentCount','replyCount','shareCount']
        totals={k:sum(float(r.get(k) or 0) for r in rows) for k in keys}
        views=totals['viewCount'] or 1
        profile['signals']={'views':totals['viewCount'],'likes_per_view':totals['likeCount']/views,'comments_per_view':totals['commentCount']/views,'replies_per_view':totals['replyCount']/views,'shares_per_view':totals['shareCount']/views}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(profile,indent=2))
    print(json.dumps(profile))
if __name__=='__main__': main()
