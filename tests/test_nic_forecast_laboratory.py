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
         "market_data_provenance":{"provider":"Binance Spot Market Data API","endpoint":"https://data-api.binance.vision/api/v3/klines",
           "instrument":"TESTUSDT","interval":"1h","closed_candle_open_time":"2026-10-11T09:00:00+00:00",
           "closed_candle_as_of":"2026-10-11T10:00:00+00:00","retrieved_at":"2026-10-11T10:00:01+00:00",
           "source_policy":"closed_1h_only","strategy_spec_sha256":m.STRATEGY_SPEC_SHA256},
         "decision":"BULLISH","hypotheses":{}}
 for side in ("BULLISH","BEARISH"):
  result["hypotheses"][side]={"forward":{str(h):{"hit_rate":.61 if side=="BULLISH" else .39} for h in (6,12,24)}}
 rows=m.make_snapshots("TEST",result)
 assert len(rows)==6
 assert len({x["forecast_id"] for x in rows})==6
 assert {x["horizon_hours"] for x in rows}=={6,12,24}
 assert all("feature_flags" in x and x["feature"]=="COMPOSITE" for x in rows)
 assert all(x["validation_status"]=="PROSPECTIVE_FROZEN_SHADOW_COHORT_NOT_PROVEN" for x in rows)
 assert all(x["strategy_version"]==m.STRATEGY_VERSION and x["strategy_spec_sha256"]==m.STRATEGY_SPEC_SHA256 for x in rows)
 assert all(x["source_provenance_required"] is True for x in rows)
 assert all(x["source_provenance"]["provider"]=="Binance Spot Market Data API" for x in rows)
 assert all(x["source_provenance"]["endpoint"].endswith("/api/v3/klines") for x in rows)
 assert all(x["source_provenance"]["closed_candle_as_of"]==result["as_of"] for x in rows)
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

if __name__=="__main__": test_regime();test_wait();test_signal_audit_contract();test_open_hourly_candle_is_excluded();test_one_snapshot_per_side_horizon_not_per_feature();test_persistence_verification_fails_when_expected_id_is_absent();print("Forecast Laboratory learning tests passed")

