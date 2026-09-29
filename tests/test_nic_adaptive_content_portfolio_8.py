"""Regression tests for NIC Adaptive Content Portfolio 8.0."""
import json, tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import nic_adaptive_content_portfolio_8 as p

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); p.LIVE=root/"live"; p.INTEL=root/"intel"; p.ATTR=p.LIVE/"attr.json"
        p.LIVE.mkdir(); p.INTEL.mkdir()
        p.ATTR.write_text(json.dumps({"learning":{"lane_priors":[
            {"lane":"data_investigation","verified_rewards":2,"verified_revenue_usdc":4},
            {"lane":"market_setup","verified_rewards":0,"verified_revenue_usdc":0}
        ]}}))
        p.main()
        out=json.loads(p.OUT.read_text())
        assert len(out["allocations"])==len(p.LANES)
        assert out["allocations"][0]["lane"]=="data_investigation"
        assert all(x["target_share"]>0 for x in out["allocations"])
        assert out["policy"]["unknown_is_not_negative"] is True
        # Portfolio must never become permission to publish.
        assert out["policy"]["portfolio_is_allocation_guidance_not_publish_permission"] is True
    print(json.dumps({"status":"PASS","checks":["verified_signal_bias","exploration_floor","unknown_is_not_negative","no_publish_permission"]}))
if __name__=="__main__": main()
