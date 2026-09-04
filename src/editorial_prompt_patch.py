"""Compatibility check for the editorial prompt.

Creator 5.2 keeps the production system prompt in multi_agent_creator.py itself.
This module is intentionally non-mutating: runtime source-code rewriting caused
syntax/indentation failures in earlier production cycles.
"""
from __future__ import annotations
import ast
from pathlib import Path

P = Path("src/multi_agent_creator.py")
text = P.read_text(encoding="utf-8")
ast.parse(text, filename=str(P))
required = (
    "NEWS MODE:",
    "INTERACTION:",
    "STYLE ROTATION:",
    "Return ONLY valid JSON",
)
missing = [x for x in required if x not in text]
if missing:
    raise RuntimeError("multi_agent_creator.py is missing required editorial rules: " + ", ".join(missing))
print({
    "status": "EDITORIAL_PROMPT_CHECK_OK",
    "version": "5.2-non-mutating",
    "source_rewrite": False,
})
