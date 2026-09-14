"""Creator 7.5.1 — Growth Portfolio Controller.

Allocates the creator's content portfolio using verified outcomes, audience
quality, experiment state and explicit revenue evidence. This is a portfolio
allocator, not a post generator: it chooses where the next valid story fits
while preserving editorial, market-data and anti-manipulation gates.
"""
from __future__ import annotations
import json, math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'analytics/creator_7_2_outcomes.jsonl'
MEMORY = ROOT / 'analytics/strategy_memory.json'
EXPERIMENT = ROOT / 'analytics/creator_7_4_experiment_plan.json'
OUT = ROOT / 'analytics/creator_7_5_growth_portfolio.json'
REPORT = ROOT / 'data/intelligence/creator_7_5_report.json'

BUCKETS = ('BREAKING_MARKET', 'DISCOVERY', 'DATA_DEEP_DIVE', 'OUTCOME_ACCOUNTABILITY',
           'EXPLAINER', 'DEBATE', 'MACRO_REGULATION', 'MEME_COMMUNITY')


def load(path, default):
    try:
        value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
        return value if isinstance(value, type(default)) else default
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


def verified_revenue(x):
    # Only an explicitly verified field is revenue. Never infer revenue from clicks/views.
    for key in ('verified_revenue', 'revenue_verified'):
        value = x.get(key)
        if isinstance(value, dict):
            if value.get('verified') is True:
                return num(value.get('amount'))
        elif value is not None and x.get('revenue_status') == 'VERIFIED':
            return num(value)
    return 0.0


def outcome_score(x):
    if x.get('outcome_score') is not None:
        return num(x['outcome_score'])
    m = x.get('metrics') or {}
    views = num(m.get('views'))
    if views <= 0:
        return 0.0
    return (num(m.get('likes')) + 2*num(m.get('comments')) +
            3*num(m.get('shares')) + 2*num(m.get('quotes'))) / views * 1000


def quality_engagement(x):
    m = x.get('metrics') or {}
    views = num(m.get('views'))
    if views <= 0:
        return 0.0
    # Comments/shares/quotes receive more weight than passive views.
    return ((num(m.get('comments')) * 3) + (num(m.get('shares')) * 4) +
            (num(m.get('quotes')) * 4) + num(m.get('likes'))) / views * 1000


def bucket(x):
    c = str(x.get('category') or '').lower()
    lane = str(x.get('story_lane') or '').lower()
    if any(k in c for k in ('meme', 'humor', 'community')) or 'meme' in lane:
        return 'MEME_COMMUNITY'
    if any(k in c for k in ('breaking', 'news', 'alert')):
        return 'BREAKING_MARKET'
    if any(k in c for k in ('capital_flow', 'watchlist', 'top_gainer', 'top_loser', 'technical_setup')) or 'discovery' in lane:
        return 'DISCOVERY'
    if any(k in c for k in ('outcome', 'follow_up', 'creator_signal_outcome')) or 'outcome' in lane:
        return 'OUTCOME_ACCOUNTABILITY'
    if any(k in c for k in ('macro', 'regulation', 'policy', 'institutional')):
        return 'MACRO_REGULATION'
    if any(k in c for k in ('analysis', 'technical', 'onchain', 'data', 'comparison')):
        return 'DATA_DEEP_DIVE'
    if any(k in c for k in ('opinion', 'debate', 'community')):
        return 'DEBATE'
    return 'EXPLAINER'


def mean(values):
    return sum(values) / len(values) if values else 0.0


def bucket_stats(data):
    grouped = defaultdict(list)
    for row in data:
        grouped[bucket(row)].append(row)
    stats = {}
    for b in BUCKETS:
        items = grouped.get(b, [])
        stats[b] = {
            'sample': len(items),
            'mean_outcome_score': round(mean([outcome_score(x) for x in items]), 4),
            'mean_quality_engagement': round(mean([quality_engagement(x) for x in items]), 4),
            'verified_revenue': round(sum(verified_revenue(x) for x in items), 8),
            'revenue_samples': sum(verified_revenue(x) > 0 for x in items),
            'mean_follower_growth': round(mean([num((x.get('metrics') or {}).get('follower_growth')) for x in items]), 4),
        }
    return stats


def asset_concentration(data):
    assets = [str(x.get('symbol') or x.get('asset') or '').upper() for x in data]
    assets = [a for a in assets if a]
    counts = Counter(assets)
    total = max(len(assets), 1)
    top = counts.most_common(5)
    return {
        'unique_assets': len(counts),
        'top_assets': [{'asset': a, 'count': n, 'share': round(n / total, 4)} for a, n in top],
        'top_asset_share': round(top[0][1] / total, 4) if top else 0.0,
    }


def experiment_overlay():
    doc = load(EXPERIMENT, {})
    current = doc.get('current_experiment') if isinstance(doc, dict) else None
    if not isinstance(current, dict):
        return {'active': False}
    return {
        'active': current.get('status') == 'ACTIVE',
        'experiment_id': current.get('experiment_id'),
        'mode': current.get('mode'),
        'primary_variable': current.get('primary_variable'),
        'treatment_value': current.get('treatment_value'),
    }


def build_targets(data, stats, experiment):
    # Baseline is diversified by design. Outcome accountability and discovery
    # receive strategic weight because they connect learning to useful market content.
    target = {
        'BREAKING_MARKET': 0.14,
        'DISCOVERY': 0.22,
        'DATA_DEEP_DIVE': 0.16,
        'OUTCOME_ACCOUNTABILITY': 0.14,
        'EXPLAINER': 0.14,
        'DEBATE': 0.08,
        'MACRO_REGULATION': 0.07,
        'MEME_COMMUNITY': 0.05,
    }
    if len(data) < 20:
        target['EXPLAINER'] += 0.05
        target['MEME_COMMUNITY'] -= 0.02
        target['OUTCOME_ACCOUNTABILITY'] -= 0.03

    # Evidence can move a limited amount of allocation, but no bucket may dominate.
    for b, s in stats.items():
        if s['sample'] >= 5 and s['mean_outcome_score'] > 0:
            if s['mean_outcome_score'] >= 1.25 * max(stats.get('EXPLAINER', {}).get('mean_outcome_score', 0), 0.0001):
                target[b] += 0.03
            elif s['mean_outcome_score'] <= 0.65 * max(stats.get('EXPLAINER', {}).get('mean_outcome_score', 0), 0.0001):
                target[b] = max(0.03, target[b] - 0.03)

    # Verified revenue is a secondary optimization signal only.
    revenue_buckets = [b for b, s in stats.items() if s['revenue_samples'] >= 2 and s['verified_revenue'] > 0]
    for b in revenue_buckets:
        target[b] += 0.02

    # Normalize and cap concentration.
    target = {b: max(0.03, min(v, 0.28)) for b, v in target.items()}
    total = sum(target.values())
    return {b: round(v / total, 4) for b, v in target.items()}


def main():
    data = rows()
    stats = bucket_stats(data)
    target = build_targets(data, stats, experiment_overlay())
    total = max(len(data), 1)
    observed = {b: round(stats[b]['sample'] / total, 4) for b in BUCKETS}
    gaps = {b: round(target[b] - observed[b], 4) for b in BUCKETS}

    # Score portfolio priority by under-allocation first, then outcome quality,
    # meaningful discussion, follower growth and only finally verified revenue.
    priority_score = {}
    for b in BUCKETS:
        s = stats[b]
        quality = s['mean_quality_engagement']
        outcome = s['mean_outcome_score']
        follower = s['mean_follower_growth']
        revenue = s['verified_revenue'] if s['revenue_samples'] >= 2 else 0.0
        priority_score[b] = round(
            gaps[b] * 100 + min(outcome, 100) * 0.25 + min(quality, 100) * 0.20 +
            min(follower, 100) * 0.10 + min(revenue, 100) * 0.05, 4
        )
    priority = sorted(BUCKETS, key=lambda b: priority_score[b], reverse=True)

    concentration = asset_concentration(data)
    experiment = experiment_overlay()
    portfolio = {
        'version': '7.5.1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'sample_size': len(data),
        'content_mix_target': target,
        'observed_mix': observed,
        'allocation_gaps': gaps,
        'bucket_stats': stats,
        'priority_scores': priority_score,
        'next_bucket_priority': priority[:4],
        'asset_concentration': concentration,
        'active_experiment': experiment,
        'portfolio_policy': {
            'max_bucket_target': 0.28,
            'min_bucket_target': 0.03,
            'verified_revenue_only': True,
            'revenue_weight': 'secondary',
            'engagement_quality_over_raw_views': True,
            'asset_concentration_warning_share': 0.35,
            'skip_when_no_quality_story': True,
            'experiment_is_subordinate_to_story_quality': True,
        },
        'rules': [
            'Diversify across discovery, market intelligence, accountability, education, debate, macro and selective memes.',
            'Never force a portfolio bucket when no verified high-quality story exists.',
            'A major verified event can temporarily override the target mix.',
            'Do not overfit to a single asset, topic, format or market regime.',
            'Prefer substantive comments, shares, quotes and follower growth over raw views.',
            'Use revenue only when explicitly verified; never infer revenue from engagement.',
            'An active 7.4 experiment may shape the next post only when the natural story supports it.',
            'Existing factual, originality, market-data, publication and anti-manipulation gates remain authoritative.',
        ],
        'next_action': (
            f"Prefer a {priority[0]} opportunity that passes all existing gates. "
            f"If unavailable, choose the strongest qualified opportunity rather than manufacturing a portfolio slot."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(portfolio, indent=2, ensure_ascii=False), encoding='utf-8')

    memory = load(MEMORY, {})
    memory['creator_7_5'] = portfolio
    overlay = memory.get('learning_overlay') if isinstance(memory.get('learning_overlay'), dict) else {}
    overlay['growth_portfolio'] = {
        'instruction': portfolio['next_action'],
        'priority_buckets': priority[:4],
        'target_mix': target,
        'asset_concentration_warning': concentration['top_asset_share'] > 0.35,
        'active_experiment': experiment,
    }
    memory['learning_overlay'] = overlay
    MEMORY.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding='utf-8')

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        'version': '7.5.1',
        'generated_at': portfolio['generated_at'],
        'sample_size': len(data),
        'portfolio': portfolio,
    }, indent=2, ensure_ascii=False), encoding='utf-8')

    print(json.dumps({
        'status': 'OK',
        'version': '7.5.1',
        'sample_size': len(data),
        'next_buckets': priority[:4],
        'top_asset_share': concentration['top_asset_share'],
        'active_experiment': experiment.get('experiment_id'),
        'report': str(REPORT),
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
