"""NIC Human Editorial Intelligence v1 — keyless continuous editorial learning.

Learns only from observed editor events and explicitly attributable outcomes.
It never rewrites facts, prices, trade levels, or publication truth. Learned
patterns are advisory policy consumed by the deterministic human editor.
"""
from __future__ import annotations
import hashlib,json,re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"; INTEL=ROOT/"data/intelligence"
EVENTS=LIVE/"nic_human_editor_events.jsonl"
STATE=LIVE/"nic_human_editor_intelligence.json"
REPORT=INTEL/"nic_human_editor_intelligence_report.json"
POLISH=LIVE/"editorial_polish.json"
SCORE=LIVE/"script_scorecard_4.json"
CONTEXT=LIVE/"publication_context.json"
ATTR=ROOT/"analytics/publication_attribution.jsonl"
OUTCOMES=ROOT/"analytics/creator_7_2_outcomes.jsonl"

def load(p,d=None):
    try:
        x=json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
        return x if isinstance(x,type(d)) else d
    except Exception:return d

def rows(p):
    out=[]
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict):out.append(x)
            except Exception:pass
    return out

def num(v):
    try:return float(v)
    except Exception:return 0.0

def sha(s):
    return hashlib.sha256(str(s or "").encode()).hexdigest()[:16]

def classify_question(text):
    low=str(text or "").lower()
    if "confirmation" in low or "real rather than" in low:return "confirmation"
    if "follow-through" in low or "watch next" in low:return "follow_through"
    return "reaction"

def extract_context():
    c=load(CONTEXT,{}) or {}
    return {
        "symbol":str(c.get("symbol") or c.get("selected_lane_symbol") or "").upper().replace("USDT","").replace("$",""),
        "category":str(c.get("category") or c.get("content_category") or "").lower(),
        "format":str(c.get("format") or "").lower(),
        "content_family":str(c.get("content_family") or "").lower(),
        "hook_family":str(c.get("hook_family") or "").lower(),
    }

def append_event(event):
    EVENTS.parent.mkdir(parents=True,exist_ok=True)
    existing=rows(EVENTS)
    if any(x.get("event_id")==event["event_id"] for x in existing):return False
    with EVENTS.open("a",encoding="utf-8") as f:f.write(json.dumps(event,ensure_ascii=False)+"\n")
    return True

def outcome_index():
    idx={}
    for x in rows(ATTR)+rows(OUTCOMES):
        pid=str(x.get("canonical_post_id") or x.get("post_id") or x.get("publication_id") or "").strip()
        if pid: idx[pid]=x
    return idx

def learn(events):
    comparable=defaultdict(lambda:{"n":0,"accepted":0,"blocked":0,"outcomes":[]})
    questions=Counter()
    transforms=Counter()
    for e in events:
        key=(e.get("category",""),e.get("format",""),e.get("transformation","unknown"))
        b=comparable[key]; b["n"]+=1
        if e.get("status")=="PRESERVED":b["accepted"]+=1
        else:b["blocked"]+=1
        if e.get("outcome_score") is not None:b["outcomes"].append(num(e["outcome_score"]))
        if e.get("question_style"):questions[e["question_style"]]+=1
        for t in e.get("transformations",[]):transforms[t]+=1
    patterns=[]
    for key,b in comparable.items():
        if b["n"]<3:continue
        outcome=sum(b["outcomes"])/len(b["outcomes"]) if b["outcomes"] else None
        patterns.append({
            "category":key[0],"format":key[1],"transformation":key[2],
            "observations":b["n"],"accepted":b["accepted"],"blocked":b["blocked"],
            "acceptance_rate":round(b["accepted"]/b["n"],3),
            "attributable_outcome_mean":round(outcome,4) if outcome is not None else None,
            "evidence_tier":"repeatable"
        })
    preferred=questions.most_common(1)[0][0] if questions else ""
    # A learned style is only promoted after three observations.
    if questions and sum(questions.values())<3:preferred=""
    state={
        "version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),
        "status":"READY","learning_mode":"CONTINUOUS_KEYLESS",
        "event_count":len(events),"repeatable_patterns":patterns,
        "transformation_counts":dict(transforms),"question_style_counts":dict(questions),
        "editor_policy":{
            "preferred_question_style":preferred,
            "minimum_observations_for_learning":3,
            "facts_are_immutable":True,
            "trade_levels_are_immutable":True,
            "safety_gates_are_authoritative":True,
            "learned_policy_is_advisory":True
        },
        "guardrails":[
            "Never invent evidence, prices, levels, outcomes, revenue or reader actions.",
            "Never use views as revenue.",
            "Never infer causality from observational performance.",
            "Never let learned policy override Signal-First, safety or publication eligibility.",
            "If evidence is insufficient, preserve the deterministic editor behavior."
        ]
    }
    return state

def main():
    ctx=extract_context(); polish=load(POLISH,{}) or {}; score=load(SCORE,{}) or {}
    winner=score.get("winner") or {}; post=""
    if isinstance(winner,dict):post=str(winner.get("script") or "")
    # The current edited report is authoritative for the before/after hashes.
    candidates=list(ROOT.glob("data/reports/*-multi-agent.json"))
    draft=max(candidates,key=lambda p:p.stat().st_mtime) if candidates else None
    before=""
    if draft:
        d=load(draft,{}) or {}; dd=d.get("draft") or {}
        before=str(dd.get("post") or dd.get("text") or winner.get("script") or "")
    after=str((polish.get("status")=="PRESERVED") and (winner.get("script") or post) or "")
    if isinstance(polish,dict) and polish.get("status")=="PRESERVED":
        # Do not pretend the scorecard is the final text; only use hashes/metrics
        # from the editor output where available.
        after=post or before
    event_id=sha((ctx["symbol"],ctx["category"],before,after,polish.get("edited_at")))
    transformations=[]
    if before!=after:transformations.append("surgical_cleanup")
    if before and "$"+ctx["symbol"] not in before.upper() and "$"+ctx["symbol"] in after.upper():transformations.append("cashtag_repair")
    qstyle=classify_question(after)
    if "?" in after and "?" not in before:transformations.append("question_repair")
    if polish.get("template_hits",0):transformations.append("template_detection")
    event={
        "event_id":event_id,"timestamp":datetime.now(timezone.utc).isoformat(),
        "symbol":ctx["symbol"],"category":ctx["category"],"format":ctx["format"],
        "content_family":ctx["content_family"],"hook_family":ctx["hook_family"],
        "status":str(polish.get("status") or "UNKNOWN"),"editor_version":str(polish.get("version") or ""),
        "original_hash":sha(before),"edited_hash":sha(after),
        "word_count_before":len(re.findall(r"\b\w+\b",before)),
        "word_count_after":len(re.findall(r"\b\w+\b",after)),
        "transformations":transformations,"transformation":transformations[0] if transformations else "preservation",
        "question_style":qstyle if "?" in after else "",
        "template_hits":int(polish.get("template_hits") or 0),
        "blocked_reason":polish.get("reason") if polish.get("status")=="BLOCKED" else None,
        "outcome_score":None,
        "revenue_verified":False
    }
    append_event(event)
    events=rows(EVENTS); state=learn(events)
    LIVE.mkdir(parents=True,exist_ok=True);INTEL.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps({
        "version":"1.0","status":"READY","generated_at":state["generated_at"],
        "event_count":state["event_count"],"repeatable_patterns":len(state["repeatable_patterns"]),
        "editor_policy":state["editor_policy"],
        "output":str(STATE.relative_to(ROOT))
    },indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"READY","event_count":len(events),"repeatable_patterns":len(state["repeatable_patterns"]),"preferred_question_style":state["editor_policy"]["preferred_question_style"]}))

if __name__=="__main__":main()
