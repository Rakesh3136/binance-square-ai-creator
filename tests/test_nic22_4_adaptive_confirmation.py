import json
import subprocess
import sys
from pathlib import Path
import tempfile

SCRIPT=Path("src/nic22_4_adaptive_confirmation.py")

def run(payload, watch):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        (root/"data/live").mkdir(parents=True)
        (root/"data/live/nic22_3_early_confirmation.json").write_text(json.dumps(payload))
        (root/"data/live/nic22_3_developing_watch.json").write_text(json.dumps(watch))
        # Execute from repository source while redirecting paths via a temporary
        # copy of the small controller.
        copy=root/"controller.py"
        text=SCRIPT.read_text(encoding="utf-8").replace(
            'CONFIRMATION=Path("data/live/nic22_3_early_confirmation.json")',
            f'CONFIRMATION=Path({str(root/"data/live/nic22_3_early_confirmation.json")!r})'
        ).replace(
            'WATCH=Path("data/live/nic22_3_developing_watch.json")',
            f'WATCH=Path({str(root/"data/live/nic22_3_developing_watch.json")!r})'
        ).replace(
            'OUT=Path("data/live/nic22_4_adaptive_confirmation.json")',
            f'OUT=Path({str(root/"data/live/nic22_4_adaptive_confirmation.json")!r})'
        )
        copy.write_text(text)
        r=subprocess.run([sys.executable,str(copy)],capture_output=True,text=True)
        assert r.returncode==0, r.stderr
        return json.loads((root/"data/live/nic22_4_adaptive_confirmation.json").read_text())

def test_near_miss_authorizes_one_recheck_without_lowering_threshold():
    out=run(
        {"near_miss":True,"confirmation_score":54,"selected_opportunity":None},
        {"symbol":"BTC","status":"WATCH_ONLY"}
    )
    assert out["status"]=="RECHECK_AUTHORIZED"
    assert out["symbol"]=="BTC"
    assert out["recheck_count"]==1
    assert out["policy"]["threshold_unchanged"] is True
    assert out["policy"]["no_threshold_lowering"] is True

def test_weak_setup_is_not_rechecked():
    out=run(
        {"near_miss":False,"confirmation_score":42,"selected_opportunity":None},
        {"symbol":"BTC","status":"WATCH_ONLY"}
    )
    assert out["status"]=="NO_RECHECK"
