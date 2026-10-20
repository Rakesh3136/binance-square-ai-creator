import hashlib
import json
import os
from pathlib import Path

from src import nic21_originality_visual_truth as n


def test_nic21_module_has_hard_similarity_thresholds():
    assert n.SIMILARITY_BLOCK < 1.0
    assert n.HOOK_BLOCK < 1.0
    assert n.STRUCTURE_BLOCK < 1.0
    assert n.CTA_BLOCK < 1.0


def test_jaccard_is_symmetric():
    assert n.jaccard("alpha beta gamma", "alpha beta") == n.jaccard("alpha beta", "alpha beta gamma")


def test_originality_blocks_near_duplicate(monkeypatch, tmp_path):
    log = tmp_path / "publication_log.jsonl"
    log.write_text(json.dumps({"text": "BTC breaks above the level and the market waits for confirmation."}) + "\n", encoding="utf-8")
    monkeypatch.setattr(n, "PUBLICATION_LOG", log)
    result = n.originality("BTC breaks above the level and the market waits for confirmation.", "BTC")
    assert result["status"] == "FAIL"


def test_visual_truth_rejects_symbol_mismatch(monkeypatch, tmp_path):
    meta = tmp_path / "visual_metadata.json"
    meta.write_text(json.dumps({"symbol": "BINANCE:ETHUSDT"}), encoding="utf-8")
    monkeypatch.setattr(n, "VISUAL_META", meta)
    monkeypatch.setattr(n, "VISUAL_FILE", tmp_path / "missing.png")
    result = n.visual_truth("$BTC setup.\\nEntry trigger: 100\\nTP1: 110\\nTP2: 120\\nSL / invalidation: 95", {"symbol": "BTC"}, "BTC")
    assert result["status"] == "FAIL"
    assert any("visual symbol" in x for x in result["failures"])


def test_setup_like_post_requires_matching_chart_metadata_and_hash(monkeypatch, tmp_path):
    image = tmp_path / "visual.png"
    image.write_bytes(b"x" * 12000)
    meta = tmp_path / "visual_metadata.json"
    meta.write_text(json.dumps({
        "symbol": "BINANCE:BTCUSDT",
        "timeframe": "1h",
        "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    monkeypatch.setattr(n, "VISUAL_META", meta)
    monkeypatch.setattr(n, "VISUAL_FILE", image)
    result = n.visual_truth("$BTC support and resistance are being watched on the 1h chart.", {"symbol": "BTC"}, "BTC")
    assert result["status"] == "PASS"


def test_setup_like_post_without_chart_is_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(n, "VISUAL_META", tmp_path / "missing.json")
    monkeypatch.setattr(n, "VISUAL_FILE", tmp_path / "missing.png")
    result = n.visual_truth("$BTC setup is being watched.\nEntry trigger: 100\nTP1: 110\nTP2: 120\nSL / invalidation: 95", {"symbol": "BTC"}, "BTC")
    assert result["status"] == "FAIL"
    assert any("requires a rendered visual" in x for x in result["failures"])


def test_editorial_prose_about_support_does_not_require_a_chart(monkeypatch, tmp_path):
    monkeypatch.setattr(n, "ROOT", tmp_path)
    context = tmp_path / "publication_context.json"
    context.write_text(json.dumps({"category": "weekly_synthesis"}), encoding="utf-8")
    monkeypatch.setattr(n, "VISUAL_META", tmp_path / "missing.json")
    monkeypatch.setattr(n, "VISUAL_FILE", tmp_path / "missing.png")
    result = n.visual_truth(
        "A useful weekly synthesis explains support and resistance as context, not as a trade entry.",
        {"symbol": "BTC"}, "BTC"
    )
    assert result["status"] == "PASS"
    assert not any("requires a rendered visual" in x for x in result["failures"])


def test_originality_only_defers_visual_truth(monkeypatch, tmp_path):
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps({"draft": {"post": "A unique editorial post about market structure.", "symbol": "BTC"}}), encoding="utf-8")
    monkeypatch.setenv("DRAFT_PATH", str(draft_path))
    monkeypatch.setattr(n, "OUT", tmp_path / "nic21_gate.json")
    monkeypatch.setattr(n, "PUBLICATION_LOG", tmp_path / "empty-publication-log.jsonl")
    assert n.run(originality_only=True) == 0
    result = json.loads((tmp_path / "nic21_gate.json").read_text(encoding="utf-8"))
    assert result["status"] == "PASS"
    assert result["visual_truth"]["status"] == "DEFERRED"


def test_current_draft_uses_explicit_draft_path(monkeypatch, tmp_path):
    path = tmp_path / "current.json"
    path.write_text(json.dumps({"draft": {"post": "Exact final draft.", "symbol": "BTC"}}), encoding="utf-8")
    monkeypatch.setenv("DRAFT_PATH", str(path))
    text, draft = n.current_draft()
    assert text == "Exact final draft."
    assert draft["symbol"] == "BTC"


def test_structure_detects_question_shape():
    assert n.structure("Short line.\n\nWhat happens next?") == ("S", "Q")


def test_symbols_in_recognizes_btc():
    assert "BTC" in n.symbols_in("$BTC setup is forming")
