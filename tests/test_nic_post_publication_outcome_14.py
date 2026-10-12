import json, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"src/nic_post_publication_outcome_14.py"
def module():
 ns={"__file__":str(SRC),"__name__":"nic_post_publication_outcome_14_test"}; exec(SRC.read_text(encoding="utf-8"),ns); return ns
def test_syntax(): subprocess.run([sys.executable,"-m","py_compile",str(SRC)],check=True)
def test_ids():
 ns=module()
 assert ns["pid"]({"post_id":"12345"})=="12345"
 assert ns["pid"]({"post_id":"https://www.binance.com/en/square/post/ABC_9"})=="abc_9"
 assert ns["pid"]({"link":"https://app.binance.com/uni-qr/cpos/376357440894054?r=abc"})=="376357440894054"
def test_nested_metrics():
 assert module()["metric_snapshot"]({"metrics":{"views":120,"likes":9,"comments":3,"shares":2,"quotes":1}})=={"views":120,"likes":9,"replies":3,"shares":2,"quotes":1}
def test_flat_metrics():
 assert module()["metric_snapshot"]({"views":"7","replies":2,"followers_gained":1})=={"views":7,"replies":2,"followers_gained":1}
def test_unknown_metrics():
 assert module()["metric_snapshot"]({"metrics":{"views":"unknown","likes":None}})=={}
def test_newest_snapshot_wins():
 ns=module()
 with tempfile.TemporaryDirectory() as td:
  p=Path(td)/"metrics.jsonl"; p.write_text(json.dumps({"post_id":"123","collected_at":"2026-10-12T01:00:00Z","metrics":{"views":10}})+"\n"+json.dumps({"post_id":"123","collected_at":"2026-10-12T02:00:00Z","metrics":{"views":20}})+"\n",encoding="utf-8")
  assert ns["newest_metric_rows"]((p,))["123"]["_normalized_metrics"]["views"]==20
if __name__=="__main__":
 test_syntax(); test_ids(); test_nested_metrics(); test_flat_metrics(); test_unknown_metrics(); test_newest_snapshot_wins()
 print(json.dumps({"status":"PASS","tests":6}))
