import json
import subprocess
import sys
from pathlib import Path

def test_calibration_is_shadow_and_immutable(tmp_path):
    live=tmp_path/'data/live'; live.mkdir(parents=True)
    decision={"decision":"WATCH","symbol":"TEST","primary_direction":"LONG","fusion_score":72,"generated_at":"2026-10-05T10:00:00+00:00"}
    (live/'nic23_5_counterfactual_challenge.json').write_text(json.dumps(decision))
    src=Path('src/nic23_6_decision_calibration.py').read_text()
    src=src.replace('ROOT=Path(__file__).resolve().parents[1]',f'ROOT=Path({str(tmp_path)!r})')
    p=tmp_path/'cal.py'; p.write_text(src)
    subprocess.run([sys.executable,str(p)],check=True)
    report=json.loads((live/'nic23_6_calibration_report.json').read_text())
    assert report['status']=='SHADOW'
    assert report['live_weights_changed'] is False
    assert report['publication_gate_changed'] is False
    ledger=(live/'nic23_6_decision_ledger.jsonl').read_text().splitlines()
    assert len(ledger)==1
    assert json.loads(ledger[0])['immutable'] is True
