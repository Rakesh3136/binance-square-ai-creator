"""Creator 6.0 surgical human editor.

Preservation-only post processor: deterministic cleanup, evidence-safe cashtag
sanitization, and a single story-specific discussion question when the author
forgot one. It is never a second AI authoring pass.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONTEXT=ROOT/'data/live/publication_context.json'; OUT=ROOT/'data/live/editorial_polish.json'
ALIASES={'bitcoin':'BTC','btc':'BTC','ether':'ETH','ethereum':'ETH','eth':'ETH','binance coin':'BNB','bnb':'BNB','solana':'SOL','sol':'SOL','xrp':'XRP','ripple':'XRP','dogecoin':'DOGE','doge':'DOGE','cardano':'ADA','ada':'ADA','avalanche':'AVAX','avax':'AVAX','chainlink':'LINK','link':'LINK','zcash':'ZEC','zec':'ZEC','tron':'TRX','trx':'TRX','polkadot':'DOT','dot':'DOT','shiba inu':'SHIB','shib':'SHIB','sui':'SUI','toncoin':'TON','ton':'TON','pepe':'PEPE','floki':'FLOKI'}
GENERIC_PHRASES=('what do you think','thoughts?','comment below','like and follow','bullish or bearish?','this is interesting','fresh check','quick market check','here is what matters','here’s what matters')
TEMPLATE_SENTENCES=('bear case:','bull case:','price reclaims the range','sellers keep control below support','buyers keep control above')

def load(path,default=None):
    if default is None: default={}
    try:
        x=json.loads(path.read_text(encoding='utf-8')); return x if isinstance(x,type(default)) else default
    except Exception:return default

def norm(v): return re.sub(r'[ \t]+',' ',str(v or '')).strip()
def normalize_symbol(v):
    s=norm(v).upper().replace('$','').replace('BINANCE:','').strip(); s=re.sub(r'USDT$','',s)
    return s if re.fullmatch(r'[A-Z0-9]{1,15}',s) else ''
def title_assets(title):
    found=[]; low=norm(title).lower()
    for name,sym in sorted(ALIASES.items(),key=lambda x:-len(x[0])):
        if re.search(r'(?<![a-z0-9])'+re.escape(name)+r'(?![a-z0-9])',low) and sym not in found: found.append(sym)
    return found

def write_block(report,path,reason,count):
    result={'status':'BLOCKED','version':'human-editor-v20','hook_preserved':False,'question_count':count,'reason':reason,'draft_path':str(path),'fail_closed':True,'edited_at':datetime.now(timezone.utc).isoformat()}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    report.setdefault('draft',{})['human_editor']=result; path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,ensure_ascii=False))

def strip_unsupported_cashtags(text,allowed):
    def repl(m):
        sym=m.group(1).upper(); return '$'+sym if sym in allowed else ''
    return re.sub(r' {2,}',' ',re.sub(r'\n[ \t]+\n','\n\n',re.sub(r'\$([A-Z][A-Z0-9]{0,14})\b',repl,text,flags=re.I))).strip()

def surgical_cleanup(text):
    text=re.sub(r'\b(the market market|price price|volume volume|crypto crypto)\b',lambda m:m.group(1).split()[0],text,flags=re.I)
    text=re.sub(r'\b(spot volume)\s+is\s+(\$[\d,.]+[KMB]?)\s+spot volume\b',r'\1 is \2',text,flags=re.I)
    text=re.sub(r'\b(\$[\d,.]+[KMB]?)\s+spot volume\s+with\b',r'\1 in spot volume, with',text,flags=re.I)
    return re.sub(r'^(post|draft|hook|answer|final)\s*:\s*','',re.sub(r'\n{3,}','\n\n',text,flags=re.M),flags=re.I).strip()

def repetition_artifact(text):
    low=re.sub(r'\s+',' ',text.lower()).strip()
    hits=sum(1 for p in GENERIC_PHRASES if p in low); template_hits=sum(1 for p in TEMPLATE_SENTENCES if p in low)
    fixed_drop=bool(re.search(r'\$[a-z0-9]+\s+just dropped\s+[\d.]+%\s*[—-]\s*now the reaction matters',low))
    fixed_cases=bool(re.search(r'bear case:.*bull case:',low))
    return hits,template_hits,fixed_drop or fixed_cases

def deterministic_question(symbol,category):
    lane=str(category or '').lower()
    if lane in {'next_gainer_candidate','next_loser_candidate','capital_flow_long','capital_flow_short','technical_setup'}:
        return f'What confirmation on ${symbol} would make you treat this setup as real rather than an early headline move?'
    if lane in {'top_gainers','top_losers','high_volatility','volume_leaders'}:
        return f'What would you watch next on ${symbol} to decide whether this move has follow-through?'
    return f'What specific reaction on ${symbol} would make you change your read?'

def main():
    raw_path=os.getenv('DRAFT_PATH','').strip(); path=Path(raw_path)
    if not path.exists():
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps({'status':'BLOCKED','version':'human-editor-v20','reason':'DRAFT_PATH is missing','fail_closed':True},indent=2),encoding='utf-8'); print(json.dumps({'status':'BLOCKED','reason':'DRAFT_PATH is missing'})); return 0
    report=load(path,{}); draft=report.setdefault('draft',{}); original=norm(draft.get('post') or draft.get('text') or '')
    if not original:
        write_block(report,path,'draft_has_no_post_text',0); return 0
    context=load(CONTEXT,{}); selected=report.get('selected_editorial_lane') or report.get('selected_opportunity') or {}
    primary=normalize_symbol(context.get('symbol') or selected.get('symbol') or draft.get('symbol'))
    if not primary:
        write_block(report,path,'primary_symbol_missing',0); return 0
    news_title=norm(context.get('news_title') or selected.get('news_title') or draft.get('news_title')); allowed={primary}|set(title_assets(news_title)) if news_title else {primary}
    edited=surgical_cleanup(strip_unsupported_cashtags(original,allowed)); lines=[norm(x) for x in edited.splitlines() if norm(x)]
    questions=re.findall(r'[^\n.!?]*\?',edited)
    category=str(context.get('category') or selected.get('category') or draft.get('content_category') or '').lower()
    if len(questions)==0:
        edited=edited+'\n\n'+deterministic_question(primary,category); questions=[deterministic_question(primary,category)]
    elif len(questions)>1:
        write_block(report,path,f'unsafe_question_count:{len(questions)}',len(questions)); return 0
    first_before=norm(lines[0]) if lines else ''; first_after=next((norm(x) for x in edited.splitlines() if norm(x)), '')
    hits,template_hits,hard_template=repetition_artifact(edited)
    if hard_template:
        write_block(report,path,'repetitive_feed_template',1); return 0
    generic_found=[p for p in GENERIC_PHRASES if p in edited.lower()]
    draft.update({'post':edited,'text':edited,'editorial_style':draft.get('editorial_style') or 'authored','human_editor':{'status':'PRESERVED','version':'human-editor-v20','hook_preserved':first_before==first_after,'question_count':1,'question_source':'deterministic_contract_repair' if not re.search(r'\?',original) else 'author','generic_phrases_detected':generic_found,'template_hits':template_hits,'fact_policy':'preserve supplied evidence only','authored_narrative_preserved':True,'edited_at':datetime.now(timezone.utc).isoformat()}})
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps({'status':'PRESERVED','version':'human-editor-v19','hook_preserved':first_before==first_after,'question_count':1,'question_source':draft['human_editor']['question_source'],'warnings':[] if not generic_found else ['generic_phrase_present'],'template_hits':template_hits,'characters':len(edited),'draft_path':str(path)},indent=2,ensure_ascii=False),encoding='utf-8'); path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'PRESERVED','version':'human-editor-v19','hook_preserved':first_before==first_after,'question_count':1,'question_source':draft['human_editor']['question_source'],'template_hits':template_hits,'characters':len(edited)}))
if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        # The editor is preservation-only. A local editor defect must never
        # crash the autonomous creator cycle or bypass downstream safety gates.
        OUT.parent.mkdir(parents=True,exist_ok=True)
        result={'status':'BLOCKED','version':'human-editor-v20','reason':f'editor_exception:{type(exc).__name__}:{exc}','fail_closed':True,'edited_at':datetime.now(timezone.utc).isoformat()}
        OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))

