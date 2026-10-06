import importlib.util
from pathlib import Path

p=Path("src/opportunity_timing_gate.py")
s=importlib.util.spec_from_file_location("timing",p)
t=importlib.util.module_from_spec(s); s.loader.exec_module(t)

def test_late_move_blocked_for_trade():
    r=t.evaluate({"symbol":"PUMP","category":"capital_flow_long","price_change_percent":9},
                 {"flow_state":"LATE","breakout_distance_pct":1,"volume_acceleration":3}, {})
    assert r["timing_state"]=="LATE"
    assert r["allowed"] is False

def test_exhausted_move_blocked():
    r=t.evaluate({"symbol":"PUMP","category":"capital_flow_short","price_change_percent":14}, {}, {})
    assert r["timing_state"]=="EXHAUSTED"
    assert r["allowed"] is False

def test_early_setup_allowed():
    r=t.evaluate({"symbol":"EARLY","category":"capital_flow_long","price_change_percent":2},
                 {"flow_state":"EARLY","breakout_distance_pct":4,"volume_acceleration":1.6}, {})
    assert r["timing_state"]=="EARLY"
    assert r["allowed"] is True

def test_confirming_setup_allowed():
    r=t.evaluate({"symbol":"CONF","category":"capital_flow_long","price_change_percent":4},
                 {"flow_state":"CONFIRMED","breakout_distance_pct":3,"volume_acceleration":2}, {})
    assert r["timing_state"]=="CONFIRMING"
    assert r["allowed"] is True

def test_post_move_editorial_is_not_a_fresh_trade():
    r=t.evaluate({"symbol":"PUMP","category":"research_insight","price_change_percent":12}, {}, {})
    assert r["timing_state"]=="EXHAUSTED"
    assert r["allowed"] is True
    assert r["publication_mode"]=="EDITORIAL_POST_MOVE"

if __name__=="__main__":
    test_late_move_blocked_for_trade()
    test_exhausted_move_blocked()
    test_early_setup_allowed()
    test_confirming_setup_allowed()
    test_post_move_editorial_is_not_a_fresh_trade()
    print("Opportunity timing gate tests passed")
