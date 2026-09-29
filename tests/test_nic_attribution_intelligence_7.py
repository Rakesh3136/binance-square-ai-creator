"""Regression tests for NIC Attribution Intelligence 7.0."""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import nic_attribution_intelligence_7 as nia

def write_jsonl(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        nia.ANALYTICS=root/"analytics"; nia.LIVE=root/"data/live"; nia.INTEL=root/"data/intelligence"
        nia.ATTR=nia.ANALYTICS/"publication_attribution.jsonl"
        nia.PERF=nia.ANALYTICS/"square_performance.jsonl"
        nia.REWARDS=nia.ANALYTICS/"wte_reward_events.jsonl"
        nia.OUT=nia.LIVE/"nic_attribution_intelligence_7.json"
        nia.LEDGER=nia.ANALYTICS/"nic_attribution_events.jsonl"
        nia.REPORT=nia.INTEL/"nic_attribution_intelligence_7_report.json"
        nia.STORY=nia.LIVE/"nic_story_discovery.json"

        write_jsonl(nia.ATTR,[{
            "canonical_post_id":"https://www.binance.com/square/post/ABC_123",
            "published_at":"2026-09-29T00:00:00+00:00",
            "symbol":"QNT","story_id":"story5-demo","story_type":"data_investigation",
            "content_lane":"data_investigation","content_format":"data_investigation",
            "hook_type":"data_contradiction","visual_type":"relationship_chart",
            "reader_payoff_type":"data_relationship","experiment_id":"exp-1"
        },{
            "canonical_post_id":"NO_REWARD","published_at":"2026-09-29T00:01:00+00:00",
            "symbol":"HBAR","story_id":"story5-demo2","content_lane":"market_setup"
        }])
        write_jsonl(nia.PERF,[{"post_id":"abc_123","views":1000,"likes":10,"comments":2}])
        write_jsonl(nia.REWARDS,[{"post_id":"abc_123","verified":True,"reward_amount_usdc":1.25,"source":"verified_test"}])
        nia.main()
        state=json.loads(nia.OUT.read_text())
        rows={x["post_id"]:x for x in state["posts"]}
        assert rows["abc_123"]["outcome_state"]=="VERIFIED_REWARD"
        assert rows["abc_123"]["verified_reward_usdc"]==1.25
        assert rows["abc_123"]["performance"]["views"]==1000
        assert rows["no_reward"]["outcome_state"]=="UNKNOWN"
        assert rows["no_reward"]["verified_reward_usdc"] is None
        assert state["summary"]["verified_reward_total_usdc"]==1.25
        # Running twice must not duplicate durable attribution events.
        nia.main()
        ledger=nia.LEDGER.read_text().splitlines()
        assert len(ledger)==2, ledger

        # A reward-looking performance metric can never become revenue.
        write_jsonl(nia.REWARDS,[{"post_id":"no_reward","verified":False,"reward_amount_usdc":999}])
        nia.main()
        state=json.loads(nia.OUT.read_text())
        rows={x["post_id"]:x for x in state["posts"]}
        assert rows["no_reward"]["outcome_state"]=="UNKNOWN"
        assert rows["no_reward"]["verified_reward_usdc"] is None

    print(json.dumps({"status":"PASS","checks":["canonical_join","verified_reward","unknown_reward","idempotent_ledger","no_inference_from_unverified_event"]},indent=2))
if __name__=="__main__":
    raise SystemExit(main())
