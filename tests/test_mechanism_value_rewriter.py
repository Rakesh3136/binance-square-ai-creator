"""Regression tests for the 740-character mechanism repair budget."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("mechanism",ROOT/"src/mechanism_value_rewriter.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def test_bridge_fits_short_draft_budget():
    original=("Bitcoin holds $83,000 while ZEC drops 12% and oil climbs again. "
              "The useful question is whether the reaction changes the broader setup. "
              "What should readers watch next?")
    question="What should readers watch next?"
    body=original.replace(question,"").rstrip()
    remaining=m.MAX_READER_CHARS-len(body)-len(question)-4
    bridge=m.deterministic_bridge("$BTC",body,remaining=remaining)
    candidate=f"{body}\n\n{bridge}\n\n{question}".strip()
    assert bridge
    assert len(candidate)<=m.MAX_READER_CHARS
    assert "because" in bridge.lower()
    assert m.mechanism_present(candidate)
    assert candidate.count("?")==1

def test_max_reader_chars_is_740():
    assert m.MAX_READER_CHARS==740
