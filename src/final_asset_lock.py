"""Final asset lock: the published draft must match the frozen primary asset.

This is intentionally later than all AI/editorial repair stages.  Selection
modules can choose a story, but no downstream writer or repairer may silently
change the monetizable primary asset.  If the draft no longer represents the
frozen asset, publication stops instead of falling back to BTC or another
convenient ticker.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / 'data/live/authoritative_opportunity.json'
CONTEXT = ROOT / 'data/live/publication_context.json'
OUT = ROOT / 'data/live/final_asset_lock.json'


def load(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def normalize(value):
    value = str(value or '').upper().replace('BINANCE:', '').strip()
    value = value.replace('USDT', '')
    value = value.replace('$', '')
    return value


def resolve_draft():
    explicit = os.getenv('DRAFT_PATH', '').strip()
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise SystemExit(f'DRAFT_PATH does not exist: {explicit}')
        return path
    reports = sorted((ROOT / 'data/reports').glob('*-multi-agent.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise SystemExit('No fresh draft report')
    return reports[0]


def main():
    frozen = load(FROZEN)
    context = load(CONTEXT)
    draft_path = resolve_draft()
    report = load(draft_path)
    draft = report.get('draft') or {}
    text = '\n'.join(str(draft.get(k) or '') for k in ('post', 'text', 'title', 'headline'))

    frozen_symbol = normalize(frozen.get('symbol') or context.get('symbol'))
    if not frozen_symbol:
        raise SystemExit('FINAL_ASSET_LOCK_FAILED: missing frozen primary symbol')

    cashtags = {m.group(1).upper() for m in re.finditer(r'\$([A-Z][A-Z0-9]{0,14})\b', text.upper())}
    headline_assets = {normalize(x) for x in (context.get('headline_assets') or []) if normalize(x)}
    allowed = {frozen_symbol} | headline_assets
    foreign = sorted(x for x in cashtags if x not in allowed)
    primary_present = frozen_symbol in cashtags

    failures = []
    if not primary_present:
        failures.append(f'primary_cashtag_missing:${frozen_symbol}')
    if foreign:
        failures.append('unsupported_primary_asset_drift:' + ','.join(foreign))

    # A non-comparison story must contain the frozen asset and must not promote
    # another asset as an alternative primary cashtag. Explicit multi-asset
    # stories are allowed only when the frozen context names those assets.
    category = str(context.get('category') or '').lower()
    comparison = category == 'comparison' or len(headline_assets) > 1
    if not comparison and foreign:
        failures.append('non_comparison_story_contains_other_cashtag')

    result = {
        'version': 1,
        'publish': not failures,
        'draft_path': str(draft_path),
        'frozen_symbol': frozen_symbol,
        'cashtags': sorted(cashtags),
        'headline_assets': sorted(headline_assets),
        'allowed_assets': sorted(allowed),
        'failures': failures,
        'policy': 'The frozen portfolio asset is immutable through final publication; drift blocks publication rather than falling back to BTC.',
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
