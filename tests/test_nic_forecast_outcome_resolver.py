import importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("resolver",ROOT/"src/nic_forecast_outcome_resolver.py")
resolver=importlib.util.module_from_spec(spec); spec.loader.exec_module(resolver)

def test_unresolved_not_trusted():
    rows=[{"forecast_id":str(i),"resolved":True,"side":"BULLISH","feature":"trend_aligned","regime":"TREND_UP","hit":True,"signed_return":1,"horizon_hours":24} for i in range(29)]
    original=resolver.MATRIX
    try:
        resolver.MATRIX=ROOT/"data/live/_test_predictivity_matrix.json"
        resolver.rebuild(rows,[])
        import json
        matrix=json.loads(resolver.MATRIX.read_text())["matrix"]
        assert matrix == {}  # legacy resolved flags cannot enter prospective learning
    finally:
        try: resolver.MATRIX.unlink()
        except FileNotFoundError: pass
        resolver.MATRIX=original

def test_resolution_emits_event_without_mutating_snapshot():
    now=datetime.now(timezone.utc)
    source={"provider":"Binance Spot Market Data API","endpoint":"https://data-api.binance.vision/api/v3/klines","instrument":"TESTUSDT","interval":"1h","closed_candle_open_time":"2026-10-01T09:00:00Z","closed_candle_as_of":"2026-10-01T10:00:00Z","retrieved_at":"2026-10-01T10:00:01Z","strategy_spec_sha256":"a"*64}
    snap={"forecast_id":"A|1","timestamp":(now-timedelta(hours=25)).isoformat(),"horizon_hours":24,
          "entry_price":100,"symbol":"TEST","side":"BULLISH","regime":"TREND_UP","feature":"COMPOSITE",
          "validation_status":"PROSPECTIVE_FROZEN_SHADOW_COHORT_NOT_PROVEN","strategy_version":"NIC-PROSPECTIVE-CHAMPION-1.0",
          "strategy_spec_sha256":"a"*64,"source_provenance":source}
    before=dict(snap)
    def fake_fetch(symbol,start,end): return [[end-3600000,0,0,0,101,0,end-1]]
    new=resolver.resolve([snap],now=now,candle_fetcher=fake_fetch,existing_events=[])
    assert snap==before
    assert len(new)==1 and new[0]["event_type"]=="FORECAST_RESOLVED"
    assert new[0]["signed_return"]==1.0
    assert new[0]["strategy_spec_sha256"]=="a"*64
    assert new[0]["source_provenance"]["instrument"]=="TESTUSDT"

def test_legacy_resolved_snapshot_never_becomes_terminal_event():
    snap={"forecast_id":"legacy","resolved":True,"signed_return":99,"side":"BULLISH","horizon_hours":6}
    assert resolver.resolve([snap],now=datetime.now(timezone.utc),candle_fetcher=lambda *a: [],existing_events=[]) == []

def test_legacy_resolved_snapshot_never_becomes_terminal_event():
    snap={"forecast_id":"legacy","resolved":True,"signed_return":99,"side":"BULLISH","horizon_hours":6}
    assert resolver.resolve([snap],now=datetime.now(timezone.utc),candle_fetcher=lambda *a: [],existing_events=[]) == []

def test_duplicate_resolution_is_blocked():
    snap={"forecast_id":"A|2","timestamp":"2020-01-01T00:00:00+00:00","horizon_hours":24,
          "entry_price":100,"symbol":"TEST","side":"BEARISH"}
    existing=[{"event_type":"FORECAST_RESOLVED","forecast_id":"A|2","signed_return":-1}]
    assert resolver.resolve([snap],now=datetime.now(timezone.utc),candle_fetcher=lambda *a: [],existing_events=existing)==[]

if __name__=="__main__":
    test_unresolved_not_trusted();test_resolution_emits_event_without_mutating_snapshot();test_legacy_resolved_snapshot_never_becomes_terminal_event();test_duplicate_resolution_is_blocked()
    print("NIC forecast immutable outcome-event tests: PASS")
