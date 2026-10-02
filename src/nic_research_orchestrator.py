"""NIC 20.1 — Research Orchestrator.
Runs a bounded, auditable research pass using configured public feeds plus Google News RSS.
It stores observations only; it never converts search results into facts automatically.
"""
from __future__ import annotations
import json, re, urllib.parse, urllib.request, urllib.error
from datetime import datetime,timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
TASK=ROOT/"data/live/nic_question_understanding.json"
ROLE=ROOT/"data/live/nic_role_contract.json"
CFG=ROOT/"data/live/nic_research_sources.json"
OUT=ROOT/"data/live/nic_research_raw.json"
REPORT=ROOT/"data/intelligence/nic_research_report.json"
UA="NIC-Research/20.1 (+https://github.com/Rakesh3136/binance-square-ai-creator)"

def load(p,d):
    try:
        x=json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
        return x if isinstance(x,type(d)) else d
    except Exception:return d

def fetch(url,timeout=12):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/rss+xml, application/xml, text/html;q=0.8"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        data=r.read(300000)
        return data.decode("utf-8","replace")

def rss_records(text,url,source_type):
    out=[]
    try:
        root=ET.fromstring(text)
    except Exception:
        return out
    for item in root.findall(".//item")[:20]:
        def val(tag):
            n=item.find(tag)
            return (n.text or "").strip() if n is not None else ""
        out.append({"url":val("link") or url,"title":val("title"),"text":re.sub(r"<[^>]+>"," ",val("description"))[:5000],
                     "published_at":val("pubDate") or None,"source_type":source_type})
    return out

def main():
    task=load(TASK,{}); role=load(ROLE,{}); cfg=load(CFG,{"feeds":[]})
    q=str(task.get("task") or role.get("mission") or "Binance Square crypto market analysis")
    # Keep search bounded and deterministic. The RSS endpoint is a discovery layer, not proof.
    queries = [
        q,
        "site:binance.com/en/support/announcement " + q,
        "Binance Square creator content " + q,
    ]
    records = []
    errors = []
    targets = [
        (
            "https://news.google.com/rss/search?"
            + urllib.parse.urlencode({"q": qq, "hl": "en-US", "gl": "US", "ceid": "US:en"}),
            "search",
        )
        for qq in queries
    ]
    for f in cfg.get("feeds",[]):
        if isinstance(f,dict) and f.get("url"): targets.append((str(f["url"]),str(f.get("source_type") or "unknown")))
    for url,stype in targets[:8]:
        try:
            body=fetch(url)
            parsed=rss_records(body,url,stype)
            if parsed:
                for item in parsed:
                    host = urllib.parse.urlparse(item.get("url", "")).netloc.lower()
                    if "binance.com" in host:
                        item["source_type"] = "official"
                records.extend(parsed)
            else: records.append({"url":url,"title":"Feed fetched without parseable entries","text":body[:2000],"source_type":stype,
                                  "limitations":["Feed format was not parsed into individual entries."]})
        except Exception as e:
            errors.append({"url":url,"error":type(e).__name__+": "+str(e)[:300]})
    # Deduplicate by URL/title.
    uniq=[]; seen=set()
    for r in records:
        k=(r.get("url"),r.get("title"))
        if k in seen: continue
        seen.add(k); uniq.append(r)
    now=datetime.now(timezone.utc).isoformat()
    for r in uniq: r["retrieved_at"]=now; r.setdefault("supports",[f"discovery for task: {q[:180]}"])
    out={"version":"20.1","status":"READY" if uniq or not errors else "PARTIAL","generated_at":now,
         "task":q,"records":uniq[:100],"errors":errors,
         "research_policy":["discovery is not proof","cross-check before publication","creator patterns are observations","unknown stays unknown"]}
    OUT.parent.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({"version":"20.1","status":out["status"],"query":q,"records":len(uniq),"errors":len(errors),"sources":["Google News RSS"]+[x[1] for x in targets[len(queries):]]},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":out["status"],"records":len(uniq),"errors":len(errors)},ensure_ascii=False))
if __name__=="__main__": main()
