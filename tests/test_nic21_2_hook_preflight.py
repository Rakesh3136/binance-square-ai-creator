import json, os, tempfile
from pathlib import Path
import sys
sys.path.insert(0, "src")
import nic21_2_hook_preflight as h

def test_sentence_metrics():
    assert len(h.words("The BTC move is 4.2% and the next reaction matters.")) >= 8
    assert h.jac("BTC move today", "BTC move today") == 1.0

def test_no_safe_invention():
    assert h.MIN_HOOK_WORDS == 8
    assert h.MAX_SIMILARITY < 0.8

def test_resolve_explicit(tmp_path, monkeypatch):
    p=tmp_path/"draft.json"
    p.write_text(json.dumps({"draft":{"post":"A sufficiently detailed opening sentence with BTC and 4.2% today. Another sentence follows with context."}}))
    monkeypatch.setenv("DRAFT_PATH",str(p))
    assert h.resolve() == p

if __name__=="__main__":
    test_sentence_metrics(); test_no_safe_invention()
    print("NIC21.2 unit tests passed")
