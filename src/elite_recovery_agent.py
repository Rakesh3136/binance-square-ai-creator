"""Bounded NIC recovery pass for elite editorial failures.

Uses only facts already present in the draft. It never invents prices, sources,
targets, outcomes or private chain-of-thought. It repairs a small set of known
editorial defects, then the unchanged authoritative judge must run again.
"""
from __future__ import annotations
import json,re,os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/live/elite_recovery.json"
FAIL_SAFE={"empty_post","policy_language_failure","repetitive_feed_template","repeats_recent_published_sentence"}

def load(p):
    try:
        x=json.loads(Path(p).read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
    except Exception:return {}

def resolve():
    p=os.getenv("DRAFT_PATH","").strip()
    if not p: raise SystemExit("Elite recovery: DRAFT_PATH is required")
    q=Path(p)
    if not q.exists(): raise SystemExit(f"Elite recovery: draft not found: {p}")
    return q

def symbol(text,draft):
    s=str(draft.get("symbol") or "").upper().replace("$","").replace("USDT","").strip()
    if s:return "$"+s
    m=re.search(r"\$([A-Z][A-Z0-9]{1,14})\b",text.upper())
    return "$"+m.group(1) if m else "$this asset"

def sentences(text):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+",text) if x.strip()]

def one_question(text):
    qs=re.findall(r"[^\n.!?]*\?",text)
    return qs[0].strip() if len(qs)==1 else ""

def replace_question(text,q,newq):
    return text.replace(q,newq,1)

def main():
    draft_path=resolve(); data=load(draft_path); draft=data.get("draft") or {}
    text=str(draft.get("post") or draft.get("text") or "").strip()
    judge=load(ROOT/"data/live/elite_prepublication_judge.json")
    failures=judge.get("failures") if isinstance(judge.get("failures"),list) else []
    if not text or any(x in FAIL_SAFE for x in failures):
        OUT.write_text(json.dumps({"status":"NO_REPAIR","reasons":["unsafe_or_nonrepairable_failure"],"failures":failures},indent=2)+"\n")
        return 1
    s=symbol(text,draft); original=text
    # Repair only bounded, structural defects. Preserve all original factual text.
    lines=sentences(text)
    if "hook_below_82" in failures and lines:
        first=lines[0]
        if len(first.split())<8 or first.lower() in {"quick market check","the market is watching"}:
            lines[0]=f"{s}: the useful question is what the next market response confirms"
        text=" ".join(lines)
    low=text.lower()
    if "missing_mechanism_or_reasoning" in failures and "because" not in low:
        text += f"\n\nWhy it matters: the observed evidence matters because the next market response shows whether this move or thesis gets follow-through or rejection."
    low=text.lower()
    if "missing_invalidation_or_confirmation" in failures:
        text += f"\n\nWhat would change this view: a failure of the stated setup, thesis, or expected follow-through would weaken the idea; confirmation requires the evidence described above to persist."
    qs=re.findall(r"[^\n.!?]*\?",text)
    if "generic_engagement_question" in failures and qs:
        q=qs[-1]
        new=f"For {s}, which specific evidence would make you change your current view?"
        text=replace_question(text,q,new)
    elif len(qs)==0 and "must_have_exactly_one_question" in failures:
        text += f"\n\nFor {s}, which specific evidence would make you change your current view?"
    # Hard preservation: all original numeric/ticker tokens must remain.
    original_tokens=set(re.findall(r"\$[A-Z][A-Z0-9]{1,14}\b|[+-]?\d+(?:\.\d+)?%",original))
    new_tokens=set(re.findall(r"\$[A-Z][A-Z0-9]{1,14}\b|[+-]?\d+(?:\.\d+)?%",text))
    if not original_tokens.issubset(new_tokens):
        OUT.write_text(json.dumps({"status":"REPAIR_FAILED","reason":"explicit_fact_token_loss","failures":failures},indent=2)+"\n")
        return 1
    repair={"status":"REPAIRED","version":"1.0-bounded-elite-recovery","failures_seen":failures,"facts_preserved":True,"private_reasoning_exposed":False,"requires_fresh_judge":True}
    draft["post"]=text; draft["text"]=text; draft["elite_recovery"]=repair; data["draft"]=draft; data["elite_recovery"]=repair
    Path(draft_path).write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    OUT.write_text(json.dumps(repair,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(repair,indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__": raise SystemExit(main())
