import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/live/creator_intelligence_report.json'
BENCHMARK_STATE = ROOT / 'analytics/square_creator_benchmark_state.json'
# Creator Brain is deliberately NOT run here. Production runs it only after
# editorial_preflight + engagement_engine so it receives the current opportunity.
# Refresh public benchmarks at most weekly; retry an unavailable public feed daily.
SCRIPTS = ['creator_intelligence.py','audience_intelligence.py','market_timing.py','experiment_engine.py','visual_intelligence.py','thesis_ledger.py','creator_evolution.py','market_intelligence_6.py','capital_flow_intelligence.py']


def benchmark_refresh_due(now=None, state_path=BENCHMARK_STATE):
    now = now or datetime.now(timezone.utc)
    try:
        state = json.loads(Path(state_path).read_text(encoding='utf-8'))
        last_run = datetime.fromisoformat(str(state.get('last_run', '')).replace('Z', '+00:00'))
        if last_run.tzinfo is None:
            return True
        interval = timedelta(hours=24)
        return now - last_run.astimezone(timezone.utc) >= interval
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return True


def main():
    results, failures = [], []
    if benchmark_refresh_due():
        try:
            subprocess.run(['python', str(ROOT / 'src' / 'square_creator_benchmark_collector.py')], cwd=ROOT, check=True)
            results.append('square_creator_benchmark_collector.py')
        except subprocess.CalledProcessError as exc:
            failures.append({'script': 'square_creator_benchmark_collector.py', 'returncode': exc.returncode})
    else:
        results.append('square_creator_benchmark_collector.py (fresh cache)')
    for name in SCRIPTS:
        try:
            subprocess.run(['python', str(ROOT / 'src' / name)], cwd=ROOT, check=True)
            results.append(name)
        except subprocess.CalledProcessError as exc:
            failures.append({'script': name, 'returncode': exc.returncode})
            # Supporting intelligence may degrade to last-known data. Do not kill
            # a production cycle because one optional module temporarily fails.
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'status': 'OK' if not failures else 'DEGRADED', 'completed': results, 'failures': failures, 'brain_deferred_to_production_stage': True, 'rule': 'Creator Brain runs after preflight and engagement selection.', 'market_intelligence_version': '6.2', 'capital_flow_intelligence': 'enabled', 'public_square_benchmark_refresh': 'refresh_if_older_than_7_days_retry_daily_if_unavailable'}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
