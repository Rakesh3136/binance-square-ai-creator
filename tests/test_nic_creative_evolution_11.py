import json, tempfile
from pathlib import Path
import sys
sys.path.insert(0,"src")
import nic_creative_evolution_11 as m

def test_fingerprint_stable():
    a={"content_lane":"market_setup","content_format":"decision_chart","hook_type":"x","visual_type":"structure"}
    assert m.fp(a)[0]==m.fp(a)[0]

def test_unattributed_reward_stays_unattributed(tmp_path,monkeypatch):
    monkeypatch.setattr(m,"AN",tmp_path)
    monkeypatch.setattr(m,"LIVE",tmp_path/"live")
    monkeypatch.setattr(m,"INTEL",tmp_path/"intel")
    monkeypatch.setattr(m,"ATTR",tmp_path/"publication_attribution.jsonl")
    monkeypatch.setattr(m,"PUB",tmp_path/"publication_log.jsonl")
    monkeypatch.setattr(m,"REW",tmp_path/"wte_reward_events.jsonl")
    monkeypatch.setattr(m,"EXT",tmp_path/"external_reward_events.jsonl")
    monkeypatch.setattr(m,"OUT",tmp_path/"live/nic_creative_evolution_11.json")
    monkeypatch.setattr(m,"REPORT",tmp_path/"intel/nic_creative_evolution_11_report.json")
    m.AN.mkdir(); (tmp_path/"live").mkdir(); (tmp_path/"intel").mkdir()
    (tmp_path/"wte_reward_events.jsonl").write_text(json.dumps({"event_id":"r1","verified":True,"reward_amount_usdc":0.1})+"\n")
    (tmp_path/"publication_attribution.jsonl").write_text(json.dumps({"post_id":"123","published_at":"2026-09-01"})+"\n")
    m.main()
    state=json.loads((tmp_path/"live/nic_creative_evolution_11.json").read_text())
    assert state["summary"]["unattributed_verified_reward_events"]==1
    assert state["fingerprints"][0]["reward_state"]=="CLOSED_UNKNOWN"
