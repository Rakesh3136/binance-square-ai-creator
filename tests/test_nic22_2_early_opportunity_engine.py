import importlib.util
from pathlib import Path

p=Path("src/nic22_2_early_opportunity_engine.py")
spec=importlib.util.spec_from_file_location("nic22_2",p)
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)

def test_extension_penalty():
    base={"discovery_score":80,"volume_acceleration":2,"volume_vs_24h_median":2,"relative_strength_24h":3,"oi_change_3h_pct":3,"breakout_distance_pct":3}
    early=dict(base,price_change_percent=2)
    late=dict(base,price_change_percent=12)
    assert n.early_score(early) > n.early_score(late)

def test_contracts():
    assert n.MAX_PRICE_MOVE == 5.0
    assert n.MIN_VOLUME_ACCEL == 1.25
    assert n.SELECTION.as_posix()=="data/live/nic22_2_early_selection.json"
    assert n.OUT.as_posix()=="data/live/nic22_2_early_opportunities.json"

def test_scanner_keeps_moderate_participation_early():
    scanner_path=Path("src/full_universe_flow_scanner.py")
    sspec=importlib.util.spec_from_file_location("full_scanner",scanner_path)
    scanner=importlib.util.module_from_spec(sspec);sspec.loader.exec_module(scanner)
    state,_=scanner.classify({
        "symbol":"TEST",
        "price_change_percent":2.5,
        "volume_acceleration":1.2,
        "volume_vs_24h_median":1.2,
        "oi_change_3h_pct":0,
        "breakout_distance_pct":4,
        "discovery_score":40,
        "close_position_6h":0.6,
    },{})
    assert state=="EARLY"

def test_scanner_still_rejects_extended_move_as_early():
    scanner_path=Path("src/full_universe_flow_scanner.py")
    sspec=importlib.util.spec_from_file_location("full_scanner",scanner_path)
    scanner=importlib.util.module_from_spec(sspec);sspec.loader.exec_module(scanner)
    state,_=scanner.classify({
        "symbol":"TEST",
        "price_change_percent":6.1,
        "volume_acceleration":2,
        "volume_vs_24h_median":2,
        "oi_change_3h_pct":2,
        "breakout_distance_pct":4,
        "discovery_score":80,
        "close_position_6h":0.8,
    },{})
    assert state=="LATE"

if __name__=="__main__":
    test_extension_penalty();test_contracts();test_scanner_keeps_moderate_participation_early();test_scanner_still_rejects_extended_move_as_early();print("NIC22.2 tests passed")
