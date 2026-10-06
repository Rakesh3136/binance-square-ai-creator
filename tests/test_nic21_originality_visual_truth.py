import json
from pathlib import Path


def test_nic21_module_has_hard_similarity_thresholds():
    from src import nic21_originality_visual_truth as n
    assert n.SIMILARITY_BLOCK < 1.0
    assert n.HOOK_BLOCK < 1.0
    assert n.STRUCTURE_BLOCK < 1.0
    assert n.CTA_BLOCK < 1.0


def test_jaccard_is_symmetric():
    from src.nic21_originality_visual_truth import jaccard
    assert jaccard("alpha beta gamma", "alpha beta") == jaccard("alpha beta", "alpha beta gamma")


def test_originality_blocks_near_duplicate(monkeypatch, tmp_path):
    from src import nic21_originality_visual_truth as n
    log = tmp_path / "publication_log.jsonl"
    log.write_text(json.dumps({"text": "BTC breaks above the level and the market waits for confirmation."}) + "\n", encoding="utf-8")
    monkeypatch.setattr(n, "PUBLICATION_LOG", log)
    result = n.originality("BTC breaks above the level and the market waits for confirmation.", "BTC")
    assert result["status"] == "FAIL"


def test_visual_truth_rejects_symbol_mismatch(monkeypatch, tmp_path):
    from src import nic21_originality_visual_truth as n
    meta = tmp_path / "visual_metadata.json"
    meta.write_text(json.dumps({"symbol": "BINANCE:ETHUSDT"}), encoding="utf-8")
    monkeypatch.setattr(n, "VISUAL_META", meta)
    monkeypatch.setattr(n, "VISUAL_FILE", tmp_path / "missing.png")
    result = n.visual_truth("$BTC is being watched.", {"symbol": "BTC"}, "BTC")
    assert result["status"] == "FAIL"
    assert any("visual symbol" in x for x in result["failures"])


def test_structure_detects_question_shape():
    from src.nic21_originality_visual_truth import structure
    assert structure("Short line.\n\nWhat happens next?") == ("S", "Q")

\ndef test_symbols_in_recognizes_btc():\n    from src.nic21_originality_visual_truth import symbols_in\n    assert "BTC" in symbols_in("$BTC setup is forming")\n