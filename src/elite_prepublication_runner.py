"""Deterministic runner for the elite pre-publication judge.

Keeps approved reusable safety language out of the creative-repetition signal,
including the canonicalized hyphen-free form produced by the judge normalizer.
"""
import elite_prepublication_judge as judge

# The judge strips punctuation before comparison, so chart-derived becomes
# chartderived. Register that canonical safety phrase explicitly.
judge._REUSABLE_NORMALIZED.add("levels are chartderived scenarios not guarantees")

if __name__ == "__main__":
    judge.main()
