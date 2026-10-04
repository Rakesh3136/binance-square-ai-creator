import json, subprocess, sys, tempfile
from pathlib import Path

SCRIPT=Path("src/nic22_5_publication_eligibility.py")

def run(files):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"data/live").mkdir(parents=True)
        replacements={}
        for name,payload in files.items():
            path=root/"data/live"/name
            path.write_text(json.dumps(payload))
            replacements[name]=str(path)
        out=root/"data/live/nic22_5_publication_eligibility.json"
        text=SCRIPT.read_text()
        for name, path in replacements.items():
            const={"nic22_3_confirmation_selection.json":"CONFIRMATION","nic22_4_adaptive_confirmation.json":"ADAPTIVE","original_research.json":"RESEARCH","content_director_brief.json":"DIRECTOR"}[name]
            text=text.replace(f'{const}=LIVE/"{name}"',f'{const}=Path({path!r})')
        text=text.replace('OUT=LIVE/"nic22_5_publication_eligibility.json"',f'OUT=Path({str(out)!r})')
        copy=root/"controller.py"; copy.write_text(text)
        r=subprocess.run([sys.executable,str(copy)],capture_output=True,text=True)
        assert r.returncode==0,r.stderr
        return json.loads(out.read_text())

def base_research():
    return {"generated_at":"2026-10-04T23:59:00+00:00","potential_gems":[{"symbol":"ABC","information_advantage_score":80,"undercoverage_score":70,"evidence_score":60,"missing_evidence":[]}]}

def test_confirmed_trade_wins():
    out=run({
      "nic22_3_confirmation_selection.json":{"status":"CONFIRMED","selected_opportunity":{"symbol":"BTC"}},
      "nic22_4_adaptive_confirmation.json":{},
      "original_research.json":base_research(),
      "content_director_brief.json":{"generated_at":"2026-10-04T23:59:00+00:00"}
    })
    assert out["eligible"] is True and out["publication_mode"]=="TRADE" and out["trade_authorized"] is True

def test_editorial_research_can_publish_without_trade():
    out=run({
      "nic22_3_confirmation_selection.json":{"status":"BLOCKED"},
      "nic22_4_adaptive_confirmation.json":{"status":"NO_RECHECK"},
      "original_research.json":base_research(),
      "content_director_brief.json":{"generated_at":"2026-10-04T23:59:00+00:00"}
    })
    assert out["eligible"] is True and out["publication_mode"]=="EDITORIAL" and out["trade_authorized"] is False

def test_stale_research_cannot_authorize():
    out=run({
      "nic22_3_confirmation_selection.json":{"status":"BLOCKED"},
      "nic22_4_adaptive_confirmation.json":{"status":"NO_RECHECK"},
      "original_research.json":{**base_research(),"generated_at":"2020-01-01T00:00:00+00:00"},
      "content_director_brief.json":{"generated_at":"2026-10-04T23:59:00+00:00"}
    })
    assert out["eligible"] is False and out["publication_mode"]=="BLOCKED"
