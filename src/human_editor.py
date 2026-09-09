"""Creator 5.8 surgical human editor.

The editor is a preservation layer, not a second author. It must not replace a
specific hook with the news headline, inject generic CTAs, or flatten a strong
thesis into a template. Only deterministic, evidence-preserving cleanup is allowed.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NEWS=ROOT/'data/live/news_snapshot.json'; CONTEXT=ROOT/'data/live/publication_context.json'; OUT=ROOT/'data/live/editorial_polish.json'
ALIASES={'bitcoin':'BTC','btc':'BTC','ether':'ETH','ethereum':'ETH','eth':'ETH','binance coin':'BNB','bnb':'BNB','solana':'SOL','sol':'SOL','xrp':'XRP','ripple':'XRP','dogecoin':'DOGE','doge':'DOGE','cardano':'ADA','ada':'ADA','avalanche':'AVAX','avax':'AVAX','chainlink':'LINK','link':'LINK','zcash':'ZEC','zec':'ZEC','tron':'TRX','trx':'TRX','polkadot':'DOT','dot':'DOT','shiba inu':'SHIB','shib':'SHIB','sui':'SUI','toncoin':'TON','ton':'TON','pepe':'PEPE','floki':'FLOKI'}
GENERIC_PHRASES=('what do you think','thoughts?','comment below','like and follow','bullish or bearish?','the next reaction matters','the interesting part starts after the headline','this is interesting','fresh check','quick market check','here is what matters','here’s what matters')

def load(path,default=None):
    if default is None: default={}
    try:
        x=json.loads(path.read_text(encoding='utf-8'))
        return x if isinstance(x,type(default)) else default
    except Exception:return default

def norm(v):
    return re.sub(r'[ \t]+',' ',str(v or '')).strip()

def normalize_symbol(v):
    s=norm(v).upper().replace('$','').replace('BINANCE:','').strip(); s=re.sub(r'USDT$','',s)
    return s if re.fullmatch(r'[A-Z0-9]{1,15}',s) else ''

def title_assets(title):
    found=[]; low=norm(title).lower()
    for name,sym in sorted(ALIASES.items(),key=lambda x:-len(x[0])):
        if re.search(r'(?<![a-z0-9])'+re.escape(name)+r'(?![a-z0-9])',low) and sym not in found: found.append(sym)
    return found

def clean_question_count(text, original_question):
    lines=[norm(x) for x in text.splitlines() if norm(x)]
    # Keep the authored question when it is already unique. Otherwise preserve the
    # first meaningful question from the original draft rather than inventing a CTA.
    qs=[x for x in lines if x.endswith('?') or '?' in x]
    if len(qs)==1: return '\n\n'.join(lines)
    lines=[x.replace('?','.') for x in lines]
    if original_question:
        lines.append(original_question if original_question.endswith('?') else original_question+'?')
    return '\n\n'.join(lines)

def strip_unsupported_cashtags(text,allowed):
    def repl(m):
        sym=m.group(1).upper()
        return '$'+sym if sym in allowed else ''
    text=re.sub(r'\$([A-Z][A-Z0-9]{0,14})\b',repl,text,flags=re.I)
    text=re.sub(r'\n[ \t]+\n','\n\n',text)
    text=re.sub(r' {2,}',' ',text)
    return text.strip()

def surgical_cleanup(text):
    text=re.sub(r'\b(the market market|price price|volume volume|crypto crypto)\b',lambda m:m.group(1).split()[0],text,flags=re.I)
    text=re.sub(r'\n{3,}','\n\n',text)
    # Remove accidental model labels while preserving the actual prose.
    text=re.sub(r'^(post|draft|hook|answer|final)\s*:\s*','',text,flags=re.I)
    return text.strip()

def main():
    raw_path=os.getenv('DRAFT_PATH','').strip()
    path=Path(raw_path)
    if not path.exists(): raise SystemExit('DRAFT_PATH is missing')
    report=load(path,{})
    draft=report.setdefault('draft',{})
    original=norm(draft.get('post') or draft.get('text') or '')
    if not original: raise SystemExit('Draft has no post text')
    context=load(CONTEXT,{})
    selected=report.get('selected_editorial_lane') or report.get('selected_opportunity') or {}
    primary=normalize_symbol(context.get('symbol') or selected.get('symbol') or draft.get('symbol'))
    if not primary: raise SystemExit('Editorial layer: primary symbol missing')
    original_lines=[norm(x) for x in original.splitlines() if norm(x)]
    original_question=next((x for x in reversed(original_lines) if '?' in x), '')
    news_title=norm(context.get('news_title') or selected.get('news_title') or draft.get('news_title'))
    news_assets=set(title_assets(news_title)) if news_title else set()
    allowed={primary}|news_assets
    edited=surgical_cleanup(strip_unsupported_cashtags(original,allowed))
    edited=clean_question_count(edited,original_question)
    # Preserve the original hook and authored narrative. Never replace the hook with
    # the headline and never insert a generic engagement prompt.
    first_before=original_lines[0] if original_lines else ''
    first_after=next((x for x in edited.splitlines() if norm(x)), '')
    hook_preserved=(norm(first_before)==norm(first_after))
    generic_found=[p for p in GENERIC_PHRASES if p in edited.lower()]
    warnings=[]
    if not hook_preserved: warnings.append('hook_changed_by_cleanup')
    if generic_found: warnings.append('generic_phrase_present')
    # Source attribution is preserved when already supplied. We deliberately do not
    # fabricate or inject a source line here; the news-integrity stage owns that job.
    questions=re.findall(r'[^\n.!?]*\?',edited)
    if len(questions)!=1:
        raise SystemExit(f'Human editor refused unsafe question count: {len(questions)}')
    draft.update({'post':edited,'text':edited,'editorial_style':draft.get('editorial_style') or 'authored','human_editor':{'status':'PRESERVED','version':'human-editor-v16','hook_preserved':hook_preserved,'question_count':1,'fact_policy':'preserve supplied evidence only','generic_phrases_detected':generic_found,'news_headline_not_injected':True,'authored_narrative_preserved':True,'edited_at':datetime.now(timezone.utc).isoformat()}})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'status':'PRESERVED','version':'human-editor-v16','hook_preserved':hook_preserved,'question_count':1,'warnings':warnings,'characters':len(edited),'draft_path':str(path)},indent=2,ensure_ascii=False),encoding='utf-8')
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'PRESERVED','version':'human-editor-v16','hook_preserved':hook_preserved,'question_count':1,'warnings':warnings,'characters':len(edited)}))
if __name__=='__main__':main()
