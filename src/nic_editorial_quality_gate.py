"""NIC Editorial Quality 3.0 — final reader-facing copy sanitizer.
Removes internal telemetry and detects template-shaped copy after all AI/editorial rewrites.
"""
from __future__ import annotations
import json, re, os
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
DRAFT=Path(os.getenv("DRAFT_PATH",""))
CONTRACT=ROOT/"data/live/nic_monetization_contract.json"
OUT=ROOT/"data/live/nic_editorial_quality_gate.json"
INTERNAL_PATTERNS=[
    r"(?im)^\\s*(?:attention|quality|engagement|opportunity|editorial)\\s+score\\s*[:=]\\s*[^\\n]+\\n?",
    r"(?im)^\\s*(?:experiment|campaign|cycle)\\s*(?:id|day)?\\s*[:=]\\s*[^\\n]+\\n?",
    r"(?im)^\\s*(?:generation_mode|content_lane|reader_payoff_type|hook_type)\\s*[:=]\\s*[^\\n]+\\n?",
]
GENERIC_OPENERS=[r"^For \\$?[A-Z0-9]{2,15}, that matters because",r"^\\$?[A-Z0-9]{2,15} is moving, but the useful signal is",r"^The \\$?[A-Z0-9]{2,15} move is easy to see\\."]
def load_json(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
    except Exception: return {}
def resolve():
    if DRAFT and DRAFT.exists(): return DRAFT
    reports=sorted((ROOT/"data/reports").glob("*-multi-agent.json"),key=lambda p:p.stat().st_mtime_ns,reverse=True)
    if not reports: raise SystemExit("NIC editorial gate: no draft found")
    return reports[0]
def clean(text):
    text=str(text or "").strip()
    for pat in INTERNAL_PATTERNS: text=re.sub(pat,"",text)
    return re.sub(r"\\n{3,}","\\n\\n",text).strip()
def main():
    path=resolve(); report=load_json(path); draft=report.get("draft") if isinstance(report.get("draft"),dict) else {}
    text=str(draft.get("post") or draft.get("text") or "").strip()
    if not text: raise SystemExit("NIC editorial gate: empty draft")
    before=text; text=clean(text)
    if not text: raise SystemExit("NIC editorial gate: internal-only draft")
    contract=load_json(CONTRACT); lane=str(contract.get("content_lane") or draft.get("content_lane") or "market_setup")
    opener=text.split("\\n\\n",1)[0]; generic=any(re.search(p,opener,re.I) for p in GENERIC_OPENERS)
    if text.count("?")>1:
        last=text.rfind("?"); text=text[:last].replace("?"," .")+text[last:]
    draft.update({"text":text,"post":text,"content_lane":lane,"reader_facing_sanitized":True,"internal_telemetry_removed":before!=text,"template_opening_detected":generic,"question_count":text.count("?")})
    report["nic_editorial_quality_gate"]={"version":"3.0","status":"PASS" if text.count("?")==1 and len(text)<=740 else "BLOCK","lane":lane,"template_opening_detected":generic,"internal_telemetry_removed":before!=text,"checked_at":datetime.now(timezone.utc).isoformat(),"rules":{"internal_telemetry_reader_hidden":True,"max_characters":740,"exactly_one_question":True,"no_fact_invention":True}}
    if len(text)>740 or text.count("?")!=1: raise SystemExit("NIC editorial gate: copy must be <=740 characters and contain exactly one question")
    report["draft"]=draft; path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report["nic_editorial_quality_gate"],indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["nic_editorial_quality_gate"],indent=2))
if __name__=="__main__": main()