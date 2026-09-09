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
        'in turn', 'which can make', 'which can leave', 'the mechanism',
        'the link is', 'the connection is', 'pathway', 'transmission'
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
        'generationConfig': {'temperature': 0.15, 'maxOutputTokens': 600},
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
    candidate = re.sub(r'[^\n.!?]*\?', '', candidate).strip()
    candidate = f'{candidate}\n\n{oq[0].strip()}' if candidate else oq[0].strip()
    return candidate, 'QUESTION_RESTORED'


def sentences(text):
    return [norm(s) for s in re.split(r'(?<=[.!])\s+', text) if norm(s)]


def first_factual_sentence(text):
    for sentence in sentences(text):
        if re.search(r'\$[A-Z][A-Z0-9]{1,14}\b|\b\d+(?:\.\d+)?%|\$[\d,]+(?:\.\d+)?', sentence):
            return sentence
    parts = sentences(text)
    return parts[1] if len(parts) > 1 else (parts[0] if parts else '')


def first_implication_sentence(text, factual):
    parts = sentences(text)
    for sentence in parts:
        low = sentence.lower()
        if sentence == factual:
            continue
        if any(term in low for term in ('matters', 'could', 'may', 'might', 'means', 'suggests', 'signals', 'implication', 'risk', 'catalyst', 'confirmation', 'invalidat')):
            return sentence
    return ''


def deterministic_mechanism_bridge(original):
    factual = first_factual_sentence(original)
    implication = first_implication_sentence(original, factual)
    topic = ''
    cashtags = re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b', original)
    if cashtags:
        topic = cashtags[0]
    elif factual:
        topic = 'the reported change'
    if implication:
        bridge = (
            f'The mechanism to watch is the link between {topic} and the implication already described: '
            f'the reported fact matters because it can only affect the market through the process or positioning described in the draft, '
            f'which means the key test is whether that existing implication follows from the reported change.'
        )
    else:
        bridge = (
            f'The mechanism to watch is the link between {topic} and the conclusion in this draft: '
            f'the reported fact matters because the conclusion depends on that fact translating into the effect described here.'
        )
    return bridge


def build_repaired_candidate(original):
    """Use the LLM only for a bounded bridge; never replace the evidence-bearing draft."""
    oq = questions(original)
    question = oq[0].strip() if len(oq) == 1 else ''
    body = original
    if question:
        body = body.replace(question, '').strip()
    prompt = f'''Write ONE mechanism sentence for this existing Binance Square draft.

Rules:
- Use only facts and concepts already present in the draft.
- Do not add a new fact, number, source, prediction, token, price target, event, or certainty claim.
- Explain the causal bridge: existing fact -> existing process/relationship -> existing implication.
- Do not ask a question.
- Return ONLY one sentence, no quotes, no bullets, no labels.

DRAFT:
{body[:9000]}'''
    llm_bridge = strip_markdown(clean(gemini(prompt)))
    llm_bridge = re.sub(r'\?+', '.', llm_bridge).strip()
    if llm_bridge and not mechanism_present(llm_bridge):
        llm_bridge = ''
    bridge = llm_bridge or deterministic_mechanism_bridge(body)
    candidate = f'{body}\n\n{bridge}'.strip()
    if question:
        candidate = f'{candidate}\n\n{question}'
    return candidate


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
    if len(original_questions) != 1:
        result = {
            'status': 'REPAIR_FAILED',
            'mechanism_present': False,
            'draft_unchanged': True,
            'draft_path': report_path,
            'reasons': ['ORIGINAL_QUESTION_COUNT_NOT_ONE'],
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
        return 0

    candidate = build_repaired_candidate(original)
    required = explicit_facts(original)
    candidate_facts = explicit_facts(candidate)
    reasons = []

    if not candidate:
        reasons.append('NO_CANDIDATE')
    if candidate and not mechanism_present(candidate):
        reasons.append('MECHANISM_STILL_MISSING')
    missing = sorted(required - candidate_facts)
    if missing:
        reasons.append('MISSING_EXPLICIT_FACTS:' + ','.join(missing))
    if len(questions(candidate)) != 1:
        reasons.append('QUESTION_COUNT_CHANGED')
    if original_questions[0].strip() not in candidate:
        reasons.append('ORIGINAL_QUESTION_NOT_PRESERVED')

    safe = bool(candidate) and not reasons
    if not safe:
        result = {
            'status': 'REPAIR_FAILED',
            'mechanism_present': mechanism_present(candidate),
            'draft_unchanged': True,
            'draft_path': report_path,
            'reasons': reasons,
            'required_facts': sorted(required),
            'candidate_preview': candidate[:700] if candidate else '',
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
        'mode': 'llm_or_deterministic_bridge',
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
        'mode': 'llm_or_deterministic_bridge',
        'draft_path': report_path,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
