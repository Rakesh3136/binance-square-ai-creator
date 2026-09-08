"""Repair a missing selected-news headline without rewriting verified draft content.

The integrity gate remains hard: this step only restores the exact selected headline
when the publication context says the post is news-selected and the draft omitted it.
No market facts, numbers, claims, or body sentences are rewritten.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / 'data/reports'
CONTEXT = ROOT / 'data/live/publication_context.json'
PREFLIGHT = ROOT / 'data/live/editorial_preflight.json'
OUT = ROOT / 'data/live/news_headline_integrity_repair.json'


def load(path, default=None):
    if default is None:
        default = {}
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def latest_report():
    reports = sorted(REPORT_DIR.glob('*-multi-agent.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def norm(value):
    return ' '.join(str(value or '').split())


def main():
    report = latest_report()
    if not report:
        raise SystemExit('No fresh draft report')

    data = load(report)
    draft = data.get('draft') or {}
    original = str(draft.get('post') or draft.get('text') or '').strip()
    context = load(CONTEXT)
    preflight = load(PREFLIGHT)
    selected = preflight.get('selected_opportunity') or {}
    headline = norm(context.get('news_title') or selected.get('news_title') or draft.get('news_title'))
    selected_news = bool(headline)

    if not selected_news:
        result = {'status': 'NOT_NEWS_SELECTED', 'repaired': False}
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
        return

    if not original:
        raise SystemExit('Draft has no post text')

    if headline.lower() in original.lower():
        result = {'status': 'NOT_NEEDED', 'repaired': False, 'headline': headline}
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
        return

    lines = [line.strip() for line in original.splitlines() if line.strip()]
    if not lines:
        raise SystemExit('Draft has no usable lines')

    # Keep the hook untouched. Add the exact verified headline immediately after it.
    new_text = lines[0] + '\n\nSource: ' + headline + '\n\n' + '\n\n'.join(lines[1:])
    draft['post'] = new_text
    draft['text'] = new_text
    draft['news_headline_integrity_repair'] = {
        'status': 'REPAIRED',
        'headline': headline,
        'verified_headline_inserted_verbatim': True,
        'body_rewritten': False,
        'repaired_at': datetime.now(timezone.utc).isoformat(),
    }
    data['draft'] = draft
    data['news_headline_integrity_repair'] = draft['news_headline_integrity_repair']
    Path(report).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    result = {
        'status': 'REPAIRED',
        'repaired': True,
        'headline': headline,
        'body_rewritten': False,
        'report': str(report),
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
