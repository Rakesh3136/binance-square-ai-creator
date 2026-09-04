import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/live/creator_intelligence_report.json'
# Creator Brain is deliberately NOT run here. Production runs it only after
# editorial_preflight + engagement_engine so it receives the current opportunity.
SCRIPTS = ['audience_intelligence.py','market_timing.py','experiment_engine.py','visual_intelligence.py','thesis_ledger.py','creator_evolution.py','market_intelligence_6.py']

def main():
    results, failures = [], []
    for name in SCRIPTS:
        try:
            subprocess.run(['python', str(ROOT / 'src' / name)], cwd=ROOT, check=True)
            results.append(name)
        except subprocess.CalledProcessError as exc:
            failures.append({'script': name, 'returncode': exc.returncode})
            # Supporting intelligence may degrade to last-known data. Do not kill
            # a production cycle because one optional module temporarily fails.
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'status': 'OK' if not failures else 'DEGRADED', 'completed': results, 'failures': failures, 'brain_deferred_to_production_stage': True, 'rule': 'Creator Brain runs after preflight and engagement selection.', 'market_intelligence_version': '6.2'}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
