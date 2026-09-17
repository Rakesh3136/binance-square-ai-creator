"""Binance Square publisher with explicit verified/submitted-unknown states."""
from __future__ import annotations
import json, os, re, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data/live'; ANALYTICS=ROOT/'analytics'
PAYLOAD_PATH=LIVE/'publication_payload.json'; LOG_PATH=ANALYTICS/'publication_log.jsonl'; RESULT_PATH=LIVE/'publication_result.json'; CONTEXT_PATH=LIVE/'publication_context.json'; FROZEN_PATH=LIVE/'authoritative_opportunity.json'; VISUAL=LIVE/'visual.png'
ENDPOINT='https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add'; NO_IMAGE_LANES={'education','commentary','community','text_only'}; DUPLICATE_HOURS=float(os.getenv('PUBLISH_DUPLICATE_HOURS','6'))
def now(): return datetime.now(timezone.utc).isoformat()
def load(path):
    try:
        v=json.loads(path.read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:return {}
def canonical_post_id(v):
    raw=str(v or '').strip().rstrip('/')
    if '/square/post/' in raw: raw=raw.split('/square/post/',1)[1].split('?',1)[0].split('#',1)[0].strip()
    return raw if re.fullmatch(r'[A-Za-z0-9_-]{1,128}',raw) else ''
def clean_symbol(v):
    s=re.sub(r'USDT$','',str(v or '').upper().replace('$','').strip()); return s if re.fullmatch(r'[A-Z0-9]{1,15}',s) else ''
def fail(message,code):
    result={'status':code,'message':message,'checked_at':now(),'endpoint':ENDPOINT,'post_id':None,'link':None,'publication_proof':'none'}; LIVE.mkdir(parents=True,exist_ok=True); RESULT_PATH.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False)); return 2
def text_payload():
    d=load(PAYLOAD_PATH); t=str(d.get('text') or d.get('bodyTextOnly') or d.get('content') or '').strip()
    if not t: raise RuntimeError('publication text is empty')
    if len(t)>10000: raise RuntimeError(f'publication text is too long ({len(t)})')
    return t
def recent_rows():
    if not LOG_PATH.exists(): return []
    accepted={'PUBLISHED_AUTONOMOUSLY','PUBLISHED_VERIFIED_BY_API_RESPONSE','VERIFIED_PUBLISHED','PUBLISHED_SUBMITTED_504'}; rows=[]
    for line in LOG_PATH.read_text(encoding='utf-8').splitlines()[-300:]:
        try:r=json.loads(line)
        except Exception:continue
        if isinstance(r,dict) and str(r.get('status') or '') in accepted: rows.append(r)
    return rows
def duplicate_reason(text,symbol,category):
    target=clean_symbol(symbol); now_dt=datetime.now(timezone.utc)
    for row in reversed(recent_rows()):
        rs=clean_symbol(row.get('symbol') or row.get('selected_lane_symbol'))
        try: age=now_dt-datetime.fromisoformat(str(row.get('published_at') or row.get('timestamp') or '').replace('Z','+00:00'))
        except Exception:continue
        if age>timedelta(hours=DUPLICATE_HOURS):continue
        old=str(row.get('text') or row.get('post') or row.get('content') or '').strip(); cat=str(row.get('category') or '').lower()
        if old and old==text.strip():return f'exact_text_duplicate_within_{DUPLICATE_HOURS:g}h'
        if target and rs==target and cat==str(category or '').lower() and not any(k in text.lower() for k in ('result','outcome','invalidated','follow-up','follow up')):return f'same_asset_and_category_within_{DUPLICATE_HOURS:g}h'
    return ''
def append(row):
    ANALYTICS.mkdir(parents=True,exist_ok=True)
    with LOG_PATH.open('a',encoding='utf-8') as h:h.write(json.dumps(row,ensure_ascii=False)+'\n')
def main():
    key=(os.getenv('BINANCE_SQUARE_OPENAPI_KEY') or os.getenv('BINANCE_SQUARE_API_KEY') or '').strip()
    if not key:return fail('BINANCE_SQUARE_OPENAPI_KEY/BINANCE_SQUARE_API_KEY is not configured','PUBLISHER_NOT_CONFIGURED')
    try:
        text=text_payload(); context=load(CONTEXT_PATH); frozen=load(FROZEN_PATH); symbol=clean_symbol(context.get('symbol') or frozen.get('symbol')); category=str(context.get('category') or frozen.get('category') or '').lower()
        if not symbol:raise RuntimeError('publication symbol is missing')
        dup=duplicate_reason(text,symbol,category)
        if dup: append({'timestamp':now(),'status':'PUBLISH_BLOCKED_DUPLICATE','post_id':None,'link':None,'symbol':symbol,'category':category,'text':text,'reason':dup}); return fail(f'Duplicate publication blocked: {dup}','PUBLISH_BLOCKED_DUPLICATE')
        visual_requested=bool(context.get('visual_requested') or context.get('visual_required') or context.get('visual_verified') or context.get('tradingview_verified') or (context.get('visual_decision') or {}).get('required')); require_image=visual_requested or category not in NO_IMAGE_LANES; use_image=VISUAL.exists() and VISUAL.stat().st_size>10000 and require_image
        if require_image and not use_image:raise RuntimeError(f'Required TradingView visual is missing or too small for {symbol}: {VISUAL}')
        if use_image:
            p=subprocess.run(['node',str(ROOT/'src/square_image_publisher.mjs'),str(VISUAL),text],env={**os.environ,'BINANCE_SQUARE_OPENAPI_KEY':key},cwd=ROOT,text=True,capture_output=True,check=False)
            if p.stdout.strip():print(p.stdout)
            if p.returncode!=0:raise RuntimeError(p.stderr.strip() or 'image publisher failed')
            lines=[x.strip() for x in p.stdout.splitlines() if x.strip()]
            if not lines:raise RuntimeError('image publisher returned no result')
            api_result=json.loads(lines[-1])
        else:
            import urllib.request
            body=json.dumps({'bodyTextOnly':text},ensure_ascii=False).encode('utf-8'); req=urllib.request.Request(ENDPOINT,data=body,method='POST',headers={'X-Square-OpenAPI-Key':key,'Content-Type':'application/json','clienttype':'binanceSkill','User-Agent':'binance-square-ai-creator/1.5'})
            try:
                with urllib.request.urlopen(req,timeout=30) as response: api=json.loads(response.read().decode('utf-8',errors='replace'))
            except urllib.error.HTTPError as e:
                if e.code==504: api={'code':'504','data':{},'message':'submitted without post id'}
                else: raise
            code=str(api.get('code','')); data=api.get('data') if isinstance(api.get('data'),dict) else {}; pid=canonical_post_id(data.get('id') or data.get('contentId'))
            api_result={'status':'PUBLISHED_VERIFIED_BY_API_RESPONSE' if code=='000000' and pid else ('PUBLISHED_SUBMITTED_504' if code=='504' else 'PUBLISH_REJECTED'),'post_id':pid or None,'link':data.get('shareLink') or '','api_code':code,'error':api.get('message')}
        status=str(api_result.get('status') or '')
        if status=='PUBLISHED_VERIFIED_BY_API_RESPONSE':
            post_id=canonical_post_id(api_result.get('post_id') or api_result.get('id'))
            if not post_id:raise RuntimeError('Binance response claimed success without a canonical post id')
            link=str(api_result.get('link') or api_result.get('shareLink') or '').strip() or f'https://www.binance.com/square/post/{post_id}'
            proof='binance_openapi_response_post_id'; exit_code=0
        elif status=='PUBLISHED_SUBMITTED_504':
            post_id=''; link=''; proof='binance_content_add_http_504_submission_unknown'; exit_code=0
        else: raise RuntimeError(api_result.get('error') or 'Binance rejected publication')
    except Exception as exc:
        append({'timestamp':now(),'status':'PUBLISH_FAILED','post_id':None,'link':None,'error':str(exc),'publication_proof':'none'}); return fail(str(exc),'PUBLISH_FAILED')
    row={'timestamp':now(),'published_at':now(),'status':status,'post_id':post_id or None,'canonical_post_id':post_id or None,'link':link or None,'text':text,'text_length':len(text),'symbol':symbol,'category':category,'experiment_id':str(context.get('experiment_id') or frozen.get('experiment_id') or ''),'reference_price':frozen.get('reference_price') or context.get('reference_price'),'trigger':frozen.get('trigger') or frozen.get('entry'),'invalidation':frozen.get('invalidation'),'targets':frozen.get('targets') or frozen.get('take_profit') or [],'visual_attached':use_image,'visual_path':str(VISUAL) if use_image else None,'visual_url':api_result.get('image_url'),'editorial_style':str(context.get('editorial_style') or ''),'publication_id_verified':bool(post_id),'publication_proof':proof}
    append(row); result={'status':status,'checked_at':now(),'post_id':post_id or None,'canonical_post_id':post_id or None,'link':link or None,'symbol':symbol,'category':category,'visual_attached':use_image,'visual_url':api_result.get('image_url'),'id_verification':'verified' if post_id else 'unavailable','publication_proof':proof}; LIVE.mkdir(parents=True,exist_ok=True); RESULT_PATH.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps(result,indent=2,ensure_ascii=False)); return exit_code
if __name__=='__main__':raise SystemExit(main())
