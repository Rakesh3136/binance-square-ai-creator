import json
import sys
import tempfile
from pathlib import Path

# When GitHub Actions runs `python tests/test_*.py`, Python puts `tests/` first
# on sys.path. Add the repository root explicitly so the namespace package
# `src` is importable in direct-script execution as well as local runs.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.nic_adaptive_experience as m


def test_engine_keeps_prediction_immutable():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ledger = root / "ledger.jsonl"
        out = root / "out.json"
        original = {
            "prediction_id": "p1",
            "setup_type": "BREAKOUT",
            "side": "LONG",
            "timeframe": "4H",
            "market_regime": "TREND",
        }
        snapshot = {
            "record_type": "PREDICTION_SNAPSHOT",
            "prediction_id": "p1",
            "prediction": original,
        }
        outcome = {
            "record_type": "OUTCOME_EVENT",
            "prediction_id": "p1",
            "outcome": "WIN",
            "event_id": "e1",
        }
        ledger.write_text(
            json.dumps(snapshot) + "\n" + json.dumps(outcome) + "\n",
            encoding="utf-8",
        )
        old_ledger, old_out = m.LEDGER, m.OUT
        try:
            m.LEDGER, m.OUT = ledger, out
            m.main()
        finally:
            m.LEDGER, m.OUT = old_ledger, old_out
        result = json.loads(out.read_text(encoding="utf-8"))
        assert json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])["prediction"] == original
        assert result["profiles"][0]["wins"] == 1
        assert result["profiles"][0]["samples"] == 1


if __name__ == "__main__":
    test_engine_keeps_prediction_immutable()
    print("NIC adaptive experience test passed")
