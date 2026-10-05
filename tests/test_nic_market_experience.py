import json, tempfile
from pathlib import Path
import src.nic_market_experience as m

def test_profile_and_calibration_are_bounded():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        ledger=root/"ledger.jsonl"; cal=root/"cal.json"; out=root/"out.json"
        lines=[]
        pred={"setup_type":"BREAKOUT","side":"LONG","timeframe":"1H","market_regime":"RISK_ON"}
        for i in range(25):
            lines.append(json.dumps({"record_type":"PREDICTION_SNAPSHOT","prediction_id":f"p{i}","prediction":pred}))
            lines.append(json.dumps({"record_type":"OUTCOME_EVENT","prediction_id":f"p{i}","event_id":f"e{i}","outcome":"WIN" if i<18 else "LOSS"}))
        ledger.write_text("\n".join(lines)+"\n")
        cal.write_text(json.dumps({"state":"CALIBRATED","recommended_probability_adjustment":0.7}))
        old=(m.LEDGER,m.CAL,m.OUT)
        try:
            m.LEDGER,m.CAL,m.OUT=ledger,cal,out
            d=m.build()
        finally:
            m.LEDGER,m.CAL,m.OUT=old
        p=d["profiles"][0]
        assert p["samples"]==25 and p["empirical_win_rate"]==0.72
        assert d["probability_calibration"]["recommended_adjustment"]==0.1

if __name__=="__main__":
    test_profile_and_calibration_are_bounded()
    print("NIC market experience test passed")
