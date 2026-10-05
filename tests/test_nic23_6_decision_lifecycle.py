import json,subprocess,sys,tempfile
from pathlib import Path

def run(decision):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); live=root/'data/live'; live.mkdir(parents=True)
        (live/'nic23_4_decision_fusion.json').write_text(json.dumps(decision))
        text=Path('src/nic23_6_decision_lifecycle.py').read_text()
        text=text.replace('ROOT=Path(__file__).resolve().parents[1]',f'ROOT=Path({str(root)!r})')
        p=root/'x.py'; p.write_text(text)
        r=subprocess.run([sys.executable,str(p)],capture_output=True,text=True); assert r.returncode==0,r.stderr
        return json.loads((live/'nic23_6_calibration.json').read_text()),live

def test_fresh_decision_is_ledgered():
    from datetime import datetime,timezone
    out,live=run({'generated_at':datetime.now(timezone.utc).isoformat(),'symbol':'BTC','decision':'WATCH','fusion_score':62})
    assert out['status']=='VERIFIED' and out['shadow_only'] is True
    assert (live/'nic23_6_decision_ledger.jsonl').exists()

def test_stale_decision_is_not_ledgered():
    out,live=run({'generated_at':'2000-01-01T00:00:00+00:00','symbol':'BTC','decision':'TRADE','fusion_score':99})
    assert out['status']=='NOT_APPLICABLE'
    assert not (live/'nic23_6_decision_ledger.jsonl').exists()
