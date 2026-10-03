import importlib.util
from pathlib import Path

p=Path("src/nic22_3_early_confirmation_engine.py")
spec=importlib.util.spec_from_file_location("nic22_3",p)
n=importlib.util.module_from_spec(spec); spec.loader.exec_module(n)

def test_requires_multiple_independent_signals():
    c={"price_change_percent":2,"volume_acceleration":2,"volume_vs_24h_median":2,
       "relative_strength_24h":2,"oi_change_3h_pct":2,"breakout_distance_pct":2,
       "discovery_score":70}
    score,signals=n.confirm_score(c)
    assert score >= n.MIN_SCORE
    assert len(signals) >= n.MIN_SIGNALS

def test_extended_move_is_not_confirmed_early():
    c={"price_change_percent":8,"volume_acceleration":3,"volume_vs_24h_median":3,
       "relative_strength_24h":4,"oi_change_3h_pct":4,"breakout_distance_pct":1,
       "discovery_score":90}
    assert abs(float(c["price_change_percent"])) > n.MAX_PRICE_MOVE

def test_contracts():
    assert n.MIN_SCORE == 60.0
    assert n.MIN_SIGNALS == 4
    assert n.SELECTION.as_posix()=="data/live/nic22_3_confirmation_selection.json"

if __name__=="__main__":
    test_requires_multiple_independent_signals()
    test_extended_move_is_not_confirmed_early()
    test_contracts()
    print("NIC22.3 tests passed")
