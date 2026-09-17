"""Durable Binance Square publication truth verifier."""
from __future__ import annotations
import json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ANALYTICS=ROOT/'analytics'; LIVE=ROOT/'data'/'live'; INTEL=ROOT/'data'/'intelligence'; RESULT=LIVE/'publication_result.json'
def read_json(path,default=None):
    try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:return default
def canonical_post_id(v):
    raw=str(v or '').strip().rstrip('/')
    if '/square/post/' in raw:raw=raw.split('/square/post/',1)[1].split('?',1)[0].split('#',1)[0]
    return raw if re.fullmatch(r'[A-Za-z0-9_-]{1,128}',raw) else ''
def read_publications():
    path=ANALYTICS/'publication_log.jsonl'; rows=[]
    if not path.exists():return rows
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            row=json.loads(line)
            if isinstance(row,dict):rows.append(row)
        except json.JSONDecodeError:pass
    return rows
def main():
    now=datetime.now(timezone.utc).isoformat(); rows=read_publications(); latest=rows[-1] if rows else None; result_file=read_json(RESULT,{}) or {}; result_id=canonical_post_id(result_file.get('canonical_post_id') or result_file.get('post_id')); log_id=canonical_post_id(latest.get('canonical_post_id') or latest.get('post_id')) if latest else ''; status=str(latest.get('status') or '') if latest else ''; verified_status=status in {'PUBLISHED_VERIFIED_BY_API_RESPONSE','VERIFIED_PUBLISHED','PUBLISHED_AUTONOMOUSLY'}; ids_match=bool(result_id and log_id and result_id==log_id); has_verified_id=bool(log_id and verified_status and latest.get('publication_id_verified') is not False)
    if has_verified_id and ids_match:truth_state='VERIFIED_PUBLISHED'; proof='publisher result and durable publication log agree on the canonical Binance Square post_id'
    elif latest and status=='PUBLISHED_SUBMITTED_504':truth_state='SUBMITTED_UNKNOWN'; proof='Binance content/add returned HTTP 504 after submission; the post may exist but no canonical post id was returned, so it is not treated as verified'
    elif latest and status:truth_state='ATTEMPTED_NOT_VERIFIED'; proof='publication attempt exists but canonical Binance post-id proof is missing or inconsistent'
    else:truth_state='NO_ATTEMPT'; proof='no durable publication record is available'
    result={'version':'20.3-creator-9.2-504-aware-live-proof','checked_at':now,'truth_state':truth_state,'proof':proof,'latest_publication':latest,'publisher_result':result_file,'canonical_post_id':log_id or result_id or None,'post_id_match':ids_match,'publication_count_observed':len(rows),'rules':{'post_id_required_for_verified_state':True,'publisher_and_log_ids_must_match':True,'submission_unknown_is_not_verified':True,'revenue_inferred':False,'gate_bypass':False,'credential_changes':False}}
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True); (LIVE/'creator_20_0_publication_truth.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); report={'version':result['version'],'generated_at':now,'truth_state':truth_state,'publication_count_observed':len(rows),'latest_post_id':log_id or None,'latest_link':latest.get('link') if latest else None,'proof':proof,'post_id_match':ids_match}; (INTEL/'creator_20_0_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); memory_path=ANALYTICS/'creator_20_0_memory.json'; memory=read_json(memory_path,{'checks':[]}) or {'checks':[]}; checks=memory.get('checks') if isinstance(memory.get('checks'),list) else []; checks.append({'checked_at':now,'truth_state':truth_state,'post_id':log_id or result_id or None,'post_id_match':ids_match}); memory['checks']=checks[-200:]; memory['latest_truth_state']=truth_state; memory['latest_canonical_post_id']=log_id or result_id or None; memory_path.write_text(json.dumps(memory,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False)); return 0
if __name__=='__main__':raise SystemExit(main())
