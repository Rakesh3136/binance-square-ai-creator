import json
from pathlib import Path

from src.candidate_generation_4 import recent_publication_context


def test_recent_publication_context_returns_newest_unique_posts(tmp_path: Path):
    log = tmp_path / "publication_log.jsonl"
    rows = [
        {"post_id": "1000001", "timestamp": "2026-10-20T00:00:00Z", "symbol": "BTC", "text": "Old thesis with evidence."},
        {"post_id": "1000002", "timestamp": "2026-10-21T00:00:00Z", "symbol": "ETH", "text": "Newer thesis with a distinct mechanism."},
        {"post_id": "1000002", "timestamp": "2026-10-21T00:00:00Z", "symbol": "ETH", "text": "Newer thesis with a distinct mechanism."},
    ]
    log.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    result = recent_publication_context(log, limit=8)

    assert [row["post_id"] for row in result] == ["1000002", "1000001"]
    assert result[0]["excerpt"] == "Newer thesis with a distinct mechanism."
    assert result[0]["symbol"] == "ETH"


def test_recent_publication_context_limits_excerpts_and_count(tmp_path: Path):
    log = tmp_path / "publication_log.jsonl"
    rows = [
        {"post_id": str(1000000 + i), "text": f"Post {i}: " + ("evidence " * 80)}
        for i in range(5)
    ]
    log.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    result = recent_publication_context(log, limit=3)

    assert len(result) == 3
    assert all(len(row["excerpt"]) <= 220 for row in result)


def test_recent_publication_context_handles_missing_log(tmp_path: Path):
    assert recent_publication_context(tmp_path / "missing.jsonl") == []
