"""Creator 7.4 — Adaptive Experiment Controller.

Turns Creator 7.3 learning into an explicit next-test plan. The controller
balances exploitation (repeat strong ideas) with exploration (test uncertain
ideas), keeps one primary variable per experiment, and never treats
observational effects as proven causality.
"""
from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'analytics/creator_7_2_outcomes.jsonl'
CAUSAL = ROOT / 'analytics/creator_7_3_strategy.json'
MEMORY = ROOT / 'analytics/strategy_memory.json'
PLAN = ROOT / 'analytics/creator_7_4_experiment_plan.json'
REPORT = ROOT / 'data/intelligence/creator_7_4_report.json'

DIMS = ('experiment_format', 'category', 'style', 'hook_type', 'visual_type')


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def rows():
    if not SOURCE.exists():
        return []
    out = []
    for line in SOURCE.read_text(encoding='utf-8').splitlines():
        try:
            x = json.loads(line)
            if isinstance(x, dict) and isinstance(x.get('metrics'), dict):
                out.append(x)
        except Exception:
            pass
    return out


def num(x):
    try:
        y = float(x)
        return y if math.isfinite(y) else 0.0
    except Exception:
        return 0.0


def outcome(x):
    if x.get('outcome_score') is not None:
        return num(x['outcome_score'])
    m = x.get('metrics', {})
    views = num(m.get('views'))
    if views <= 0:
        return 0.0
    return (num(m.get('likes')) + 2*num(m.get('comments')) + 3*num(m.get('shares')) + 2*num(m.get('quotes'))) / views * 1000


def median(values):
    values = sorted(values)
    if not values:
        return 0.0
    n = len(values)
    return values[n//2] if n % 2 else (values[n//2-1] + values[n//2]) / 2


def effect(data, dim, value):
    treatment = [outcome(x) for x in data if str(x.get(dim) or 'unknown') == value]
    control = [outcome(x) for x in data if str(x.get(dim) or 'unknown') != value]
    if not treatment or not control:
        return None
    tm, cm = median(treatment), median(control)
    lift = tm - cm
    return {
        'dimension': dim,
        'value': value,
        'treatment_sample': len(treatment),
        'control_sample': len(control),
        'treatment_median': round(tm, 4),
        'control_median': round(cm, 4),
        'lift_points': round(lift, 4),
        'lift_percent': round(lift / max(abs(cm), 1) * 100, 2),
    }


def build_plan(data, causal):
    now = datetime.now(timezone.utc).isoformat()
    existing = load_json(PLAN, {})
    current = existing.get('current_experiment') if isinstance(existing, dict) else None

    # Continue an unfinished test rather than constantly changing variables.
    if isinstance(current, dict) and current.get('status') == 'ACTIVE':
        return current, 'continue_active_experiment'

    effects = causal.get('effects', []) if isinstance(causal, dict) else []
    recommendations = causal.get('recommendations', []) if isinstance(causal, dict) else []

    # First priority: replicate a repeated observational winner to validate it.
    winners = [e for e in recommendations if e.get('decision') == 'PREFER']
    winners.sort(key=lambda e: (num(e.get('lift_percent')), int(e.get('treated_sample', 0))), reverse=True)
    if winners:
        w = winners[0]
        exp_id = f"74-rep-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        plan = {
            'experiment_id': exp_id,
            'status': 'ACTIVE',
            'created_at': now,
            'mode': 'REPLICATION',
            'hypothesis': f"Replicate the observed lift from {w['dimension']}={w['value']} under a fresh market condition.",
            'primary_variable': w['dimension'],
            'control_value': '__baseline__',
            'treatment_value': w['value'],
            'objective_metric': 'outcome_score',
            'secondary_metrics': ['views', 'likes', 'comments', 'shares', 'quotes', 'follower_growth'],
            'sample_target': 10,
            'reason': 'Repeated observational winner requires fresh validation before stronger strategy promotion.',
            'stop_rules': ['Do not declare causality from this test alone.', 'Do not publish filler just to complete the sample.', 'Preserve factual and originality constraints.'],
        }
        return plan, 'replicate_winner'

    # Otherwise choose the value with the highest information need: low sample
    # first, then the largest uncertainty (small absolute observed lift).
    candidates = []
    for dim in DIMS:
        values = sorted({str(x.get(dim) or 'unknown') for x in data})
        for value in values:
            e = effect(data, dim, value)
            if not e:
                continue
            uncertainty = 1 / max(e['treatment_sample'], 1) + 1 / max(e['control_sample'], 1)
            ambiguity = 1 / (1 + abs(e['lift_percent']))
            score = uncertainty * 100 + ambiguity * 10
            candidates.append((score, e))
    candidates.sort(key=lambda z: z[0], reverse=True)

    if candidates:
        _, e = candidates[0]
        mode = 'EXPLORATION'
        value = e['value']
        dim = e['dimension']
    else:
        # Cold-start experiment: use a balanced, platform-native pair.
        mode = 'EXPLORATION'
        dim, value = 'experiment_format', 'data_driven_breakdown'
        e = {'treatment_sample': 0, 'control_sample': len(data), 'lift_percent': 0}

    exp_id = f"74-exp-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    plan = {
        'experiment_id': exp_id,
        'status': 'ACTIVE',
        'created_at': now,
        'mode': mode,
        'hypothesis': f"Test whether {dim}={value} improves the outcome versus the account baseline while holding other major choices stable.",
        'primary_variable': dim,
        'control_value': '__baseline__',
        'treatment_value': value,
        'objective_metric': 'outcome_score',
        'secondary_metrics': ['views', 'likes', 'comments', 'shares', 'quotes', 'follower_growth'],
        'sample_target': 10,
        'observed_context': {'treatment_sample': e.get('treatment_sample', 0), 'control_sample': e.get('control_sample', 0), 'observed_lift_percent': e.get('lift_percent', 0)},
        'reason': 'Choose the next test where additional evidence can reduce uncertainty without sacrificing editorial quality.',
        'stop_rules': ['Do not claim causality from observational evidence.', 'Skip weak stories rather than manufacture a test post.', 'Never use fake engagement or guaranteed-return language.'],
    }
    return plan, 'explore_uncertainty'


def main():
    data = rows()
    causal = load_json(CAUSAL, {})
    plan, decision = build_plan(data, causal)
    plan_doc = {
        'version': '7.4',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'ACTIVE',
        'decision': decision,
        'current_experiment': plan,
        'controller_policy': {
            'exploration_rate': 0.35 if len(data) < 30 else 0.20,
            'one_primary_variable_per_test': True,
            'prefer_replication_before_promotion': True,
            'skip_if_no_quality_story': True,
            'revenue_policy': 'Use revenue only when explicitly verified; never infer revenue from engagement.',
        },
        'hard_constraints': ['factual_accuracy', 'originality', 'verified_market_data', 'no_fake_engagement', 'no_guaranteed_returns'],
    }
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan_doc, indent=2, ensure_ascii=False), encoding='utf-8')

    memory = load_json(MEMORY, {})
    memory['creator_7_4'] = plan_doc
    overlay = memory.get('learning_overlay')
    if not isinstance(overlay, dict):
        overlay = {}
    overlay['adaptive_experiment_controller'] = {
        'instruction': 'When the next post is generated, follow creator_7_4.current_experiment as the primary learning test when the chosen story naturally supports it. Keep all other editorial constraints unchanged. Do not force a weak story merely to satisfy an experiment.',
        'experiment_id': plan.get('experiment_id'),
        'primary_variable': plan.get('primary_variable'),
        'treatment_value': plan.get('treatment_value'),
        'mode': plan.get('mode'),
    }
    memory['learning_overlay'] = overlay
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding='utf-8')

    report = {'version': '7.4', 'generated_at': plan_doc['generated_at'], 'sample_size': len(data), 'decision': decision, 'next_experiment': plan, 'policy': plan_doc['controller_policy']}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'status': 'OK', 'version': '7.4', 'decision': decision, 'experiment_id': plan.get('experiment_id'), 'primary_variable': plan.get('primary_variable'), 'treatment_value': plan.get('treatment_value'), 'report': str(REPORT)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
