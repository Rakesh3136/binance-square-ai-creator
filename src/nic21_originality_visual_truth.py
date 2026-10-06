"""NIC 21 — Originality + Visual Truth Gate.

Deterministic pre-publication gate. It does not rewrite the draft or invent facts.
It inspects the current draft, recent publication history, and visual metadata,
then emits a durable gate artifact and optionally acquires a publication lock.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("data/live")
ANALYTICS = Path("analytics")
REPORTS = Path("data/reports")
OUT = ROOT / "nic21_gate.json"
LOCK = ROOT / "nic21_publication.lock"
PUBLICATION_LOG = ANALYTICS / "publication_log.jsonl"
DRAFT_PREFLIGHT = ROOT / "editorial_preflight.json"
VISUAL_META = ROOT / "visual_metadata.json"
VISUAL_FILE = ROOT / "visual.png"

SIMILARITY_BLOCK = 0.88
HOOK_BLOCK = 0.92
STRUCTURE_BLOCK = 0.90
CTA_BLOCK = 0.92
RECENT_POSTS = 12


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except Exception:
        return default


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(text).lower()).strip()


def tokens(text: str) -> set[str]:
    return {x for x in norm(text).split() if len(x) > 2}


def jaccard(a: str, b: str) -> float:
    aa, bb = tokens(a), tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(norm(s).split()) >= 4]


def hook(text: str) -> str:
    ss = sentences(text)
    return ss[0] if ss else str(text).strip()[:240]


def structure(text: str) -> tuple[str, ...]:
    # Compare paragraph/section shape rather than wording.
    parts = [p.strip() for p in str(text).split("\n\n") if p.strip()]
    shape = []
    for p in parts:
        words = len(norm(p).split())
        shape.append("Q" if "?" in p else "S" if words < 20 else "L")
    return tuple(shape[:12])


def cta(text: str) -> str:
    qs = [s for s in sentences(text) if "?" in s]
    return qs[-1] if qs else ""


def recent_posts() -> list[dict]:
    if not PUBLICATION_LOG.exists():
        return []
    out = []
    for line in PUBLICATION_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-RECENT_POSTS:]:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        text = str(obj.get("text") or obj.get("post") or obj.get("content") or "").strip()
        if text:
            out.append(obj | {"_text": text})
    return out


def latest_report() -> Path | None:
    reports = sorted(REPORTS.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def current_draft() -> tuple[str, dict]:
    report = latest_report()
    if not report:
        return "", {}
    obj = load_json(report, {})
    draft = obj.get("draft") if isinstance(obj.get("draft"), dict) else {}
    text = str(draft.get("post") or draft.get("text") or draft.get("body") or draft.get("content") or "").strip()
    return text, draft


def selected_symbol(draft: dict) -> str:
    pre = load_json(DRAFT_PREFLIGHT, {})
    selected = pre.get("selected_opportunity") if isinstance(pre.get("selected_opportunity"), dict) else {}
    raw = draft.get("symbol") or selected.get("symbol") or ""
    return re.sub(r"[^A-Z0-9]", "", str(raw).upper().replace("USDT", ""))


def symbols_in(text: str) -> set[str]:
    found = set()
    for x in re.findall(r"\$?([A-Z][A-Z0-9]{1,11})(?:USDT)?\b", text.upper()):
        if x not in {"THE", "AND", "FOR", "THIS", "WITH", "FROM", "WHAT", "WHEN", "JUST", "ONE"}:
            found.add(x)
    return found


def visual_truth(draft_text: str, draft: dict, symbol: str) -> dict:
    meta = load_json(VISUAL_META, {})
    required = {"symbol": symbol}
    failures: list[str] = []
    warnings: list[str] = []

    visual_symbol = str(meta.get("symbol") or meta.get("chart_symbol") or "").upper()
    visual_symbol = visual_symbol.replace("BINANCE:", "").replace("USDT", "")
    if visual_symbol and symbol and visual_symbol != symbol:
        failures.append(f"visual symbol {visual_symbol} != draft symbol {symbol}")
    elif not visual_symbol:
        warnings.append("visual metadata does not expose a chart symbol")

    text_symbols = symbols_in(draft_text)
    if symbol and text_symbols and symbol not in text_symbols:
        failures.append(f"draft does not visibly reference selected symbol {symbol}")
    extras = text_symbols - ({symbol} if symbol else set())
    if extras:
        warnings.append("draft contains additional ticker-like tokens: " + ", ".join(sorted(extras)))

    timeframe_text = " ".join(re.findall(r"\b(?:\d+[mhdw]|\d+\s*(?:min|hour|day|week)s?)\b", draft_text.lower()))
    visual_tf = str(meta.get("timeframe") or meta.get("interval") or "").lower()
    if visual_tf and timeframe_text and not any(visual_tf == x for x in re.findall(r"\b(?:\d+[mhdw])\b", timeframe_text)):
        warnings.append(f"visual timeframe {visual_tf} differs from explicit draft timeframe")

    if VISUAL_FILE.exists():
        meta_hash = str(meta.get("sha256") or meta.get("image_sha256") or "")
        actual_hash = hashlib.sha256(VISUAL_FILE.read_bytes()).hexdigest()
        if meta_hash and meta_hash != actual_hash:
            failures.append("visual metadata hash does not match visual.png")
    elif meta:
        failures.append("visual metadata exists but visual.png is missing")
    else:
        warnings.append("no visual package found; visual truth cannot be fully verified")

    # A visual may explicitly carry evidence/annotation fields. If present, make
    # their relationship to the draft auditable without pretending pixels prove prose.
    for key in ("price", "support", "resistance", "levels", "direction"):
        if key in meta and meta.get(key) in (None, ""):
            warnings.append(f"visual field {key} is empty")

    return {"status": "PASS" if not failures else "FAIL", "required": required,
            "failures": failures, "warnings": warnings,
            "visual_metadata_present": bool(meta), "visual_file_present": VISUAL_FILE.exists()}


def originality(draft_text: str, symbol: str) -> dict:
    posts = recent_posts()
    failures: list[str] = []
    comparisons = []
    current_hook = hook(draft_text)
    current_structure = structure(draft_text)
    current_cta = cta(draft_text)

    for i, post in enumerate(posts):
        old = post["_text"]
        sem = jaccard(draft_text, old)
        hs = jaccard(current_hook, hook(old))
        ss = 1.0 if current_structure and current_structure == structure(old) else 0.0
        cs = jaccard(current_cta, cta(old)) if current_cta and cta(old) else 0.0
        old_symbol = re.sub(r"[^A-Z0-9]", "", str(post.get("symbol") or "").upper().replace("USDT", ""))
        same_asset = bool(symbol and old_symbol and symbol == old_symbol)
        comparison = {"recent_index": i, "same_asset": same_asset, "semantic_similarity": round(sem, 4),
                      "hook_similarity": round(hs, 4), "structure_similarity": ss,
                      "cta_similarity": round(cs, 4)}
        comparisons.append(comparison)
        reasons = []
        if sem >= SIMILARITY_BLOCK: reasons.append("semantic_similarity")
        if hs >= HOOK_BLOCK: reasons.append("hook_similarity")
        if ss >= STRUCTURE_BLOCK and cs >= CTA_BLOCK: reasons.append("structure_and_cta_similarity")
        if reasons:
            failures.append(f"recent post {i}: " + ", ".join(reasons))

    return {"status": "PASS" if not failures else "FAIL", "failures": failures,
            "comparisons": comparisons, "recent_posts_checked": len(posts),
            "thresholds": {"semantic": SIMILARITY_BLOCK, "hook": HOOK_BLOCK,
                           "structure": STRUCTURE_BLOCK, "cta": CTA_BLOCK}}


def acquire_lock(owner: str, ttl_seconds: int = 900) -> tuple[bool, str]:
    ROOT.mkdir(parents=True, exist_ok=True)
    payload = {"owner": owner, "acquired_at": now(), "pid": os.getpid()}
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        return True, "acquired"
    except FileExistsError:
        try:
            old = load_json(LOCK, {})
            acquired = old.get("acquired_at", "")
            # ISO timestamps are only used for stale-lock detection; a malformed
            # timestamp is treated as active to avoid accidental concurrent publish.
            dt = datetime.fromisoformat(acquired.replace("Z", "+00:00"))
            stale = (datetime.now(timezone.utc) - dt).total_seconds() > ttl_seconds
        except Exception:
            stale = False
        if stale:
            try:
                LOCK.unlink()
            except FileNotFoundError:
                pass
            return acquire_lock(owner, ttl_seconds)
        return False, "active_lock"


def release_lock(owner: str) -> bool:
    if not LOCK.exists():
        return True
    data = load_json(LOCK, {})
    if data.get("owner") != owner:
        return False
    try:
        LOCK.unlink()
        return True
    except FileNotFoundError:
        return True


def run(acquire: bool = False, release: bool = False) -> int:
    owner = f"{os.getpid()}:{time.time_ns()}"
    if release:
        return 0 if release_lock(owner) else 1
    text, draft = current_draft()
    if not text:
        result = {"status": "BLOCKED", "reason": "no_current_draft", "updated_at": now()}
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 1
    symbol = selected_symbol(draft)
    orig = originality(text, symbol)
    visual = visual_truth(text, draft, symbol)
    failures = list(orig["failures"]) + list(visual["failures"])
    lock = {"status": "NOT_REQUESTED"}
    if acquire and not failures:
        ok, reason = acquire_lock(owner)
        lock = {"status": "ACQUIRED" if ok else "BLOCKED", "reason": reason, "owner": owner}
        if not ok:
            failures.append("publication lock is already held")
    result = {"schema_version": "NIC21.1", "gate": "NIC_21_ORIGINALITY_VISUAL_TRUTH",
              "status": "PASS" if not failures else "BLOCKED", "updated_at": now(),
              "symbol": symbol, "originality": orig, "visual_truth": visual,
              "publication_lock": lock, "failures": failures,
              "draft_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--acquire-lock", action="store_true")
    parser.add_argument("--release-lock", action="store_true")
    raise SystemExit(run(acquire=parser.parse_args().acquire_lock,
                         release=parser.parse_args().release_lock))
