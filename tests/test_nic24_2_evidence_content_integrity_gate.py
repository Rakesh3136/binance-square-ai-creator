from __future__ import annotations
import json, os, tempfile
from pathlib import Path
import subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
GATE=ROOT/"src/nic24_2_evidence_content_integrity_gate.py"

def run_case(post, frozen, enforce="true", technical_levels=None):
    with tempfile.TemporaryDirectory() as td:
        report=Path(td)/"draft.json"
        report.write_text(json.dumps({"draft":{"post":post,"symbol":frozen.get("symbol")}}),encoding="utf-8")
        live=ROOT/"data/live"
        live.mkdir(parents=True,exist_ok=True)
        names={
            "authoritative_opportunity.json":frozen,
            "publication_context.json":{"symbol":frozen.get("symbol",""),"chart_symbols":[frozen.get("symbol","")],"visual_decision":{"timeframe":"1H"}},
            "editorial_preflight.json":{"selected_opportunity":{"symbol":frozen.get("symbol","")}},
            "nic24_regime_strategy_router.json":{"generated_at":"2099-01-01T00:00:00+00:00","routes":[{"symbol":frozen.get("symbol",""),"regime":"TREND_CONTINUATION"}]},
            "nic24_1_strategy_content_plan.json":{"generated_at":"2099-01-01T00:00:00+00:00","plans":[{"symbol":frozen.get("symbol",""),"regime":"TREND_CONTINUATION"}]},
            "nic_prediction_engine.json":{"generated_at":"2099-01-01T00:00:00+00:00"},
            "market_snapshot.json":{"generated_at":"2099-01-01T00:00:00+00:00"},
        }
        old={}
        for name,value in names.items():
            p=live/name
            old[name]=p.read_text(encoding="utf-8") if p.exists() else None
            p.write_text(json.dumps(value),encoding="utf-8")
        env=dict(os.environ,DRAFT_PATH=str(report),NIC24_2_ENFORCE=enforce,NIC24_2_MAX_MARKET_AGE_MINUTES="100000")
        try:
            return subprocess.run([sys.executable,str(GATE)],cwd=ROOT,env=env,capture_output=True,text=True)
        finally:
            for name,value in old.items():
                p=live/name
                if value is None: p.unlink(missing_ok=True)
                else: p.write_text(value,encoding="utf-8")

def test_pass():
    r=run_case("BTC is consolidating near support. The invalidation is $90000?",{"symbol":"BTC","category":"technical_setup","direction":"LONG","invalidation":90000,"not_a_guarantee":True})
    assert r.returncode==0,r.stdout+r.stderr

def test_foreign_coin():
    r=run_case("BTC is the setup, while $ETH may outperform?",{"symbol":"BTC","category":"technical_setup","direction":"LONG"})
    assert r.returncode==24,r.stdout+r.stderr

def test_number_drift():
    r=run_case("BTC setup: entry $95000, then reassess?",{"symbol":"BTC","category":"technical_setup","direction":"LONG","entry_trigger":94000})
    assert r.returncode==24,r.stdout+r.stderr

def test_watch_only():
    r=run_case("BTC is WATCH_ONLY but the long entry is ready?",{"symbol":"BTC","category":"technical_setup","decision":"WATCH_ONLY"})
    assert r.returncode==24,r.stdout+r.stderr

def test_certainty():
    r=run_case("BTC will rise, guaranteed, if momentum continues?",{"symbol":"BTC","category":"technical_setup","direction":"LONG"})
    assert r.returncode==24,r.stdout+r.stderr

def test_technical_enrichment_handoff():
    levels={"current_price":0.06863,"support":0.04829,"resistance":0.07162,
            "tp1":0.0774525,"target":0.083285,"invalidation":0.04829,
            "direction":"LONG_BIAS","timeframe":"1H"}
    post=("STRK current price $0.06863; support $0.04829; resistance $0.07162; "
          "TP1 $0.0774525; target $0.083285; invalidation $0.04829.")
    r=run_case(post,{"symbol":"STRK","category":"technical_setup","direction":"LONG_BIAS"},
               technical_levels=levels)
    assert r.returncode==0,r.stdout+r.stderr

if __name__=="__main__":
    test_pass();test_foreign_coin();test_number_drift();test_watch_only();test_certainty();test_technical_enrichment_handoff()
    print("NIC 24.2 tests passed")
