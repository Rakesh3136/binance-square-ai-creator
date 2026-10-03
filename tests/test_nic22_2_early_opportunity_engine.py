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

if __name__=="__main__":
    test_extension_penalty();test_contracts();print("NIC22.2 tests passed")
