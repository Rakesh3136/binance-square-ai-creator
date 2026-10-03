from pathlib import Path
import importlib.util
import json

SPEC=importlib.util.spec_from_file_location("monitor",Path("src/nic22_3_2_developing_setup_monitor.py"))
M=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)


def test_watch_only_and_no_publication(tmp_path):
    confirmation=tmp_path/"confirmation.json"
    early=tmp_path/"early.json"
    watch=tmp_path/"watch.json"
    history=tmp_path/"history.json"
    M.CONFIRMATION=confirmation; M.EARLY=early; M.WATCH=watch; M.HISTORY=history
    confirmation.write_text(json.dumps({
        "status":"BLOCKED","confirmation_score":46.0,
        "selected_opportunity":None,
        "observed_signals":["volume_acceleration","volume_vs_24h_median","relative_strength","breakout_proximity"],
        "score_breakdown":{"volume_acceleration":15,"volume_vs_24h_median":12,"relative_strength":12,"breakout_proximity":7},
    }))
    early.write_text(json.dumps({"selected_opportunity":{"symbol":"TESTUSDT","price_change_percent":1.2}}))
    assert M.main()==0
    out=json.loads(watch.read_text())
    assert out["status"]=="WATCH_ONLY"
    assert out["publication_allowed"] is False
    assert out["recheck_on_next_cycle"] is True
