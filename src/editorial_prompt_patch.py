"""Compatibility check for the editorial prompt.

The production prompt lives in multi_agent_creator.py. This module must validate
semantic requirements that actually exist in that prompt; it must never require
legacy marker labels or rewrite source code at runtime.
"""
from __future__ import annotations
import ast
from pathlib import Path

P = Path("src/multi_agent_creator.py")
text = P.read_text(encoding="utf-8")
ast.parse(text, filename=str(P))

# These checks intentionally validate the current prompt's actual rules rather
# than brittle legacy headings such as "INTERACTION:" and "STYLE ROTATION:".
required_rules = {
    "NEWS MODE": "NEWS MODE:",
    "technical evidence rule": "TECHNICAL MODE:",
    "exactly one question rule": "exactly ONE story-specific question",
    "anti-slop rule": "ANTI-SLOP PHRASES TO AVOID:",
    "JSON output contract": "Return ONLY valid JSON",
    "finished-post contract": "finished publication copy",
}
missing = [name for name, marker in required_rules.items() if marker not in text]
if missing:
    raise RuntimeError(
        "multi_agent_creator.py is missing required editorial rules: "
        + ", ".join(missing)
    )

print({
    "status": "EDITORIAL_PROMPT_CHECK_OK",
    "version": "5.3-semantic-check",
    "source_rewrite": False,
    "checked_rules": list(required_rules),
})
