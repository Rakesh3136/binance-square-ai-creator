"""Standing, explicitly scoped authorization for editorial-only auto-publication."""
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
POLICY_PATH=ROOT/"nic_publication_policy.json"
OUT=LIVE/"nic_publication_authorization.json"
ACTIONABLE=re.compile(
    r"(?:\bentry\s*(?:price)?\s*[:=@]|"
    r"\bstop[ -]?loss\s*[:=@]|\btake[ -]?profit\s*[:=@]|"
    r"\b(?:SL|TP[1-3]?)\s*[:=@]|"
    r"\b(?:buy|sell)\s+now\b|\b(?:open|enter)\s+(?:a\s+)?"
    r"(?:long|short)\b|\b\d{1,3}\s*x\s+leverage\b)", re.I)

def load(path):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        return {}

def fresh(value, now, max_age_minutes=45):
    raw=str(value.get("generated_at") or value.get("timestamp") or "").strip()
    try:
        dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        if dt.tzinfo is None: return False
        age=(now-dt.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= max_age_minutes*60
    except ValueError:
        return False

def draft_text(path):
    report=load(path)
    draft=report.get("draft") if isinstance(report.get("draft"),dict) else {}
    for key in ("post","text","body","content","caption"):
        value=draft.get(key)
        if isinstance(value,str) and value.strip(): return value.strip()
    for key in ("text","post"):
        value=report.get(key)
        if isinstance(value,str) and value.strip(): return value.strip()
    return ""

def evaluate(policy, eligibility, routing, lane, text, now=None, nic21=None):
    now=now or datetime.now(timezone.utc)
    reasons=[]
    if policy.get("editorial_auto_publication_enabled") is not True:
        reasons.append("standing editorial auto-publication authorization is disabled")
    if str(policy.get("editorial_mode") or "").upper() != "EDITORIAL_ONLY":
        reasons.append("policy is not restricted to EDITORIAL_ONLY")
    if policy.get("trade_signal_publication_enabled") is not False:
        reasons.append("trade-signal publication must remain disabled")
    if policy.get("live_orders_enabled") is not False:
        reasons.append("live orders must remain disabled")
    if policy.get("requires_human_review_for_editorial") is True:
        reasons.append("mandatory human review is outstanding; this gate cannot authorize publication automatically")
    elif policy.get("requires_human_review_for_editorial") is not False:
        reasons.append("human-review policy must be explicit")
    if eligibility.get("eligible") is not True or str(eligibility.get("publication_mode") or "").upper() != "EDITORIAL":
        reasons.append("current-cycle eligibility is not EDITORIAL")
    if eligibility.get("trade_authorized") is not False:
        reasons.append("current-cycle editorial eligibility must explicitly deny trade authorization")
    if routing.get("publish") is not True or str(routing.get("decision") or "").upper() not in {"EDITORIAL_SIGNAL","EDITORIAL","RESEARCH","NO_TRADE"}:
        reasons.append("Signal-First did not explicitly authorize an editorial/research cycle")
    if lane.get("publish") is not True or str(lane.get("status") or "").upper() != "EDITORIAL_ELIGIBLE":
        reasons.append("editorial lane gate did not explicitly pass")
    if lane.get("trade_authorized") is not False:
        reasons.append("editorial lane must explicitly deny trade authorization")
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""
    if lane.get("draft_sha256") != text_hash:
        reasons.append("editorial lane result does not match the exact final draft")
    if not isinstance(nic21, dict) or nic21.get("status") != "PASS":
        reasons.append("NIC 21 originality/visual-truth gate did not explicitly pass")
    elif nic21.get("draft_sha256") != text_hash:
        reasons.append("NIC 21 result does not match the exact final draft")
    for label, artifact in (("eligibility",eligibility),("routing",routing),("editorial lane",lane)):
        if not fresh(artifact,now): reasons.append(f"{label} artifact is missing, stale, or future-dated")
    if not text.strip(): reasons.append("publishable draft text is missing")
    if ACTIONABLE.search(text): reasons.append("draft contains actionable trade instructions or levels")
    ok=not reasons
    return {
        "schema":"NIC-PUBLICATION-AUTHORIZATION-1.0",
        "generated_at":now.isoformat(),
        "status":"AUTHORIZED_EDITORIAL_ONLY" if ok else "BLOCKED",
        "authorized":ok,
        "publication_mode":"EDITORIAL_ONLY" if ok else "BLOCKED",
        "trade_signal_publication_authorized":False,
        "live_orders_authorized":False,
        "human_review_claimed":False,
        "human_review_status":"RECORDED_SEPARATELY_NOT_CLAIMED",
        "reasons":reasons,
        "draft_sha256":hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
        "policy":str(POLICY_PATH.relative_to(ROOT)),
        "note":"Creator has explicitly re-authorized guarded editorial-only background publishing. This gate never claims a human reviewed the draft; it authorizes only the exact draft that passes every current-cycle gate."
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--draft-path",required=True)
    args=parser.parse_args()
    path=Path(args.draft_path)
    if not path.is_absolute(): path=ROOT/path
    result=evaluate(
        load(POLICY_PATH),
        load(LIVE/"nic22_5_publication_eligibility.json"),
        load(LIVE/"signal_first_routing.json"),
        load(LIVE/"nic_editorial_lane_gate.json"),
        draft_text(path),
        nic21=load(LIVE/"nic21_gate.json"),
    )
    LIVE.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("status","authorized","publication_mode","trade_signal_publication_authorized","live_orders_authorized","human_review_claimed","reasons")},indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
