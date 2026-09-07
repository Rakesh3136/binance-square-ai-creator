import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "live" / "creator_21_0_editorial_state.json"
OUT = ROOT / "data" / "live" / "creator_21_0_quality_gate.json"

try:
    state = json.loads(STATE.read_text(encoding="utf-8"))
except Exception:
    state = {"decision": "RESEARCH_AND_WAIT"}

decision = state.get("decision", "RESEARCH_AND_WAIT")
result = {
    "version": "21.0",
    "publish_allowed_by_editorial_layer": decision == "PUBLISH_ONLY_STRONG_EDITORIAL_ANGLE",
    "decision": decision,
    "reason": "Allow publication only when Creator 21.0 has evidence for a strong editorial angle; all existing publication/safety gates remain authoritative.",
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
