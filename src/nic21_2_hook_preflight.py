"""NIC 21.2 — Hook Diversity + Anti-Bot Opening Preflight.

Repairs only the opening sentence before the authoritative elite judge.
It never invents facts, changes the selected asset, or bypasses downstream gates.
"""
from __future__ import annotations
import hashlib, json, os, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/live/nic21_2_hook_preflight.json"
LOG=ROOT/"analytics/publication_log.jsonl"
GENERIC={
    "this is the crypto story im watching right now","quick market check",
    "the headline is only half the story","big things are coming","the market is watching",
}
MIN_HOOK_WORDS=8
MAX_SIMILARITY=.78

def norm(s): return re.sub(r"\s+"," ",str(s or "").strip())
def words(s): return re.findall(r"[A-Za-z0-9$%'.+-]+",str(s))
def toks(s): return {x.lower() for x in words(s) if len(x)>2}
def jac(a,b):
    a,b=toks(a),toks(b)
    return len(a&b)/len(a|b) if a|b else 0.0
def sentences(text):
    return [norm(x) for x in re.split(r"(?<=[.!?])\s+|\n+",text) if len(words(x))>=4]
def load(p,default):
    try:
        v=json.loads(Path(p).read_text(encoding="utf-8"))
        return v if isinstance(v,type(default)) else default
    except Exception:
        return default
def recent_hooks():
    out=[]
    if not LOG.exists(): return out
    for line in LOG.read_text(encoding="utf-8",errors="replace").splitlines()[-20:]:
        try:
            o=json.loads(line)
            t=str(o.get("text") or o.get("post") or o.get("content") or "")
            ss=sentences(t)
            if ss: out.append(ss[0])
        except Exception: pass
    return out
def resolve():
    raw=os.getenv("DRAFT_PATH","").strip()
    if raw:
        p=Path(raw)
        return p if p.exists() else None
    xs=sorted((ROOT/"data/reports").glob("*-multi-agent.json"),key=lambda p:p.stat().st_mtime,reverse=True)
    return xs[0] if xs else None

def main():
    report=resolve()
    if not report: raise SystemExit("NIC21.2: no draft")
    data=load(report,{})
    draft=data.get("draft") if isinstance(data.get("draft"),dict) else {}
    text=norm(draft.get("post") or draft.get("text") or "")
    if not text: raise SystemExit("NIC21.2: empty draft")
    ss=sentences(text)
    if not ss: raise SystemExit("NIC21.2: no usable sentences")
    old_hook=ss[0]
    recent=recent_hooks()
    generic=old_hook.lower().strip().rstrip(".!?") in GENERIC
    weak=len(words(old_hook))<MIN_HOOK_WORDS
    candidates=[]
    for i,s in enumerate(ss[:8]):
        if len(words(s))<MIN_HOOK_WORDS: continue
        similarity=max((jac(s,r) for r in recent),default=0)
        numeric=bool(re.search(r"(\$\d|\d+(?:\.\d+)?%|\$?[A-Z]{2,12}\b)",s))
        candidates.append((similarity,not numeric,i,s))
    candidates.sort(key=lambda x:(x[0],x[1],x[2]))
    chosen=None
    for sim,_,_,s in candidates:
        if sim<MAX_SIMILARITY and s.lower().strip().rstrip(".!?") not in GENERIC:
            chosen=s; break

    changed=False
    reason="existing_hook_passed"
    if generic or weak or (chosen and jac(old_hook,chosen)<1 and max((jac(old_hook,r) for r in recent),default=0)>=MAX_SIMILARITY):
        if chosen and chosen != old_hook:
            body=ss[1:]
            newtext="\n\n".join([chosen]+body)
            draft["post"]=newtext; draft["text"]=newtext; data["draft"]=draft
            Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            changed=True; reason="selected_existing_evidence_bound_hook"
        elif len(ss)>=2:
            combined=norm(ss[0]+" "+ss[1])
            if len(words(combined))>=MIN_HOOK_WORDS:
                body=ss[2:]
                newtext="\n\n".join([combined]+body)
                draft["post"]=newtext; draft["text"]=newtext; data["draft"]=draft
                Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
                changed=True; reason="combined_existing_sentences_for_hook"
            else:
                reason="no_safe_hook_repair_available"
        else:
            reason="no_safe_hook_repair_available"

    final_hook=sentences(str((data.get("draft") or {}).get("post") or ""))[0]
    final_similarity=max((jac(final_hook,r) for r in recent),default=0)
    passed=len(words(final_hook))>=MIN_HOOK_WORDS and final_hook.lower().strip().rstrip(".!?") not in GENERIC and final_similarity<MAX_SIMILARITY
    result={
        "schema_version":"NIC21.2","gate":"NIC_21_HOOK_DIVERSITY_ANTI_BOT",
        "status":"PASS" if passed else "BLOCKED","passed":passed,
        "changed":changed,"reason":reason,
        "hook_word_count":len(words(final_hook)),
        "recent_hook_similarity":round(final_similarity,4),
        "generic_hook":final_hook.lower().strip().rstrip(".!?") in GENERIC,
        "hook_sha256":hashlib.sha256(final_hook.encode()).hexdigest(),
        "updated_at":datetime.now(timezone.utc).isoformat(),
        "policy":{"pre_judge_only":True,"no_fact_invention":True,"no_gate_bypass":True,"authoritative_judge_remains_final":True},
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0 if passed else 1

if __name__=="__main__":
    raise SystemExit(main())
