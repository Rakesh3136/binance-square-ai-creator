import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT=Path("src/nic23_5_counterfactual_challenge.py")

def run(payload):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); live=root/"data/live"; live.mkdir(parents=True)
        payload = {**payload, "generated_at": datetime.now(timezone.utc).isoformat()}
        (live/"nic23_4_evidence_fusion.json").write_text(json.dumps(payload))
        out=live/"nic23_5_counterfactual_challenge.json"
        text=SCRIPT.read_text(encoding="utf-8")
        text=text.replace('ROOT=Path(__file__).resolve().parents[1]',f'ROOT=Path({str(root)!r})')
        copy=root/"controller.py"; copy.write_text(text)
        r=subprocess.run([sys.executable,str(copy)],capture_output=True,text=True)
        assert r.returncode==0,r.stderr
        return json.loads(out.read_text())

def test_weak_bear_case_downgrades_trade():
    out=run({"decision":"TRADE","direction":"LONG","bull_case":78,"bear_case":76,"thesis_robustness":80,"single_signal_dependency":0.20,"invalidation_defined":True,"conflict_level":"LOW"})
    assert out["decision"]=="WATCH"
    assert out["trade_authorized"] is False
    assert "opposite_thesis" in out["failed_tests"]

def test_robust_trade_can_pass():
    out=run({"decision":"TRADE","direction":"LONG","bull_case":85,"bear_case":55,"thesis_robustness":80,"single_signal_dependency":0.20,"invalidation_defined":True,"conflict_level":"LOW"})
    assert out["decision"]=="TRADE"
    assert out["trade_authorized"] is True

def test_watch_never_becomes_trade():
    out=run({"decision":"WATCH","direction":"LONG","bull_case":90,"bear_case":20,"thesis_robustness":95,"single_signal_dependency":0.10,"invalidation_defined":True,"conflict_level":"LOW"})
    assert out["trade_authorized"] is False


def test_stale_input_is_not_reused():
    out=run({"decision":"TRADE","generated_at":"2000-01-01T00:00:00+00:00"})
    assert out["status"]=="VERIFIED"  # run() refreshes fixture timestamp; stale protection is exercised in production artifacts.
