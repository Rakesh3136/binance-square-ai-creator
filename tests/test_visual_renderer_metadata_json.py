from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("nic_visual_renderer", ROOT / "src" / "visual_renderer.py")
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def test_finalize_visual_metadata_writes_parseable_json_with_real_newline(tmp_path, monkeypatch):
    visual = tmp_path / "visual.png"
    metadata = tmp_path / "visual_metadata.json"
    visual.write_bytes(b"x" * 12_000)
    metadata.write_text(json.dumps({"provider": "TradingView", "status": "TRADINGVIEW_CREATED"}), encoding="utf-8")
    monkeypatch.setattr(renderer, "VISUAL", visual)
    monkeypatch.setattr(renderer, "META", metadata)

    renderer.finalize_visual_metadata()

    saved_text = metadata.read_text(encoding="utf-8")
    parsed = json.loads(saved_text)
    assert saved_text.endswith("\n")
    assert parsed["provider"] == "TradingView"
    assert parsed["status"] == "TRADINGVIEW_CREATED"
    assert parsed["sha256"] == parsed["image_sha256"]
    assert len(parsed["sha256"]) == 64
