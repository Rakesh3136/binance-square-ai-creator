"""Audit current-run Binance Square publication evidence without inferring success."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
RESULT=LIVE/"publication_result.json"
OUT=LIVE/"nic_publication_proof_audit.json"

def load(path):
    try:
        v=json.loads(path.read_text(encoding="utf-8"))
        return v if isinstance(v,dict) else {}
    except (OSError,ValueError):
        return {}

def evaluate(result, expected_run_id, publisher_outcome):
    current=bool(expected_run_id) and str(result.get("github_run_id") or "")==str(expected_run_id)
    status=str(result.get("status") or "").upper()
    pid=str(result.get("canonical_post_id") or result.get("post_id") or "").strip()
    link=str(result.get("link") or "").strip()
    reasons=[]
    proof="NONE"
    if not current:
        reasons.append("publication result is missing or belongs to another GitHub run")
        final="NO_VERIFIED_PUBLICATION"
    elif status=="PUBLISHED_VERIFIED_BY_API_RESPONSE" and pid and link:
        final="CONFIRMED_PUBLISHED"
        proof="CURRENT_RUN_BINANCE_API_POST_ID_AND_LINK"
    elif status=="PUBLISHED_SUBMITTED_504":
        final="SUBMISSION_UNCONFIRMED"
        reasons.append("Binance returned HTTP 504; a post ID is not verified")
    elif status=="PUBLISH_FAILED" or str(publisher_outcome).lower()=="failure":
        final="PUBLISH_FAILED"
        reasons.append(str(result.get("message") or result.get("error") or "publisher failed"))
    else:
        final="NO_VERIFIED_PUBLICATION"
        reasons.append("no current-run Binance API success with canonical post ID and link")
    return {
        "schema":"NIC-PUBLICATION-PROOF-AUDIT-1.0",
        "audited_at":datetime.now(timezone.utc).isoformat(),
        "github_run_id":str(expected_run_id or "") or None,
        "publisher_step_outcome":str(publisher_outcome or "unknown"),
        "publisher_result_status":status or None,
        "status":final,
        "verified":final=="CONFIRMED_PUBLISHED",
        "post_id":pid if final=="CONFIRMED_PUBLISHED" else None,
        "link":link if final=="CONFIRMED_PUBLISHED" else None,
        "publication_proof":proof,
        "reasons":reasons,
        "monetization_verified":False,
        "trade_authorization":False
    }

def main():
    result=evaluate(load(RESULT),os.getenv("NIC_RUN_ID",""),os.getenv("PUBLISHER_OUTCOME",""))
    LIVE.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
