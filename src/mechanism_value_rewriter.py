"""Deterministic evidence-preserving mechanism/value repair.

Adds one deterministic causal bridge using facts already present in the draft.
Upstream stages own broad differentiation; this stage owns mechanism integrity.
"""
from __future__ import annotations
import json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MAX_READER_CHARS=740
REPORT_DIR=ROOT/"data/reports"
OUT=ROOT/"data/live/mechanism_value_repair.json"
MECHANISM_TERMS=("because","driven by","explains why","the reason","which means","leads to","causes","due to","means that","translates into","shows up in","flows into","results in","comes from","depends on","hinges on","works through","is linked to","matters because","suggests that","implies that","in turn","which can make","which can leave","the mechanism","pathway","transmission")

def load(path):
    try:
        x=json.loads(Path(path).read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
    except Exception: return {}

def resolve_report():
    import os
    explicit=os.getenv("DRAFT_PATH","").strip()
    if explicit:
        p=Path(explicit)
        if not p.exists(): raise SystemExit(f"Mechanism repair: DRAFT_PATH does not exist: {explicit}")
        return p
    reports=sorted(REPORT_DIR.glob("*-multi-agent.json"),key=lambda p:p.stat().st_mtime,reverse=True)
    return reports[0] if reports else None

def norm(x): return re.sub(r"\s+"," ",str(x or "").strip())
def questions(text): return re.findall(r"[^?\n]*\?",text)
def mechanism_present(text): return any(t in text.lower() for t in MECHANISM_TERMS)
def explicit_facts(text):
    return (set(re.findall(r"\$[A-Z][A-Z0-9]{1,14}\b",text))|
            set(re.findall(r"\b[+-]?\d+(?:\.\d+)?%",text))|
            set(re.findall(r"\b\d+(?:\.\d+)?\b",text)))

def extract_symbol(draft,original):
    raw=str(draft.get("symbol") or "").strip().upper()
    if raw: return "$"+raw.replace("$","").replace("USDT","")
    m=re.search(r"\$([A-Z][A-Z0-9]{1,14})\b",original.upper())
    return "$"+m.group(1) if m else "$THIS-ASSET"

def deterministic_bridge(symbol,original,remaining=None):
    pct=re.findall(r"\b[+-]?\d+(?:\.\d+)%",original)
    if pct:
        o=pct[0]
        opts=[f"For {symbol}, that matters because the {o} reaction needs follow-through or rejection.",f"For {symbol}, the {o} reaction matters because the next response tests follow-through or rejection."]
    else:
        opts=[f"For {symbol}, the reaction matters because the next response tests follow-through or rejection.",f"For {symbol}, that matters because the next response tests follow-through or rejection."]
    if remaining is not None:
        fit=[x for x in opts if len(x)<=max(0,remaining)]
        return max(fit,key=len) if fit else ""
    return opts[0]

def normalize_questions(text,symbol):
    qs=questions(text)
    if len(qs)==1: return text,qs[0].strip(),False
    if len(qs)>1:
        keep=qs[-1].strip()
        body=text.replace(keep,"")
        for q in questions(body): body=body.replace(q,q.rstrip("?").rstrip()+".")
        return (body.strip()+"\n\n"+keep).strip(),keep,True
    q=f"What evidence should readers watch next for {symbol}?"
    return text.rstrip()+"\n\n"+q,q,True

def write_result(result):
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))

def main():
    report=resolve_report()
    if not report: raise SystemExit("Mechanism repair: no draft report")
    data=load(report); draft=data.get("draft") or {}; original=str(draft.get("post") or draft.get("text") or "").strip()
    if not original: raise SystemExit(f"Mechanism repair: draft has no post text: {report}")
    symbol=extract_symbol(draft,original)
    normalized,original_question,question_repaired=normalize_questions(original,symbol)
    body=normalized.replace(original_question,"").rstrip()
    bridge="" if mechanism_present(body) else deterministic_bridge(symbol,body,remaining=MAX_READER_CHARS-len(body)-len(original_question)-4)
    candidate=normalized if not bridge else f"{body}\n\n{bridge}\n\n{original_question}".strip()
    reasons=[]
    if bridge and "because" not in bridge.lower(): reasons.append("BRIDGE_CAUSAL_TERM_MISSING")
    if len(candidate)>MAX_READER_CHARS: reasons.append("FINAL_COPY_OVER_740")
    if not mechanism_present(candidate): reasons.append("MECHANISM_STILL_MISSING")
    if len(questions(candidate))!=1: reasons.append("QUESTION_COUNT_NOT_ONE")
    if explicit_facts(original)-explicit_facts(candidate): reasons.append("EXPLICIT_FACT_LOSS")
    if reasons:
        write_result({"status":"REPAIR_FAILED","draft_unchanged":True,"draft_path":str(report),"reasons":reasons,"bridge_preview":bridge}); return 1
    repair={"status":"REPAIRED","method":"deterministic_causal_bridge","question_repaired":question_repaired,"verified_facts_preserved":True,"exactly_one_question":True,"mechanism_present":True,"reader_value_floor_enabled":True,"max_reader_characters":MAX_READER_CHARS}
    draft["post"]=candidate; draft["text"]=candidate; draft["mechanism_value_repair"]=repair; data["draft"]=draft; data["mechanism_value_repair"]=repair
    Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    write_result({**repair,"draft_path":str(report)}); return 0
if __name__=="__main__": raise SystemExit(main())
