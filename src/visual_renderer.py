"""Visual dispatcher for Binance Square with bounded chart-style diversity."""
from __future__ import annotations
import json, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SRC=Path(__file__).resolve().parent
TRADINGVIEW=SRC/'tradingview_renderer.mjs'; MEME=SRC/'meme_visual_renderer.py'; ANALYST=SRC/'analyst_square_chart_renderer.py'; SNAPSHOT=ROOT/'data/live/historical_setup_snapshot.json'; CONTEXT=ROOT/'data/live/publication_context.json'; FROZEN=ROOT/'data/live/authoritative_opportunity.json'
def load(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return {}
def clean_symbol(value):
    raw=str(value or '').upper().replace('BINANCE:','').strip(); return raw[:-4] if raw.endswith('USDT') else raw
def ensure_playwright():
    node=shutil.which('node'); npm=shutil.which('npm')
    if not node or not npm:raise SystemExit('TradingView renderer requires node and npm')
    probe=subprocess.run([node,'-e',"import('playwright').then(()=>process.exit(0)).catch(()=>process.exit(1))"],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    if probe.returncode==0:return
    print('Playwright package missing; bootstrapping TradingView renderer dependency')
    subprocess.run([npm,'install','--no-save','--no-package-lock','playwright@latest'],cwd=ROOT,check=True)
    npx=shutil.which('npx')
    if not npx:raise SystemExit('npm installed Playwright but npx is unavailable')
    subprocess.run([npx,'playwright','install','--with-deps','chromium'],cwd=ROOT,check=True)
def apply_chart_style():
    planner=SRC/'visual_style_planner.py'; overlay=SRC/'chart_style_overlay.py'
    if planner.exists():
        subprocess.run(['python',str(planner)],cwd=ROOT,check=True)
    if overlay.exists() and (ROOT/'data/live/visual.png').exists():
        subprocess.run(['python',str(overlay)],cwd=ROOT,check=True)
def main():
    ctx=load(CONTEXT); frozen=load(FROZEN); cat=str(ctx.get('category') or '').lower()
    signal_lanes={'capital_flow_long','capital_flow_short','flow','technical_setup','creator_signal_outcome','follow_up'}
    routing=load(ROOT/'data/live/signal_first_routing.json')
    authoritative_signal=(str(routing.get('decision') or '').upper()=='PRIMARY_SIGNAL' and routing.get('prediction_contract_complete') is not False and bool(routing.get('selected')))
    if cat in signal_lanes and authoritative_signal:
        expected=clean_symbol(ctx.get('symbol') or frozen.get('symbol')); snap=load(SNAPSHOT); actual=clean_symbol(snap.get('symbol'))
        if not expected:raise SystemExit('historical chart requires an authoritative publication symbol')
        if not snap or snap.get('status')!='FROZEN':raise SystemExit('historical chart snapshot missing for Signal-First technical lane')
        if actual!=expected:raise SystemExit(f'historical chart asset mismatch: snapshot={actual or "<missing>"} current={expected}')
        pred=snap.get('prediction') or {}; frozen_pred=frozen.get('prediction') if isinstance(frozen.get('prediction'),dict) else {}
        checks={'direction':str(pred.get('direction') or '').upper()==str(frozen.get('direction') or frozen_pred.get('direction') or pred.get('direction') or '').upper(),'entry':pred.get('entry_trigger')==(frozen.get('entry_trigger') if frozen.get('entry_trigger') is not None else frozen_pred.get('entry_trigger',pred.get('entry_trigger'))),'tp1':pred.get('tp1')==(frozen.get('tp1') if frozen.get('tp1') is not None else frozen_pred.get('tp1',pred.get('tp1'))),'tp2':pred.get('tp2')==(frozen.get('tp2') if frozen.get('tp2') is not None else frozen_pred.get('tp2',pred.get('tp2'))),'sl':pred.get('sl')==(frozen.get('sl') if frozen.get('sl') is not None else frozen_pred.get('sl',pred.get('sl')))}
        if not all(checks.values()):raise SystemExit(f'historical chart setup mismatch with authoritative prediction: {checks}')
        rc=subprocess.run(['python',str(ANALYST)],cwd=ROOT,check=False).returncode
        if rc==0:
            # The analyst renderer is also a setup visual. Apply the same
            # authoritative trade overlay here; previously this branch skipped
            # professional_chart_overlay.py, so the final posted image could be
            # a clean chart even though the visual contract metadata looked valid.
            overlay=SRC/'professional_chart_overlay.py'
            if overlay.exists():
                overlay_rc=subprocess.run(['python',str(overlay)],cwd=ROOT,check=False).returncode
                if overlay_rc!=0:
                    raise SystemExit('professional chart overlay failed; refusing unmarked setup visual')
            apply_chart_style()
        return rc
    if cat=='crypto_meme':return subprocess.run(['python',str(MEME)],cwd=ROOT,check=False).returncode
    ensure_playwright(); rc=subprocess.run(['node',str(TRADINGVIEW)],cwd=ROOT,check=False).returncode
    if rc==0:
        # TradingView is the base market-data layer. Always apply the
        # deterministic trade-level overlay after rendering so a plain
        # screenshot can never silently become the final setup visual.
        overlay=SRC/'professional_chart_overlay.py'
        if overlay.exists():
            overlay_rc=subprocess.run(['python',str(overlay)],cwd=ROOT,check=False).returncode
            if overlay_rc!=0:
                raise SystemExit('professional chart overlay failed; refusing unmarked setup visual')
        apply_chart_style()
    return rc
if __name__=='__main__':raise SystemExit(main())
