"""Disable visuals only for editorial lanes where a chart is optional."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
REPORT_DIR=Path('data/reports')
REQUIRED={'technical_setup','high_volatility','top_gainers','top_losers','creator_signal_outcome'}

def main():
    reports=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if not reports: raise SystemExit('No draft available for visual degradation')
    report=reports[0]; data=json.loads(report.read_text(encoding='utf-8'))
    selected=data.get('selected_editorial_lane') or {}
    lane=str(selected.get('category') or data.get('content_category') or '').lower()
    if lane in REQUIRED:
        raise SystemExit(f'REQUIRED_TRADINGVIEW_VISUAL_FAILED: {lane} is chart-first; refusing text-only fallback')
    visual=data.get('visual_plan') if isinstance(data.get('visual_plan'),dict) else {}
    visual.update({'use_visual':False,'type':'none','degraded_from_visual':True,'degraded_at':datetime.now(timezone.utc).isoformat()})
    data['visual_plan']=visual
    report.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'VISUAL_DEGRADED_TO_TEXT','report':str(report)}))
if __name__=='__main__': main()
