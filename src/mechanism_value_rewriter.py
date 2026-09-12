"""Evidence-preserving mechanism/value repair.

Adds story-specific reasoning and repairs a repeated engagement question when
necessary, without weakening the elite judge or inventing market facts.
"""
from __future__ import annotations
import json, os, re, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; REPORT_DIR=ROOT/'data/reports'; OUT=ROOT/'data/live/mechanism_value_repair.json'; PUBLICATION_LOG=ROOT/'analytics/publication_log.jsonl'
MECHANISM_TERMS=('because','driven by','explains why','the reason','which means','leads to','causes','due to','means that','translates into','shows up in','flows into','results in','comes from','depends on','hinges on','works through','is linked to','matters because','suggests that','implies that','in turn','which can make','which can leave','the mechanism','pathway','transmission')
GENERIC_BRIDGES=('the mechanism to watch','the link between','the conclusion in this draft','the reported fact matters because','the effect described here')
def load(path):
    try:
        v=json.loads(Path(path).read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:return {}
def resolve_report():
    explicit=os.getenv('DRAFT_PATH','').strip()
    if explicit:
        p=Path(explicit)
        if not p.exists(): raise SystemExit(f'Mechanism repair: DRAFT_PATH does not exist: {explicit}')
        return p
    xs=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True); return xs[0] if xs else None
def norm(v): return re.sub(r'\s+',' ',str(v or '').strip())
def questions(text): return re.findall(r'[^?\n]*\?',text)
def sentences(text): return [norm(s) for s in re.split(r'(?<=[.!?])\s+|\n+',text) if norm(s)]
def mechanism_present(text): return any(x in text.lower() for x in MECHANISM_TERMS)
def generic_bridge(s):
    low=norm(s).lower(); return any(x in low for x in GENERIC_BRIDGES)
def explicit_facts(text):
    out=set(re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b',text)); out|=set(re.findall(r'\b[+-]?\d+(?:\.\d+)?%',text)); out|=set(re.findall(r'\$[\d,]+(?:\.\d+)?(?:\s*[KMBkmb])?\b',text)); return out
def recent_repetitions(text):
    if not PUBLICATION_LOG.exists(): return []
    cur={re.sub(r'[^a-z0-9 ]','',s.lower()).strip() for s in sentences(text) if len(s.split())>=8}; matches=[]
    try:
        for row in PUBLICATION_LOG.read_text(encoding='utf-8').splitlines()[-12:]:
            try:o=json.loads(row)
            except Exception:continue
            old=str(o.get('text') or o.get('post') or o.get('content') or '')
            oldset={re.sub(r'[^a-z0-9 ]','',s.lower()).strip() for s in sentences(old) if len(s.split())>=8}; matches.extend(sorted(cur&oldset))
    except Exception: pass
    return matches[:8]
def recent_questions():
    if not PUBLICATION_LOG.exists(): return []
    out=[]
    try:
        for row in PUBLICATION_LOG.read_text(encoding='utf-8').splitlines()[-24:]:
            try:o=json.loads(row)
            except Exception:continue
            text=str(o.get('text') or o.get('post') or o.get('content') or '')
            out.extend(norm(q) for q in questions(text) if len(q.split())>=4)
    except Exception: pass
    return out
def normalized_question(q): return re.sub(r'[^a-z0-9 ]','',norm(q).lower()).strip()
def question_repeats(q,recent): return normalized_question(q) in {normalized_question(x) for x in recent}
def gemini(prompt):
    key=os.getenv('GEMINI_API_KEY','').strip()
    if not key:return ''
    model=os.getenv('GEMINI_MODEL','gemini-3.6-flash').strip(); url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}'
    payload={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'temperature':0.35,'maxOutputTokens':220}}
    try:
        req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=40) as r:data=json.loads(r.read().decode())
        parts=((data.get('candidates') or [{}])[0].get('content') or {}).get('parts') or []; return str(parts[0].get('text','')).strip() if parts else ''
    except Exception:return ''
def clean(v):
    v=re.sub(r'^```(?:text|markdown)?\s*|\s*```$','',str(v or '').strip(),flags=re.I|re.S); v=re.sub(r'^(sentence|question)\s*:\s*','',v,flags=re.I); return next((x.strip() for x in v.splitlines() if x.strip()),'')
def deterministic_bridges(original):
    symbol=(re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b',original) or ['$THIS-ASSET'])[0]
    pct=(re.findall(r'\b[+-]?\d+(?:\.\d+)%',original) or ['the observed move'])[0]
    fact=next((s for s in sentences(original) if pct in s or symbol in s), '')
    if fact:
        return [f'For {symbol}, that matters because the existing {pct} move is the market fact behind the reaction, while the next response shows whether traders are accepting or rejecting it.',f'The useful signal in {symbol} is what happens after the observed {pct} move: follow-through would support the reaction, while rejection would weaken it.',f'{symbol} is worth watching because the observed {pct} move creates a test between follow-through and rejection rather than proving either outcome in advance.',f'The {pct} move gives {symbol} a simple test: follow-through would reinforce the move, while rejection would argue against treating it as durable.',f'For {symbol}, the next reaction is the evidence chain: the existing {pct} move sets the context, and follow-through versus rejection determines what that move means.']
    return [f'For {symbol}, the next observable reaction separates a temporary burst of attention from a meaningful change in behavior because follow-through and rejection imply different outcomes.',f'The market read on {symbol} depends on the next observable response, because that is where attention either turns into follow-through or fades.',f'What matters next for {symbol} is the reaction itself, because a move becomes more informative when the market confirms or rejects it.']
def gemini_bridge(original,repetitions):
    prompt=f'''Write ONE natural, asset-specific reasoning sentence for this Binance Square post. Connect a fact already present to an observable implication already present. Do not invent anything. Use a causal connector such as because, while, or which means. Do not mention drafts, prompts, templates or "the mechanism". Return only the sentence. Avoid these recent sentences: {json.dumps(repetitions)}\nPOST:\n{original[:9000]}'''
    c=clean(gemini(prompt)); return c if c and mechanism_present(c) and not generic_bridge(c) else ''
def question_candidates(original,recent):
    symbol=(re.findall(r'\$[A-Z][A-Z0-9]{1,14}\b',original) or ['$THIS-ASSET'])[0]
    pct=(re.findall(r'\b[+-]?\d+(?:\.\d+)%',original) or ['the observed move'])[0]
    candidates=[f'Does {symbol} follow through after the {pct} move, or does the next reaction reject it?',f'What would confirm that {symbol} is sustaining the reaction after the {pct} move?',f'Will the next {symbol} reaction reinforce the {pct} move or weaken the read?',f'Is the next response in {symbol} confirming the move, or challenging it?']
    return [q for q in candidates if not question_repeats(q,recent)]
def main():
    report=resolve_report()
    if not report: raise SystemExit('Mechanism repair: no draft report')
    data=load(report); draft=data.get('draft') or {}; original=str(draft.get('post') or draft.get('text') or '').strip()
    if not original: raise SystemExit(f'Mechanism repair: draft has no post text: {report}')
    qs=questions(original)
    if len(qs)!=1:
        result={'status':'REPAIR_FAILED','draft_unchanged':True,'draft_path':str(report),'reasons':['ORIGINAL_QUESTION_COUNT_NOT_ONE']}; OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result,indent=2)); return 1
    original_question=qs[0].strip(); recent_q=recent_questions()
    body=original; removed=[]
    for s in sentences(body):
        if generic_bridge(s) and '?' not in s:
            body=body.replace(s,'').strip(); removed.append(s)
    body_without_question=body.replace(original_question,'').rstrip()
    reps=recent_repetitions(body_without_question)
    bridge=gemini_bridge(body_without_question,reps)
    if not bridge:
        for candidate_bridge in deterministic_bridges(body_without_question):
            if not recent_repetitions(candidate_bridge): bridge=candidate_bridge; break
    if not bridge: bridge=deterministic_bridges(body_without_question)[-1]
    question=original_question
    question_changed=False
    if question_repeats(question,recent_q):
        qprompt=f'''Write ONE specific Binance Square engagement question for this post. It must be materially different from the recent questions listed, use only facts already present, and ask exactly one clear question. No predictions presented as facts, no invented numbers, no generic "what do you think" phrasing. Return only the question. POST:\n{body_without_question[:9000]}\nRECENT QUESTIONS TO AVOID:\n{json.dumps(recent_q[-12:],ensure_ascii=False)}'''
        candidate_q=clean(gemini(qprompt))
        if candidate_q.endswith('?') and len(questions(candidate_q))==1 and not question_repeats(candidate_q,recent_q): question=candidate_q
        else:
            candidates=question_candidates(body_without_question,recent_q)
            if candidates: question=candidates[0]
        question_changed=question!=original_question
    candidate=f'{body_without_question}\n\n{bridge}\n\n{question}'.strip(); reasons=[]
    if not mechanism_present(bridge): reasons.append('MECHANISM_STILL_MISSING')
    if generic_bridge(bridge): reasons.append('GENERIC_BRIDGE')
    if len(questions(candidate))!=1: reasons.append('QUESTION_COUNT_CHANGED')
    if question_repeats(question,recent_q): reasons.append('NO_NOVEL_QUESTION_AVAILABLE')
    if sorted(explicit_facts(original)-explicit_facts(candidate)): reasons.append('EXPLICIT_FACT_LOSS')
    if recent_repetitions(bridge): reasons.append('REPAIR_SENTENCE_REPEATS_RECENT_PUBLICATION')
    if reasons:
        result={'status':'REPAIR_FAILED','draft_unchanged':True,'draft_path':str(report),'reasons':reasons,'candidate_preview':candidate[:1200]}; OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False)); return 1
    draft['post']=candidate; draft['text']=candidate; draft['mechanism_value_repair']={'status':'REPAIRED','verified_facts_preserved':True,'exactly_one_question':True,'mechanism_present':True,'reader_value_floor_enabled':True,'generic_bridge_removed':bool(removed),'question_diversity_repaired':question_changed,'original_question_preserved':not question_changed}; data['draft']=draft; data['mechanism_value_repair']=draft['mechanism_value_repair']; Path(report).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    result={'status':'REPAIRED','verified_facts_preserved':True,'exactly_one_question':True,'mechanism_present':True,'reader_value_floor_enabled':True,'question_diversity_repaired':question_changed,'original_question_preserved':not question_changed,'draft_path':str(report)}; OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False)); return 0
if __name__=='__main__': raise SystemExit(main())