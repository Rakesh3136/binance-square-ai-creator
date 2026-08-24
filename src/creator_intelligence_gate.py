from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "data/reports"
FEEDBACK = ROOT / "data/live/creator_edit_feedback.json"
RESULT = ROOT / "data/live/creator_intelligence_gate.json"

def load(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}

def recent_posts():
    path = ROOT / "analytics/publication_log.jsonl"
    if not path.exists(): return []
    rows=[]
    for line in path.read_text(encoding="utf-8").splitlines()[-30:]:
        try:
            x=json.loads(line)
            if isinstance(x,dict): rows.append(x)
        except Exception: pass
    return rows

def main():
    files=sorted(DRAFTS.glob("*-multi-agent.json"), key=lambda p:p.stat().st_mtime, reverse=True)
    if not files: raise SystemExit("No AI draft found")
    path=files[0]; data=load(path); draft=data.get("draft") or {}
    text=str(draft.get("post") or draft.get("text") or "").strip()
    hook=str(draft.get("hook") or "").strip(); style=str(draft.get("editorial_style") or "").strip().lower()
    selected=data.get("selected_editorial_lane") or {}; preflight=load(ROOT/"data/live/editorial_preflight.json")
    opportunity=preflight.get("selected_opportunity") or {}; previous=recent_posts()
    checks=[]; score=100
    def fail(reason,points):
        nonlocal score; checks.append({"status":"fail","reason":reason,"points":points}); score-=points
    def ok(reason): checks.append({"status":"pass","reason":reason})
    if len(text)<100: fail("draft_too_short",20)
    elif len(text)>750: fail("draft_exceeds_750_characters",15)
    else: ok("mobile_length_ok")
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    if len(lines)<3: fail("not_enough_mobile_structure",10)
    else: ok("mobile_structure_ok")
    if not hook or (lines and hook.lower() not in lines[0].lower()): fail("hook_not_explicit",8)
    else: ok("hook_present")
    if len(re.findall(r"[^.!?\n]*\?",text))!=1: fail("must_have_exactly_one_question",15)
    else: ok("single_low_friction_question")
    if re.search(r"\b(like|follow|share|smash|subscribe)\b",text,re.I): fail("engagement_begging",12)
    else: ok("no_engagement_begging")
    if re.search(r"\b(guaranteed|100% profit|risk[- ]free|will moon|easy money)\b",text,re.I): fail("hype_claim_or_guarantee",20)
    else: ok("no_guaranteed_returns")
    symbol=str(opportunity.get("symbol") or selected.get("symbol") or "").upper().replace("USDT","")
    if symbol and not re.search(rf"\${re.escape(symbol)}\b",text,re.I): fail("primary_asset_cashtag_missing",8)
    else: ok("cashtag_attribution_present")
    normalized=re.sub(r"[^a-z0-9 ]","",text.lower())
    prior_texts=[str(x.get("post_text") or x.get("hook") or "").strip().lower() for x in previous]
    if normalized and any(normalized[:80]==re.sub(r"[^a-z0-9 ]","",p)[:80] for p in prior_texts if p): fail("opening_reused_from_previous_post",20)
    else: ok("opening_is_not_exact_reuse")
    prior_styles=[str(x.get("editorial_style") or "").lower() for x in previous[-5:]]
    if style and style in prior_styles[-2:]: fail("style_repeated_too_soon",10)
    else: ok("style_rotation_ok")
    if float(opportunity.get("adjusted_score") or 0)<72: fail("opportunity_below_publish_floor",20)
    else: ok("opportunity_is_strong")
    score=max(0,min(100,score)); publish=score>=82
    reasons=[x["reason"] for x in checks if x["status"]=="fail"]
    result={"status":"PASS" if publish else "REJECT","publish":publish,"score":score,"draft":str(path),"reasons":reasons,"checks":checks,"principle":"The creator may reject its own draft; publishing is earned, not assumed."}
    RESULT.parent.mkdir(parents=True,exist_ok=True); RESULT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    FEEDBACK.write_text(json.dumps({"status":"NEEDS_REWRITE" if not publish else "PASSED","reasons":reasons,"instruction":"Rewrite the draft from scratch. Keep verified facts, but change the hook, structure, wording and interaction mechanism. Do not patch individual sentences. Make it feel like a human creator with a distinct point of view."},indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if not publish: raise SystemExit(1)
if __name__=="__main__": main()
