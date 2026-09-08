"""Repair near-duplicate hooks without weakening the hard integrity gate."""
from __future__ import annotations
import json, os, re, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / 'data/reports'
CONTEXT = ROOT / 'data/live/publication_context.json'
PREFLIGHT = ROOT / 'data/live/editorial_preflight.json'
PUBLICATIONS = ROOT / 'analytics/publication_log.jsonl'
OUT = ROOT / 'data/live/hook_diversity_repair.json'


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
    return re.sub(r'\s+', ' ', str(value or '').strip())


def tokens(value):
    return set(re.findall(r'[a-z0-9$]+', str(value).lower()))


def similarity(a, b):
    left, right = tokens(a), tokens(b)
    return len(left & right) / max(1, len(left | right))


def recent_hooks():
    result = []
    if not PUBLICATIONS.exists():
        return result
    cutoff = datetime.now(timezone.utc) - timedelta(hours=36)
    for line in PUBLICATIONS.read_text(encoding='utf-8').splitlines()[-80:]:
        try:
            record = json.loads(line)
            dt = datetime.fromisoformat(str(record.get('published_at', '')).replace('Z', '+00:00'))
            hook = norm(record.get('hook'))
            if hook and dt >= cutoff:
                result.append(hook)
        except Exception:
            pass
    return result


def gemini(prompt):
    key = os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        return ''
    model = os.getenv('GEMINI_MODEL', 'gemini-3.6-flash').strip()
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.85, 'maxOutputTokens': 180},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
        candidates = data.get('candidates') or []
        if not candidates:
            return ''
        content = candidates[0].get('content') or {}
        parts = content.get('parts') or []
        if not parts:
            return ''
        return norm(parts[0].get('text', ''))
    except Exception:
        return ''


def clean_candidate(value):
    value = norm(value).strip('"“”\'')
    value = re.sub(r'^(hook|alternative hook)\s*:\s*', '', value, flags=re.I)
    return value.split('\n')[0].strip()


def fallback(symbol, body, recent):
    sentences = re.split(r'(?<=[.!?])\s+', norm(body))
    for sentence in sentences:
        low = sentence.lower()
        if len(sentence) >= 35 and not low.startswith(('source:', '🚨')) and '?' not in sentence:
            insight = ' '.join(sentence.split()[:18]).rstrip('.,:;')
            candidate = f"The useful signal in ${symbol} is the evidence behind the move: {insight}."
            if not any(similarity(candidate, hook) >= 0.68 for hook in recent):
                return candidate
    candidate = f"For ${symbol}, the evidence behind the move matters more than repeating the latest headline."
    if not any(similarity(candidate, hook) >= 0.68 for hook in recent):
        return candidate
    return f"A better read on ${symbol} starts with what the current evidence actually supports."


def main():
    report = latest_report()
    if not report:
        raise SystemExit('No fresh draft report')

    data = load(report)
    draft = data.get('draft') or {}
    original_text = str(draft.get('post') or draft.get('text') or '')
    text = norm(original_text)
    if not text:
        raise SystemExit('Draft has no post text')

    lines = [line.strip() for line in original_text.splitlines() if line.strip()]
    hook = lines[0] if lines else ''
    recent = recent_hooks()
    near = [
        (round(similarity(hook, old_hook), 2), old_hook)
        for old_hook in recent
        if similarity(hook, old_hook) >= 0.68
    ]

    if not near:
        OUT.write_text(
            json.dumps({'status': 'NOT_NEEDED', 'original_hook': hook, 'matches': []}, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        print(json.dumps({'status': 'NOT_NEEDED', 'hook': hook}, ensure_ascii=False))
        return

    context = load(CONTEXT)
    preflight = load(PREFLIGHT)
    selected = preflight.get('selected_opportunity') or {}
    symbol = str(
        context.get('symbol') or selected.get('symbol') or draft.get('symbol') or ''
    ).upper().replace('$', '').replace('USDT', '').strip()
    headline = norm(context.get('news_title') or selected.get('news_title') or draft.get('news_title'))
    body = '\n'.join(lines[1:])

    prompt = f'''You are the final hook editor for a high-quality Binance Square crypto post.
The current hook is too similar to a recent post. Replace ONLY the first line with a genuinely different semantic angle.
Primary asset: ${symbol}
Verified news headline that MUST remain elsewhere in the post verbatim: {headline}
Current body (DO NOT rewrite it):
{body[:6500]}
Recent hooks to avoid:
{json.dumps([hook for _, hook in near[:8]], ensure_ascii=False)}
Rules: use only facts already present in the supplied body/headline; do not add numbers, events, predictions, targets, sentiment claims, whale activity or urgency. Do not repeat the headline. Do not start with the ticker plus a percentage. Do not use generic hooks such as "fresh check" or "quick market check". Make the hook 12-24 words, specific to the evidence or implication in this post, and clearly different in wording and structure from every recent hook. Return ONLY the new hook, one line.'''

    candidate = clean_candidate(gemini(prompt))
    if not candidate:
        candidate = fallback(symbol, body, recent)

    if any(similarity(candidate, old_hook) >= 0.68 for old_hook in recent):
        candidate = fallback(symbol, body, recent)

    if not candidate or any(similarity(candidate, old_hook) >= 0.68 for old_hook in recent):
        OUT.write_text(
            json.dumps(
                {'status': 'REPAIR_FAILED', 'original_hook': hook, 'candidate': candidate, 'matches': near[:5]},
                indent=2,
                ensure_ascii=False,
            ),
            encoding='utf-8',
        )
        raise SystemExit('Could not produce a sufficiently distinct hook')

    lines[0] = candidate
    new_text = '\n\n'.join(lines)
    repair = {
        'status': 'REPAIRED',
        'original_hook': hook,
        'new_hook': candidate,
        'max_recent_similarity': max((similarity(candidate, old_hook) for old_hook in recent), default=0.0),
        'verified_body_preserved': True,
        'headline_preserved': headline.lower() in new_text.lower() if headline else True,
    }
    draft['post'] = new_text
    draft['text'] = new_text
    draft['hook_diversity_repair'] = repair
    data['draft'] = draft
    data['hook_diversity_repair'] = repair
    Path(report).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    OUT.write_text(
        json.dumps({
            'status': 'REPAIRED',
            'original_hook': hook,
            'new_hook': candidate,
            'blocked_matches': near[:5],
            'max_recent_similarity': repair['max_recent_similarity'],
            'report': str(report),
        }, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    print(json.dumps({
        'status': 'REPAIRED',
        'original_hook': hook,
        'new_hook': candidate,
        'max_recent_similarity': repair['max_recent_similarity'],
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
