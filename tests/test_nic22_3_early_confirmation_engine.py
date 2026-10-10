import importlib.util
from pathlib import Path

p=Path("src/nic22_3_early_confirmation_engine.py")
spec=importlib.util.spec_from_file_location("nic22_3",p)
n=importlib.util.module_from_spec(spec); spec.loader.exec_module(n)

def test_requires_multiple_independent_signals():
    c={"price_change_percent":2,"volume_acceleration":2,"volume_vs_24h_median":2,
       "relative_strength_24h":2,"oi_change_3h_pct":2,"breakout_distance_pct":2,
       "discovery_score":70}
    score,signals,breakdown=n.confirm_score(c)
    assert score >= n.MIN_SCORE
    assert len(signals) >= n.MIN_SIGNALS
    assert breakdown["volume_acceleration"] == 15

def test_extended_move_is_not_confirmed_early():
    c={"price_change_percent":8,"volume_acceleration":3,"volume_vs_24h_median":3,
       "relative_strength_24h":4,"oi_change_3h_pct":4,"breakout_distance_pct":1,
       "discovery_score":90,"flow_state":"LATE"}
    selected,near,evaluated=n.evaluate_candidates([c])
    assert selected is None
    assert near is None
    assert evaluated[0]["confirmation_eligible"] is False

def test_near_miss_contract():
    c={"price_change_percent":2,"volume_acceleration":1.5,"volume_vs_24h_median":1.2,
       "relative_strength_24h":0.5,"oi_change_3h_pct":1,"breakout_distance_pct":5,
       "discovery_score":50}
    score,signals,breakdown=n.confirm_score(c)
    assert 50 <= score < n.MIN_SCORE
    assert len(signals) >= n.MIN_SIGNALS
    assert n.NEAR_MISS_MIN_SCORE == 50.0
    assert sum(breakdown.values()) == score
    assert score == 56.0

def test_ranked_queue_selects_confirmed_candidate_below_weak_top_pick():
    weak={"symbol":"WEAK","flow_state":"EARLY","price_change_percent":1.5,
          "volume_acceleration":1.1,"volume_vs_24h_median":1.0,"relative_strength_24h":0.1,
          "oi_change_3h_pct":0,"breakout_distance_pct":8,"discovery_score":40,"adjusted_score":99}
    strong={"symbol":"STRONG","flow_state":"DEVELOPING","price_change_percent":2,
            "volume_acceleration":2,"volume_vs_24h_median":2,"relative_strength_24h":2,
            "oi_change_3h_pct":2,"breakout_distance_pct":2,"discovery_score":70,"adjusted_score":70}
    selected,near,evaluated=n.evaluate_candidates([weak,strong])
    assert len(evaluated)==2
    assert selected is not None
    assert selected["symbol"]=="STRONG"
    assert selected["confirmation_status"]=="CONFIRMED_EARLY_SETUP"
    assert near is None

def test_extended_candidate_never_becomes_near_miss_or_confirmed():
    extended={"symbol":"PUMPED","flow_state":"LATE","price_change_percent":9,
              "volume_acceleration":3,"volume_vs_24h_median":3,"relative_strength_24h":4,
              "oi_change_3h_pct":4,"breakout_distance_pct":1,"discovery_score":90}
    early={"symbol":"WATCH","flow_state":"EARLY","price_change_percent":2,
           "volume_acceleration":1.5,"volume_vs_24h_median":1.2,"relative_strength_24h":0.5,
           "oi_change_3h_pct":1,"breakout_distance_pct":5,"discovery_score":50}
    selected,near,evaluated=n.evaluate_candidates([extended,early])
    assert selected is None
    assert near is not None and near["symbol"]=="WATCH"
    assert evaluated[0]["confirmation_eligible"] is False

def test_contracts():
    assert n.MIN_SCORE == 60.0
    assert n.MIN_SIGNALS == 4
    assert n.SELECTION.as_posix()=="data/live/nic22_3_confirmation_selection.json"
    assert n.NEAR_MISS.as_posix()=="data/live/nic22_3_near_miss.json"

if __name__=="__main__":
    test_requires_multiple_independent_signals()
    test_extended_move_is_not_confirmed_early()
    test_near_miss_contract()
    test_ranked_queue_selects_confirmed_candidate_below_weak_top_pick()
    test_extended_candidate_never_becomes_near_miss_or_confirmed()
    test_contracts()
    print("NIC22.3 ranked confirmation tests passed")
