"""Visual dispatcher for Binance Square.

Signal-First technical lanes use the immutable historical snapshot and the
human analyst-style Square renderer. Other technical/news lanes retain
TradingView; meme lanes retain the meme renderer.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(__file__).resolve().parent
TRADINGVIEW = SRC / "tradingview_renderer.mjs"
MEME = SRC / "meme_visual_renderer.py"
ANALYST = SRC / "analyst_square_chart_renderer.py"
SNAPSHOT = ROOT / "data/live/historical_setup_snapshot.json"
CONTEXT = ROOT / "data/live/publication_context.json"
FROZEN = ROOT / "data/live/authoritative_opportunity.json"


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def clean_symbol(value) -> str:
    raw = str(value or "").upper().replace("BINANCE:", "").strip()
    return raw[:-4] if raw.endswith("USDT") else raw


def ensure_playwright() -> None:
    """Ensure the Node TradingView renderer can import Playwright on CI runners.

    The workflow installs Node but the repository intentionally does not require
    a persistent node_modules tree. Bootstrap only when the TradingView lane is
    actually selected, keeping ordinary creator cycles lightweight.
    """
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        raise SystemExit("TradingView renderer requires node and npm")

    probe = subprocess.run(
        [node, "-e", "import('playwright').then(()=>process.exit(0)).catch(()=>process.exit(1))"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return

    print("Playwright package missing; bootstrapping TradingView renderer dependency")
    subprocess.run(
        [npm, "install", "--no-save", "--no-package-lock", "playwright@latest"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [npx for npx in [shutil.which("npx")] if npx][0],
        cwd=ROOT,
        check=True,
    ) if False else None

    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("npm installed Playwright but npx is unavailable")
    subprocess.run([npx, "playwright", "install", "--with-deps", "chromium"], cwd=ROOT, check=True)


def main() -> int:
    ctx = load(CONTEXT)
    frozen = load(FROZEN)
    cat = str(ctx.get("category") or "").lower()
    signal_lanes = {
        "capital_flow_long", "capital_flow_short", "flow", "technical_setup",
        "creator_signal_outcome", "follow_up",
    }

    routing = load(ROOT / "data/live/signal_first_routing.json")
    authoritative_signal = (
        str(routing.get("decision") or "").upper() == "PRIMARY_SIGNAL"
        and routing.get("prediction_contract_complete") is not False
        and bool(routing.get("selected"))
    )

    # Historical charts are mandatory only for an authoritative Signal-First
    # trade contract. Editorial/knowledge stories can still request a chart,
    # but they must use the ordinary TradingView renderer instead of failing
    # because no frozen prediction snapshot exists.
    if cat in signal_lanes and authoritative_signal:
        expected = clean_symbol(ctx.get("symbol") or frozen.get("symbol"))
        snap = load(SNAPSHOT)
        actual = clean_symbol(snap.get("symbol"))
        if not expected:
            raise SystemExit("historical chart requires an authoritative publication symbol")
        if not snap or snap.get("status") != "FROZEN":
            raise SystemExit("historical chart snapshot missing for Signal-First technical lane")
        if actual != expected:
            raise SystemExit(f"historical chart asset mismatch: snapshot={actual or '<missing>'} current={expected}")

        pred = snap.get("prediction") or {}
        frozen_pred = frozen.get("prediction") if isinstance(frozen.get("prediction"), dict) else {}
        checks = {
            "direction": str(pred.get("direction") or "").upper() == str(frozen.get("direction") or frozen_pred.get("direction") or pred.get("direction") or "").upper(),
            "entry": pred.get("entry_trigger") == (frozen.get("entry_trigger") if frozen.get("entry_trigger") is not None else frozen_pred.get("entry_trigger", pred.get("entry_trigger"))),
            "tp1": pred.get("tp1") == (frozen.get("tp1") if frozen.get("tp1") is not None else frozen_pred.get("tp1", pred.get("tp1"))),
            "tp2": pred.get("tp2") == (frozen.get("tp2") if frozen.get("tp2") is not None else frozen_pred.get("tp2", pred.get("tp2"))),
            "sl": pred.get("sl") == (frozen.get("sl") if frozen.get("sl") is not None else frozen_pred.get("sl", pred.get("sl"))),
        }
        if not all(checks.values()):
            raise SystemExit(f"historical chart setup mismatch with authoritative prediction: {checks}")
        return subprocess.run(["python", str(ANALYST)], cwd=ROOT, check=False).returncode

    if cat == "crypto_meme":
        return subprocess.run(["python", str(MEME)], cwd=ROOT, check=False).returncode

    ensure_playwright()
    return subprocess.run(["node", str(TRADINGVIEW)], cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
