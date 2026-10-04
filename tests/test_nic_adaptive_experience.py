import json, tempfile
from pathlib import Path
import src.nic_adaptive_experience as m

def test_engine_keeps_prediction_immutable(monkeypatch,tmp_path):
    ledger=tmp_path/'ledger.json'; out=tmp_path/'out.json'
    original={'prediction_id':'p1','setup_type':'BREAKOUT','side':'LONG','timeframe':'4H','market_regime':'TREND'}
    ledger.write_text(json.dumps({'predictions':[original],'outcomes':[{'prediction_id':'p1','result':'WIN'}]}))
    monkeypatch.setattr(m,'LEDGER',ledger); monkeypatch.setattr(m,'OUT',out)
    m.main(); result=json.loads(out.read_text())
    assert json.loads(ledger.read_text())['predictions'][0] == original
    assert result['profiles'][0]['wins']==1
