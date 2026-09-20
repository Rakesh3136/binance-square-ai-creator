"""Visual dispatcher for Binance Square.

Technical/news lanes use the validated TradingView renderer. Crypto meme lanes
use an original, license-safe meme visual so reach content is not published as
text-only when the story benefits from a picture.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(__file__).resolve().parent
TRADINGVIEW = SRC / 'tradingview_renderer.mjs'
MEME = SRC / 'meme_visual_renderer.py'
HISTORICAL = SRC / 'historical_setup_renderer.py'
SNAPSHOT = ROOT / 'data/live/historical_setup_snapshot.json'
CONTEXT = ROOT / 'data/live/publication_context.json'


def category() -> str:
    try:
        data = json.loads(CONTEXT.read_text(encoding='utf-8'))
        return str(data.get('category') or '').lower()
    except Exception:
        return ''


def main() -> int:
    cat = category()
    # Signal-First technical posts must use the frozen historical state.
    # This branch intentionally bypasses the live TradingView widget so a later
    # price move can never rewrite the original setup chart.
    if SNAPSHOT.exists() and cat in {'capital_flow_long', 'capital_flow_short', 'flow', 'technical_setup', 'creator_signal_outcome', 'follow_up'}:
        return subprocess.run(['python', str(HISTORICAL)], check=False).returncode
    if cat == 'crypto_meme':
        if not MEME.exists():
            raise SystemExit(f'Missing meme renderer: {MEME}')
        return subprocess.run(['python', str(MEME)], check=False).returncode
    if not TRADINGVIEW.exists():
        raise SystemExit(f'Missing TradingView renderer: {TRADINGVIEW}')
    return subprocess.run(['node', str(TRADINGVIEW)], check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
