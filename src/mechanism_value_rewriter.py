"""Evidence-preserving repair for drafts that describe facts without explaining the causal mechanism."""
from __future__ import annotations
import json, os, re, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / 'data/reports'
OUT = ROOT / 'data/live/mechanism_value_repair.json'


def load(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def latest_report():
    reports = sorted(REPORT_DIR.glob('*-multi-agent.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def resolve_report():
    explicit = os.getenv('DRAFT_PATH', '').strip()
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise SystemExit(f'Mechanism repair: DRAFT_PATH does not exist: {explicit}')
        return path
    return latest_report()


def norm(value):
    return re.sub(r'\s+', ' ', str(value or '').strip())


def questions(text):
    return re.findall(r'[^\n.!?]*\?', text)


def mechanism_present(text):
    low = text.lower()
    terms = (
        'because', 'driven by', 'explains why', 'the reason', 'which means',
        'leads to', 'causes', 'due to', 'means that', 'translates into',
        'shows up in', 'flows into', 'results in', 'comes from', 'depends on',
        'hinges on', 'works through', 'is linked to', 'matters because',
        'suggests that', 'implies that', 'so the effect', 'this matters because',
        'in turn', 'which can make', 'which can leave'
    )
    return any(term in low for term in terms)


def gemini(prompt):
    key = os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        return ''
    model = os.getenv('GEMINI_MODEL', 'gemini-3.6-flash').strip()
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.35, 'maxOutputTokens': 1000},
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=40) as response:
            data = json.loads(response.read().decode())
        parts = ((data.get('candidates') or [{}])[0].get('content') or {}).get('parts') or []
        return str(parts[0].get('text', '')).strip() if parts else ''
    except Exception:
        return ''


def clean(value):
    value = str(value or '').strip()
    value = re.sub(r'^```(?:text|markdown)?\s*|\s*```$', '', value, flags=re.I | re.S)
    value = re.sub(r'^post\s*:\s*', '', value, flags=re.I)
    return value.strip()


def explicit_facts(text):
    facts = set(re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b', text))
    facts |= set(re.findall(r'\b\d+(?:\.\d+)?%', text))
    facts |= set(re.findall(r'\$[\d,]+(?:\.\d+)?(?:\s*[KMBkmb])?\b', text))
    return facts


def strip_markdown(text):
    text = re.sub(r'^\s*[*-]\s*', '', text, flags=re.M)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.M)
    return text.strip()


def replace_or_restore_question(original, candidate):
    oq = questions(original)
    cq = questions(candidate)
    if len(oq) != 1:
        return candidate, 'ORIGINAL_QUESTION_COUNT_NOT_ONE'
    if len(cq) == 1:
        return candidate, None
    # The model is not allowed to lose the exact reader question. Remove any
    # question fragments from the candidate, then append the original question.
    candidate = re.sub(r'[^\n.!?]*\?', '', candidate).strip()
    candidate = f'{candidate}\n\n{oq[0].strip()}' if candidate else oq[0].strip()
    return candidate, 'QUESTION_RESTORED'


def main():
    report = resolve_report()
    if not report:
        raise SystemExit('Mechanism repair: no draft report')

    data = load(report)
    draft = data.get('draft') or {}
    original = str(draft.get('post') or draft.get('text') or '').strip()
    report_path = str(report)
    if not original:
        raise SystemExit(f'Mechanism repair: draft has no post text: {report_path}')

    if mechanism_present(original):
        result = {'status': 'NOT_NEEDED', 'mechanism_present': True, 'draft_path': report_path}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
        return 0

    original_questions = questions(original)
    original_question = original_questions[0].strip() if len(original_questions) == 1 else ''
    prompt = f'''You are the final senior editor for a Binance Square crypto post. The draft has evidence but does not clearly explain WHY the supplied facts matter and HOW they connect to the implication.

Rewrite the post while preserving every verified fact, number, cashtag, attribution, caveat, and the core meaning of the existing reader question.

STRICT RULES:
- Do not add any new fact, number, source, prediction, price target, event, personal experience, or certainty claim.
- Do not turn a hypothesis into a fact.
- Add at least one explicit causal relationship using natural language such as "because", "which means", "depends on", "leads to", "the reason", "in turn", or equivalent.
- Explain the mechanism plainly: fact -> process/relationship -> implication.
- Keep the existing counterpoint/invalidation or confirmation condition.
- Do NOT write any question yourself. The system will restore the exact original question after your rewrite.
- Keep the first-line hook unless a small grammatical change is required.
- No generic engagement bait, no hype promises, no emoji stacks, no new "Source:" line.
- Return ONLY the rewritten post body, with normal paragraphs/bullets and no analysis, labels, or markdown fences.

ORIGINAL DRAFT:
{original[:9000]}'''

    candidate = strip_markdown(clean(gemini(prompt)))
    required = explicit_facts(original)
    candidate_facts = explicit_facts(candidate)
    reasons = []

    if not candidate:
        reasons.append('GEMINI_NO_OUTPUT')
    if candidate and not mechanism_present(candidate):
        reasons.append('MECHANISM_STILL_MISSING')
    missing = sorted(required - candidate_facts)
    if missing:
        reasons.append('MISSING_EXPLICIT_FACTS:' + ','.join(missing))

    candidate, q_reason = replace_or_restore_question(original, candidate)
    if q_reason == 'ORIGINAL_QUESTION_COUNT_NOT_ONE':
        reasons.append(q_reason)
    elif q_reason == 'QUESTION_RESTORED':
        reasons.append(q_reason)

    # Re-check after restoration. The restored question is an exact carry-over;
    # all non-question content must still satisfy the mechanism and evidence checks.
    if candidate and len(questions(candidate)) != 1:
        reasons.append('QUESTION_COUNT_CHANGED')
    if original_question and original_question not in candidate:
        reasons.append('ORIGINAL_QUESTION_NOT_PRESERVED')

    safe = not any(r for r in reasons if r not in {'QUESTION_RESTORED'}) and bool(candidate)
    if not safe:
        result = {
            'status': 'REPAIR_FAILED',
            'mechanism_present': mechanism_present(candidate),
            'draft_unchanged': True,
            'draft_path': report_path,
            'reasons': reasons,
            'required_facts': sorted(required),
            'candidate_preview': candidate[:500] if candidate else '',
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
        return 0

    draft['post'] = candidate
    draft['text'] = candidate
    draft['mechanism_value_repair'] = {
        'status': 'REPAIRED',
        'verified_facts_preserved': True,
        'exactly_one_question': True,
        'mechanism_present': True,
        'draft_path': report_path,
    }
    data['draft'] = draft
    data['mechanism_value_repair'] = draft['mechanism_value_repair']
    Path(report).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    result = {
        'status': 'REPAIRED',
        'verified_facts_preserved': True,
        'exactly_one_question': True,
        'mechanism_present': True,
        'draft_path': report_path,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
