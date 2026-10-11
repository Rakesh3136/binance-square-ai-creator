import importlib.util,json
from pathlib import Path
s=importlib.util.spec_from_file_location("lab",Path("src/nic_forecast_laboratory.py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def test_regime():
 assert m.regime({"rsi":75,"momentum":8,"trend":1,"volume_ratio":1})=="TREND_UP_EXTENDED"
 assert m.regime({"rsi":25,"momentum":-8,"trend":-1,"volume_ratio":1})=="TREND_DOWN_EXTENDED"
 assert m.regime({"rsi":55,"momentum":2,"trend":1,"volume_ratio":1})=="TREND_UP"
def test_wait():
 assert m.summarize([1,-1])["hit_rate"]==.5
def test_signal_audit_contract():
 x=m.walkforward([{"c":100,"h":101,"l":99,"v":100}]*150,"BULLISH","volume_expansion")
 assert set(("feature","base","conditional","lift","eligible","predictive"))<=set(x)

def test_open_hourly_candle_is_excluded():
 now = 8 * 60 * 60 * 1000 + 30 * 60 * 1000
 rows = [
  {"t": 7 * 60 * 60 * 1000, "c": 1},
  {"t": 8 * 60 * 60 * 1000, "c": 2},
 ]
 closed = m.closed_candles(rows, now_ms=now)
 assert [x["c"] for x in closed] == [1]
 assert [x["c"] for x in m.closed_candles(rows, now_ms=8 * 60 * 60 * 1000)] == [1]

def test_one_snapshot_per_side_horizon_not_per_feature():
 result={"status":"READY","as_of":"2026-10-11T10:00:00+00:00","symbol":"TEST","regime":"RANGE",
         "current_features":{"price":100,"trend":1,"momentum":2,"rsi":55,"volume_ratio":1.4,"distance_ema20":1,"range_position":.6},
         "decision":"BULLISH","hypotheses":{}}
 for side in ("BULLISH","BEARISH"):
  result["hypotheses"][side]={"forward":{str(h):{"hit_rate":.61 if side=="BULLISH" else .39} for h in (6,12,24)}}
 rows=m.make_snapshots("TEST",result)
 assert len(rows)==6
 assert len({x["forecast_id"] for x in rows})==6
 assert {x["horizon_hours"] for x in rows}=={6,12,24}
 assert all("feature_flags" in x and x["feature"]=="COMPOSITE" for x in rows)
 assert all(x["validation_status"]=="LIVE_FORWARD_ONLY_NO_HISTORICAL_WALK_FORWARD_PROOF" for x in rows)
if __name__=="__main__": test_regime();test_wait();test_signal_audit_contract();test_open_hourly_candle_is_excluded();test_one_snapshot_per_side_horizon_not_per_feature();print("Forecast Laboratory learning tests passed")

def test_persistence_verification_fails_when_expected_id_is_absent():
 import tempfile
 with tempfile.TemporaryDirectory() as tmp:
  path=Path(tmp)/"truth.jsonl"
  path.write_text("",encoding="utf-8")
  try:
   m.verify_persisted_snapshots(path,[{"forecast_id":"missing-id"}])
  except RuntimeError as exc:
   assert "newly appended IDs are missing" in str(exc)
  else:
   raise AssertionError("Missing forecast ID must fail closed")
