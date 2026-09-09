"""Evidence-preserving repair for drafts that describe facts without explaining the causal mechanism."""
from __future__ import annotations
import json, os, re, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT_DIR=ROOT/'data/reports'; OUT=ROOT/'data/live/mechanism_value_repair.json'

def load(path):
    try:
        v=json.loads(Path(path).read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception: return {}

def latest_report():
    p=os.getenv('DRAFT_PATH','').strip()
    if p:
        q=Path(p)
        if q.exists(): return q
        raise SystemExit(f'Mechanism repair: DRAFT_PATH does not exist: {p}')
    xs=sorted(REPORT_DIR.glob('*-multi-agent.json'), key=lambda p:p.stat().st_mtime, reverse=True)
    return xs[0] if xs else None

def norm(v): return re.sub(r'\s+', ' ', str(v or '').strip())

def mechanism_present(text):
    low=text.lower()
    terms=('because','driven by','explains why','the reason','which means','leads to','causes','due to','means that','translates into','shows up in','flows into','results in','comes from','depends on','hinges on','works through','is linked to','matters because','suggests that','implies that','so the effect')
    return any(x in low for x in terms)

def question_count(text): return len(re.findall(r'[^\n.!?]*\?', text))

def explicit_tokens(text):
    return set(re.findall(r'\$[A-Z][A-Z0-9]{1,14}|\b\d+(?:\.\d+)?%', text))

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
    except Exception as exc:
        print(json.dumps({'status':'GEMINI_ERROR','error':type(exc).__name__}))
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
        result={'status':'NOT_NEEDED','mechanism_present':True,'draft_path':str(report)}
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result)); return 0
    prompt=f'''You are the final senior editor for a Binance Square crypto post. The draft has evidence but does not clearly explain the mechanism: WHY the supplied facts matter and HOW they connect to the stated implication.\n\nRewrite the post, preserving every verified fact, number, ticker, attribution, caveat and question. You may reorder sentences and add concise reasoning that logically connects facts already present. Do NOT add any new fact, number, source, prediction, price target, event, personal experience or claim of certainty. Do NOT turn a hypothesis into a fact.\n\nEditorial requirements:\n- Keep the same core thesis and subject.\n- Make at least one explicit causal relationship using natural language such as "because", "which means", "depends on", "leads to", "the reason", or equivalent.\n- Explain the mechanism in plain language: fact -> process/relationship -> implication.\n- Keep the counterpoint/invalidation or confirmation condition.\n- Keep exactly ONE genuine reader question; preserve its meaning.\n- Keep the first-line hook unless a small wording change is required for grammatical flow.\n- No generic engagement bait, no hype promises, no emoji stacks, no "Source:" line unless one already exists.\n- Return ONLY the finished post text.\n\nORIGINAL DRAFT:\n{original[:9000]}'''
    candidate=clean(gemini(prompt))
    safe=False; failure_reason='no_candidate'
    if candidate:
        if question_count(candidate)!=1: failure_reason='question_count_changed'
        elif not mechanism_present(candidate): failure_reason='mechanism_still_missing'
        elif not explicit_tokens(original).issubset(explicit_tokens(candidate)): failure_reason='explicit_facts_changed'
        else: safe=True
    if not safe:
        result={'status':'REPAIR_FAILED','mechanism_present':False,'draft_unchanged':True,'draft_path':str(report),'reason':failure_reason,'original_explicit_tokens':sorted(explicit_tokens(original)),'candidate_preview':candidate[:500]}
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,ensure_ascii=False)); return 0
    draft['post']=candidate; draft['text']=candidate; draft['mechanism_value_repair']={'status':'REPAIRED','verified_facts_preserved':True,'exactly_one_question':True,'mechanism_present':True}
    data['draft']=draft; data['mechanism_value_repair']=draft['mechanism_value_repair']
    Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'status':'REPAIRED','verified_facts_preserved':True,'exactly_one_question':True,'mechanism_present':True,'draft_path':str(report)}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result)); return 0

if __name__=='__main__': raise SystemExit(main())
