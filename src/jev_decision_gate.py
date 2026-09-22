"""Optional Jev System-One decision layer.

Jev is an additional typed judgment layer, not a source of market data and not a
replacement for deterministic safety/evidence gates. If JEV_API_KEY is absent,
the creator remains fully functional and records Jev as unavailable.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/live/jev_decision.json"
URL = "https://www.jevai.org/api/v1/decisions"


def _post(payload: dict, key: str) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _answer(resp: dict, name: str):
    data = resp.get("data") if isinstance(resp, dict) else {}
    answers = data.get("answers") if isinstance(data, dict) else {}
    if isinstance(answers, dict):
        item = answers.get(name) or {}
        if isinstance(item, dict):
            return item
    return {}


def evaluate(*, symbol: str, category: str, post: str, direction: str,
             entry, tp1, tp2, sl, opportunity_score: float,
             quality_score: float, evidence: list[str], deterministic_ok: bool) -> dict:
    key = os.getenv("JEV_API_KEY", "").strip()
    result = {
        "enabled": bool(key),
        "status": "disabled_no_api_key" if not key else "error",
        "publish": bool(deterministic_ok),
        "confidence": 0.0,
        "action": "local_gates_only",
    }
    if not key:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    state = {
        "symbol": symbol,
        "category": category,
        "direction": direction,
        "entry_trigger": entry,
        "tp1": tp1,
        "tp2": tp2,
        "sl": sl,
        "opportunity_score": opportunity_score,
        "quality_score": quality_score,
        "evidence": evidence[-12:],
        "deterministic_gates_passed": deterministic_ok,
        "post_excerpt": post[:2400],
        "rule": "Jev may recommend review/block, but cannot override deterministic safety/evidence failures.",
    }
    payload = {
        "model": "typesafe-ai/jev",
        "state": state,
        "questions": {
            "action": {
                "type": "choice",
                "instructions": "Choose the appropriate publication action after reviewing the supplied evidence.",
                "criteria": {
                    "publish": "Evidence and setup are coherent enough to proceed to the existing deterministic publisher.",
                    "review": "The setup may be valid, but uncertainty is material; require another analysis cycle.",
                    "block": "The supplied evidence is not sufficient for publication.",
                },
            },
            "evidence_sufficient": {
                "type": "noul",
                "instructions": "Is the supplied evidence sufficient to support the stated conditional trading setup?",
            },
            "setup_quality": {
                "type": "score",
                "instructions": "Score the overall quality of the supplied setup for publication.",
                "criteria": ["weak", "fair", "good", "strong", "exceptional"],
            },
        },
    }
    try:
        resp = _post(payload, key)
        action = _answer(resp, "action")
        evidence_a = _answer(resp, "evidence_sufficient")
        quality_a = _answer(resp, "setup_quality")
        action_choice = str(action.get("choice") or action.get("value") or "").lower()
        confidence = float(action.get("confidence") or evidence_a.get("confidence") or 0.0)
        evidence_prob = evidence_a.get("noul")
        try:
            evidence_prob = float(evidence_prob) if evidence_prob is not None else None
        except Exception:
            evidence_prob = None
        # Jev is a second judge. It only adds a block/review when confidence is
        # meaningful; it never converts a deterministic failure into approval.
        publish = bool(deterministic_ok and action_choice == "publish" and confidence >= 0.70)
        if evidence_prob is not None:
            publish = publish and evidence_prob >= 0.70
        result.update({
            "status": "ok",
            "publish": publish,
            "action": action_choice or "unknown",
            "confidence": confidence,
            "evidence_probability": evidence_prob,
            "setup_quality": quality_a.get("score") or quality_a.get("value"),
            "raw": resp,
        })
    except urllib.error.HTTPError as exc:
        # Jev is an optional second-opinion integration. An invalid/expired key
        # (401/403) means Jev is unavailable, not that the market setup itself
        # failed. Keep deterministic/ensemble authority intact and make the
        # failure auditable so the key can be repaired without deadlocking the
        # creator. A valid Jev response with review/block still fails closed.
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
        except Exception:
            detail = ""
        if exc.code in {401, 403}:
            result.update({
                "status": "unavailable_auth",
                "error": f"HTTPError: {exc.code} {exc.reason}",
                "error_detail": detail,
                "publish": bool(deterministic_ok),
                "action": "local_gates_only",
                "confidence": 0.0,
                "jev_authoritative": False,
            })
        else:
            result.update({
                "status": "unavailable_http",
                "error": f"HTTPError: {exc.code} {exc.reason}",
                "error_detail": detail,
                "publish": bool(deterministic_ok),
                "action": "local_gates_only",
                "confidence": 0.0,
                "jev_authoritative": False,
            })
    except (urllib.error.URLError, TimeoutError) as exc:
        # Temporary connectivity/DNS/timeout failures are integration
        # availability failures. Never turn them into a false Jev approval.
        result.update({
            "status": "unavailable_transport",
            "error": f"{type(exc).__name__}: {exc}",
            "publish": bool(deterministic_ok),
            "action": "local_gates_only",
            "confidence": 0.0,
            "jev_authoritative": False,
        })
    except Exception as exc:
        # Unexpected Jev failures remain fail-closed: do not claim Jev approval.
        result.update({
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "publish": False,
            "jev_authoritative": False,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps({"status": "module_ready", "api_configured": bool(os.getenv("JEV_API_KEY"))}, indent=2))
