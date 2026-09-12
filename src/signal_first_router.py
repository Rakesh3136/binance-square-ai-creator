"""Signal-First Creator Router.

Makes measurable capital-flow/outcome opportunities the primary publishing lane.
Memes remain a controlled secondary lane and can only win when no sufficiently
strong signal exists or when explicitly used to amplify an already-selected signal.
This module is routing only: it does not create trade levels, outcomes, or facts.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / 'data/live/editorial_preflight.json'
DIRECTOR = ROOT / 'data/live/content_director_brief.json'
CADENCE = ROOT / 'data/live/autonomous_cadence_6.json'
OUT = ROOT / 'data/live/signal_first_routing.json'

PRIMARY_LANES = {'flow', 'capital_flow_long', 'capital_flow_short', 'creator_signal_outcome', 'follow_up'}
MARKET_SIGNAL_LANES = {'market', 'top_gainers', 'top_losers', 'high_volatility', 'volume_leaders', 'technical_setup'}
MEME_LANES = {'crypto_meme', 'meme'}
MIN_PRIMARY_SCORE = float(os.getenv('SIGNAL_FIRST_MIN_SCORE', '72'))
MIN_FLOW_CONFIDENCE = float(os.getenv('SIGNAL_FIRST_MIN_FLOW_CONFIDENCE', '65'))
MEME_MAX_SHARE = float(os.getenv('SIGNAL_FIRST_MEME_MAX_SHARE', '0.25'))


def load(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def num(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def lane(item):
    return str(item.get('lane') or item.get('type') or item.get('category') or '').lower()


def signal_candidate(brief, preflight):
    ranked = brief.get('ranked_stories') or []
    candidates = []
    for item in ranked:
        if not isinstance(item, dict):
            continue
        l = lane(item)
        score = num(item.get('score'))
        if l in PRIMARY_LANES or l in MARKET_SIGNAL_LANES or item.get('type') in {'flow', 'market'}:
            if score >= MIN_PRIMARY_SCORE and item.get('symbol'):
                candidates.append(item)
    selected = preflight.get('selected_opportunity') or {}
    if selected and str(selected.get('lane','')).lower() in {'flow','market','news'}:
        score = num(selected.get('score'))
        if score >= MIN_PRIMARY_SCORE and selected.get('symbol'):
            candidates.append({**selected, 'score': score, 'type': selected.get('lane')})
    return max(candidates, key=lambda x: num(x.get('score'))) if candidates else None


def flow_is_complete(item):
    setup = item.get('trade_setup') or {}
    return (
        str(setup.get('side') or '').upper() in {'LONG', 'SHORT'}
        and setup.get('trigger') is not None
        and setup.get('invalidation') is not None
        and num(item.get('flow_confidence'), num(item.get('score'))) >= MIN_FLOW_CONFIDENCE
    )


def main():
    preflight = load(PREFLIGHT)
    brief = load(DIRECTOR)
    cadence = load(CADENCE)
    candidate = signal_candidate(brief, preflight)
    cadence_publish = bool(cadence.get('publish', False))
    existing_category = str(cadence.get('category') or cadence.get('content_category') or '').lower()

    decision = 'NO_PUBLISH'
    publish = False
    selected = None
    primary = False
    meme = False
    reason = 'no_qualified_primary_signal'

    if candidate and cadence_publish:
        selected = dict(candidate)
        primary = True
        publish = True
        decision = 'PRIMARY_SIGNAL'
        reason = 'qualified_signal_out_ranks_secondary_content'
        if candidate.get('type') == 'flow' or lane(candidate) in {'flow','capital_flow_long','capital_flow_short'}:
            if not flow_is_complete(candidate):
                publish = False
                primary = False
                decision = 'NO_PUBLISH'
                reason = 'flow_candidate_missing_trigger_or_invalidation'

    # A meme is allowed only as a fallback. It cannot displace a qualified signal.
    if not publish and cadence_publish and existing_category in MEME_LANES:
        meme = True
        publish = True
        decision = 'SECONDARY_MEME'
        reason = 'no_qualified_primary_signal; controlled_meme_fallback'
        selected = {'category': 'crypto_meme', 'lane': 'meme', 'score': 0, 'symbol': '', 'primary_signal_available': False}

    # If cadence itself selected a non-meme non-signal lane, preserve it only when
    # there is no qualified signal. The router records that it was not a signal win.
    if not publish and cadence_publish and existing_category not in MEME_LANES:
        decision = 'CADENCE_NO_SIGNAL'
        reason = 'cadence_allowed_cycle_but_no_primary_signal_met_threshold'

    result = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'router_version': '1.0-signal-first',
        'publish': publish,
        'decision': decision,
        'reason': reason,
        'primary_signal': primary,
        'secondary_meme': meme,
        'selected': selected,
        'cadence_publish': cadence_publish,
        'existing_category': existing_category,
        'policy': {
            'primary_lane': 'capital_flow_and_measurable_market_outcomes',
            'secondary_lane': 'controlled_memes',
            'minimum_primary_score': MIN_PRIMARY_SCORE,
            'minimum_flow_confidence': MIN_FLOW_CONFIDENCE,
            'target_meme_share_max': MEME_MAX_SHARE,
            'meme_cannot_displace_qualified_signal': True,
            'no_signal_means_no_signal_post': True,
            'flow_requires_trigger_and_invalidation': True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
