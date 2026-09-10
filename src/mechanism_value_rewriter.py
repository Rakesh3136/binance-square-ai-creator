"""Evidence-preserving mechanism repair with anti-template protection.

The repair stage must improve causal clarity without injecting a stock sentence
that can be repeated across assets. Existing evidence and the single question
are preserved exactly; only a bounded mechanism sentence may be added/replaced.
"""
from __future__ import annotations
import json, os, re, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / 'data/reports'
OUT = ROOT / 'data/live/mechanism_value_repair.json'
PUBLICATION_LOG = ROOT / 'analytics/publication_log.jsonl'

MECHANISM_TERMS = (
    'because','driven by','explains why','the reason','which means','leads to',
    'causes','due to','means that','translates into','shows up in','flows into',
    'results in','comes from','depends on','hinges on','works through',
    'is linked to','matters because','suggests that','implies that','in turn',
    'which can make','which can leave','the mechanism','pathway','transmission'
)
GENERIC_BRIDGES = (
    r'the mechanism to watch is the link between .* and the conclusion in this draft',
    r'the reported fact matters because the conclusion depends on that fact translating into the effect described here',
    r'the mechanism to watch is the link between .* and the implication already described',
    r'the reported fact matters because it can only affect the market through the process or positioning described in the draft',
)


def load(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def resolve_report():
    explicit = os.getenv('DRAFT_PATH', '').strip()
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise SystemExit(f'Mechanism repair: DRAFT_PATH does not exist: {explicit}')
        return path
    reports = sorted(REPORT_DIR.glob('*-multi-agent.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def norm(value):
    return re.sub(r'\s+', ' ', str(value or '').strip())


def questions(text):
    return re.findall(r'[^\n.!?]*\?', text)


def mechanism_present(text):
    low = text.lower()
    return any(term in low for term in MECHANISM_TERMS)


def generic_bridge(sentence):
    low = norm(sentence).lower()
    return any(re.search(pattern, low, re.I) for pattern in GENERIC_BRIDGES)


def sentences(text):
    return [norm(s) for s in re.split(r'(?<=[.!])\s+', text) if norm(s)]


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


def recent_repetitions(text):
    if not PUBLICATION_LOG.exists():
        return []
    current = {re.sub(r'[^a-z0-9 ]', '', s.lower()).strip() for s in sentences(text) if len(s.split()) >= 8}
    if not current:
        return []
    matches = []
    try:
        for row in PUBLICATION_LOG.read_text(encoding='utf-8').splitlines()[-12:]:
            try:
                obj = json.loads(row)
            except Exception:
                continue
            old = str(obj.get('text') or obj.get('post') or obj.get('content') or '')
            oldset = {re.sub(r'[^a-z0-9 ]', '', s.lower()).strip() for s in sentences(old) if len(s.split()) >= 8}
            matches.extend(sorted(current & oldset))
    except Exception:
        pass
    return matches[:8]


def gemini(prompt):
    key = os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        return ''
    model = os.getenv('GEMINI_MODEL', 'gemini-3.6-flash').strip()
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    payload = {'contents':[{'parts':[{'text':prompt}]}], 'generationConfig':{'temperature':0.35,'maxOutputTokens':300}}
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=40) as response:
            data = json.loads(response.read().decode())
        parts = ((data.get('candidates') or [{}])[0].get('content') or {}).get('parts') or []
        return str(parts[0].get('text','')).strip() if parts else ''
    except Exception:
        return ''


def clean_candidate(value):
    value = strip_markdown(value)
    value = re.sub(r'^```(?:text|markdown)?\s*|\s*```$', '', value, flags=re.I | re.S).strip()
    value = re.sub(r'^sentence\s*:\s*', '', value, flags=re.I).strip()
    value = re.sub(r'\?+', '.', value).strip()
    if '\n' in value:
        value = next((x.strip() for x in value.splitlines() if x.strip()), '')
    return value


def choose_replacement(original, offending, repetitions):
    body = original
    if offending:
        body = body.replace(offending, '').strip()
    prompt = f'''Write ONE natural mechanism sentence for this existing Binance Square post.

The sentence must connect an EXISTING fact in the post to an EXISTING implication, joke, contrast, or observable market reaction. Do not invent facts, prices, targets, sources, outcomes, or predictions.
Do not use stock phrasing such as "the mechanism to watch", "the link between", "the conclusion in this draft", "the reported fact matters because", or "the effect described here".
Do not mention drafts, mechanisms, prompts, templates, conclusions, or instructions.
Sound like a human crypto creator. Make the sentence specific to the asset/context already present.
Return ONLY one sentence.

RECENT SENTENCES TO AVOID REPEATING:
{json.dumps(repetitions, ensure_ascii=False)}

POST:
{body[:9000]}'''
    candidate = clean_candidate(gemini(prompt))
    if candidate and mechanism_present(candidate) and not generic_bridge(candidate):
        return candidate
    return ''


def deterministic_bridge(original):
    """Last-resort bridge built from existing wording, never from invented data."""
    parts = sentences(original)
    topic = (re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b', original) or ['this setup'])[0]
    implication = next((s for s in parts if any(x in s.lower() for x in ('because','could','may','might','matters','means','risk','watch','signal','reaction'))), '')
    if implication and implication != parts[0]:
        return f'For {topic}, that makes the next reaction more informative than the headline itself because {implication[0].lower() + implication[1:]}'
    return f'{topic} is interesting here because the next observable reaction is what will tell us whether this read holds.'


def build_candidate(original):
    qs = questions(original)
    question = qs[0].strip() if len(qs) == 1 else ''
    body = original
    offending = ''
    for s in sentences(original):
        if generic_bridge(s):
            offending = s
            body = body.replace(s, '').strip()
            break
    repetitions = recent_repetitions(body)
    bridge = choose_replacement(body, offending, repetitions) or deterministic_bridge(body)
    candidate = f'{body}\n\n{bridge}'.strip()
    if question:
        candidate = f'{candidate}\n\n{question}'
    return candidate, offending, bridge


def main():
    report = resolve_report()
    if not report:
        raise SystemExit('Mechanism repair: no draft report')
    data = load(report); draft = data.get('draft') or {}
    original = str(draft.get('post') or draft.get('text') or '').strip()
    if not original:
        raise SystemExit(f'Mechanism repair: draft has no post text: {report}')

    qs = questions(original)
    offending = next((s for s in sentences(original) if generic_bridge(s)), '')
    needs_repair = bool(offending) or not mechanism_present(original)
    if not needs_repair:
        result = {'status':'NOT_NEEDED','mechanism_present':True,'draft_path':str(report)}
        OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(result, indent=2), encoding='utf-8'); print(json.dumps(result)); return 0
    if len(qs) != 1:
        result = {'status':'REPAIR_FAILED','draft_unchanged':True,'draft_path':str(report),'reasons':['ORIGINAL_QUESTION_COUNT_NOT_ONE']}
        OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(result, indent=2), encoding='utf-8'); print(json.dumps(result)); return 0

    candidate, removed, bridge = build_candidate(original)
    required = explicit_facts(original)
    reasons=[]
    if not bridge or generic_bridge(bridge): reasons.append('BAD_MECHANISM_BRIDGE')
    if not mechanism_present(candidate): reasons.append('MECHANISM_STILL_MISSING')
    if sorted(required - explicit_facts(candidate)): reasons.append('EXPLICIT_FACT_LOSS')
    if len(questions(candidate)) != 1: reasons.append('QUESTION_COUNT_CHANGED')
    if qs[0].strip() not in candidate: reasons.append('ORIGINAL_QUESTION_NOT_PRESERVED')
    if recent_repetitions(candidate): reasons.append('RECENT_SENTENCE_REPETITION_AFTER_REPAIR')

    if reasons:
        result={'status':'REPAIR_FAILED','draft_unchanged':True,'draft_path':str(report),'reasons':reasons,'removed_generic_bridge':removed,'candidate_preview':candidate[:900]}
        OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8'); print(json.dumps(result, indent=2, ensure_ascii=False)); return 0

    draft['post']=candidate; draft['text']=candidate; draft['mechanism_value_repair']={'status':'REPAIRED','verified_facts_preserved':True,'exactly_one_question':True,'mechanism_present':True,'generic_bridge_removed':bool(removed),'recent_repetition_blocked':True}
    data['draft']=draft; data['mechanism_value_repair']=draft['mechanism_value_repair']
    Path(report).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    result={'status':'REPAIRED','verified_facts_preserved':True,'exactly_one_question':True,'mechanism_present':True,'generic_bridge_removed':bool(removed),'draft_path':str(report)}
    OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8'); print(json.dumps(result, indent=2, ensure_ascii=False)); return 0

if __name__ == '__main__':
    raise SystemExit(main())
