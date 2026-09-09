"""Evidence-preserving repair for drafts that describe facts without explaining the causal mechanism."""
from __future__ import annotations
import json, os, re, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT_DIR=ROOT/'data/reports'; OUT=ROOT/'data/live/mechanism_value_repair.json'


def load(path):
    try:
        v=json.loads(Path(path).read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:
        return {}


def latest_report():
    xs=sorted(REPORT_DIR.glob('*-multi-agent.json'), key=lambda p:p.stat().st_mtime, reverse=True)
    return xs[0] if xs else None


def norm(v): return re.sub(r'\s+', ' ', str(v or '').strip())


def mechanism_present(text):
    low=text.lower()
    terms=('because','driven by','explains why','the reason','which means','leads to','causes','due to','means that','translates into','shows up in','flows into','results in','comes from','depends on','hinges on','works through','is linked to','matters because','suggests that','implies that','so the effect')
    return any(x in low for x in terms)


def question_count(text): return len(re.findall(r'[^\n.!?]*\?', text))


def gemini(prompt):
    key=os.getenv('GEMINI_API_KEY','').strip()
    if not key: return ''
    model=os.getenv('GEMINI_MODEL','gemini-3.6-flash').strip()
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    payload={'contents':[{'parts':[{'text':prompt}]}], 'generationConfig':{'temperature':0.45,'maxOutputTokens':900}}
    try:
        req=urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=40) as response: data=json.loads(response.read().decode())
        parts=((data.get('candidates') or [{}])[0].get('content') or {}).get('parts') or []
        return str(parts[0].get('text','')).strip() if parts else ''
    except Exception:
        return ''


def clean(v):
    v=str(v or '').strip()
    v=re.sub(r'^```(?:text)?\s*|\s*```$', '', v, flags=re.I|re.S)
    v=re.sub(r'^post\s*:\s*', '', v, flags=re.I)
    return v.strip()


def main():
    report=latest_report()
    if not report: raise SystemExit('Mechanism repair: no draft report')
    data=load(report); draft=data.get('draft') or {}; original=norm(draft.get('post') or draft.get('text') or '')
    if not original: raise SystemExit('Mechanism repair: draft has no post text')
    if mechanism_present(original):
        result={'status':'NOT_NEEDED','mechanism_present':True}
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result)); return 0

    prompt=f'''You are the final senior editor for a Binance Square crypto post. The draft has evidence but does not clearly explain the mechanism: WHY the supplied facts matter and HOW they connect to the stated implication.

Rewrite the post, preserving every verified fact, number, ticker, attribution, caveat and question. You may reorder sentences and add concise reasoning that logically connects facts already present. Do NOT add any new fact, number, source, prediction, price target, event, personal experience or claim of certainty. Do NOT turn a hypothesis into a fact.

Editorial requirements:
- Keep the same core thesis and subject.
- Make at least one explicit causal relationship using natural language such as "because", "which means", "depends on", "leads to", "the reason", or equivalent.
- Explain the mechanism in plain language: fact -> process/relationship -> implication.
- Keep the counterpoint/invalidation or confirmation condition.
- Keep exactly ONE genuine reader question; preserve its meaning.
- Keep the first-line hook unless a small wording change is required for grammatical flow.
- No generic engagement bait, no hype promises, no emoji stacks, no "Source:" line unless one already exists.
- Return ONLY the finished post text.

ORIGINAL DRAFT:
{original[:9000]}'''
    candidate=clean(gemini(prompt))
    safe=False
    if candidate and question_count(candidate)==1 and mechanism_present(candidate):
        # Hard evidence-preservation checks: all explicit tickers and percentage values in the original must remain.
        orig_tokens=set(re.findall(r'\$[A-Z][A-Z0-9]{1,14}|\b[A-Z]{2,10}\b|\b\d+(?:\.\d+)?%', original))
        cand_tokens=set(re.findall(r'\$[A-Z][A-Z0-9]{1,14}|\b[A-Z]{2,10}\b|\b\d+(?:\.\d+)?%', candidate))
        safe=orig_tokens.issubset(cand_tokens)
    if not safe:
        result={'status':'REPAIR_FAILED','mechanism_present':False,'draft_unchanged':True}
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result)); return 0

    draft['post']=candidate; draft['text']=candidate; draft['mechanism_value_repair']={'status':'REPAIRED','verified_facts_preserved':True,'exactly_one_question':True,'mechanism_present':True}
    data['draft']=draft; data['mechanism_value_repair']=draft['mechanism_value_repair']
    Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'status':'REPAIRED','verified_facts_preserved':True,'exactly_one_question':True,'mechanism_present':True}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result)); return 0

if __name__=='__main__': raise SystemExit(main())
