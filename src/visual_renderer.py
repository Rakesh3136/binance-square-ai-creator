"""Visual dispatcher for Binance Square.

Signal-First technical lanes use the immutable historical snapshot and the
professional setup renderer. Other technical/news lanes retain TradingView.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=Path(__file__).resolve().parent
TRADINGVIEW=SRC/'tradingview_renderer.mjs'
MEME=SRC/'meme_visual_renderer.py'
PRO=SRC/'professional_setup_renderer.py'
SNAPSHOT=ROOT/'data/live/historical_setup_snapshot.json'
CONTEXT=ROOT/'data/live/publication_context.json'


def category():
    try:return str(json.loads(CONTEXT.read_text()) .get('category') or '').lower()
    except Exception:return ''

def main():
    cat=category()
    if SNAPSHOT.exists() and cat in {'capital_flow_long','capital_flow_short','flow','technical_setup','creator_signal_outcome','follow_up'}:
        return subprocess.run(['python',str(PRO)],cwd=ROOT,check=False).returncode
    if cat=='crypto_meme': return subprocess.run(['python',str(MEME)],cwd=ROOT,check=False).returncode
    return subprocess.run(['node',str(TRADINGVIEW)],cwd=ROOT,check=False).returncode

if __name__=='__main__': raise SystemExit(main())
