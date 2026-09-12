"""Single Binance Square publication adapter with a last-mile duplicate lock."""
from __future__ import annotations
import json, os, re, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=ROOT/'data/live'; ANALYTICS=ROOT/'analytics'
PAYLOAD_PATH=LIVE/'publication_payload.json'; LOG_PATH=ANALYTICS/'publication_log.jsonl'; RESULT_PATH=LIVE/'publication_result.json'; CONTEXT_PATH=LIVE/'publication_context.json'; FROZEN_PATH=LIVE/'authoritative_opportunity.json'; VISUAL=LIVE/'visual.png'
ENDPOINT='https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add'
IMAGE_LANES={'crypto_meme','market_meme','trader_humor','technical_setup','capital_flow_long','capital_flow_short','result_followup','research_radar','news','breaking_news','news_and_macro'}
DUPLICATE_HOURS=float(os.getenv('PUBLISH_DUPLICATE_HOURS','6'))

def now():return datetime.now(timezone.utc).isoformat()
def load(p):
    try:
        x=json.loads(Path(p).read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}
def clean_symbol(v):
    x=re.sub(r'USDT$','',str(v or '').upper().replace('$','').strip());return x if re.fullmatch(r'[A-Z0-9]{1,15}',x) else ''
def fail(msg,code):
    result={'status':code,'message':msg,'checked_at':now(),'endpoint':ENDPOINT,'post_id':None,'link':None};LIVE.mkdir(parents=True,exist_ok=True);RESULT_PATH.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False));return 2
def text_payload():
    data=load(PAYLOAD_PATH);text=str(data.get('text') or data.get('bodyTextOnly') or data.get('content') or '').strip()
    if not text:raise RuntimeError('publication text is empty')
    if len(text)>10000:raise RuntimeError(f'publication text is too long ({len(text)})')
    return text
def recent_rows():
    if not LOG_PATH.exists():return []
    accepted={'PUBLISHED_AUTONOMOUSLY','PUBLISHED_VERIFIED_BY_API_RESPONSE','PUBLISHED_SUBMITTED_504','VERIFIED_PUBLISHED'};rows=[]
    for line in LOG_PATH.read_text(encoding='utf-8').splitlines()[-300:]:
        try:r=json.loads(line)
        except Exception:continue
        if isinstance(r,dict) and str(r.get('status') or '') in accepted:rows.append(r)
    return rows
def duplicate_reason(text,symbol,category):
    target=clean_symbol(symbol);now_dt=datetime.now(timezone.utc)
    for row in reversed(recent_rows()):
        rs=clean_symbol(row.get('symbol') or row.get('selected_lane_symbol'));t=row.get('published_at') or row.get('timestamp') or ''
        try:age=now_dt-datetime.fromisoformat(str(t).replace('Z','+00:00'))
        except Exception:continue
        if age>timedelta(hours=DUPLICATE_HOURS):continue
        old_text=str(row.get('text') or row.get('post') or row.get('content') or '').strip()
        old_cat=str(row.get('category') or '').lower()
        if old_text and old_text==text.strip():return f'exact_text_duplicate_within_{DUPLICATE_HOURS:g}h'
        if target and rs==target and old_cat==str(category or '').lower() and not any(k in text.lower() for k in ('result','outcome','invalidated','follow-up','follow up')):
            return f'same_asset_and_category_within_{DUPLICATE_HOURS:g}h'
    return ''
def append(row):
    ANALYTICS.mkdir(parents=True,exist_ok=True)
    with LOG_PATH.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
def main():
    key=os.getenv('BINANCE_SQUARE_OPENAPI_KEY','').strip()
    if not key:return fail('BINANCE_SQUARE_OPENAPI_KEY is not configured','PUBLISHER_NOT_CONFIGURED')
    try:
        text=text_payload();ctx=load(CONTEXT_PATH);frozen=load(FROZEN_PATH);symbol=clean_symbol(ctx.get('symbol') or frozen.get('symbol'));cat=str(ctx.get('category') or frozen.get('category') or '').lower()
        if not symbol:raise RuntimeError('publication symbol is missing')
        dup=duplicate_reason(text,symbol,cat)
        if dup:
            append({'timestamp':now(),'status':'PUBLISH_BLOCKED_DUPLICATE','post_id':None,'link':None,'symbol':symbol,'category':cat,'text':text,'reason':dup})
            return fail(f'Duplicate publication blocked: {dup}','PUBLISH_BLOCKED_DUPLICATE')
        use_image=VISUAL.exists() and VISUAL.stat().st_size>10000 and (cat in IMAGE_LANES or bool(ctx.get('visual_requested')))
        if use_image:
            proc=subprocess.run(['node',str(ROOT/'src/square_image_publisher.mjs'),str(VISUAL),text],env={**os.environ,'BINANCE_SQUARE_OPENAPI_KEY':key},cwd=ROOT,text=True,capture_output=True,check=False)
            if proc.stdout.strip():print(proc.stdout)
            if proc.returncode!=0:raise RuntimeError(proc.stderr.strip() or 'image publisher failed')
            lines=[x.strip() for x in proc.stdout.splitlines() if x.strip()]
            if not lines:raise RuntimeError('image publisher returned no result')
            result=json.loads(lines[-1])
        else:
            import urllib.request
            body=json.dumps({'bodyTextOnly':text},ensure_ascii=False).encode('utf-8');req=urllib.request.Request(ENDPOINT,data=body,method='POST',headers={'X-Square-OpenAPI-Key':key,'Content-Type':'application/json','clienttype':'binanceSkill','User-Agent':'binance-square-ai-creator/1.3'})
            with urllib.request.urlopen(req,timeout=30) as response:api=json.loads(response.read().decode('utf-8',errors='replace'))
            code=str(api.get('code',''));data=api.get('data') if isinstance(api.get('data'),dict) else {};pid=data.get('id') or data.get('contentId');result={'status':'PUBLISHED_VERIFIED_BY_API_RESPONSE' if code=='000000' and pid else 'PUBLISH_REJECTED','post_id':str(pid or '') or None,'link':f'https://www.binance.com/square/post/{pid}' if pid else None,'api_code':code,'error':api.get('message')}
        status=str(result.get('status') or '')
        if status=='PUBLISHED_UNKNOWN':result['status']='PUBLISHED_SUBMITTED_504'
        elif status!='PUBLISHED_VERIFIED_BY_API_RESPONSE' or not result.get('post_id'):raise RuntimeError(result.get('error') or 'publication response did not contain a verified post id')
    except Exception as e:
        append({'timestamp':now(),'status':'PUBLISH_FAILED','post_id':None,'link':None,'error':str(e)});return fail(str(e),'PUBLISH_FAILED')
    post_id=str(result.get('post_id') or '').strip() or None;link=str(result.get('link') or (f'https://www.binance.com/square/post/{post_id}' if post_id else '')) or None;final_status=str(result.get('status') or 'PUBLISHED_VERIFIED_BY_API_RESPONSE')
    row={'timestamp':now(),'published_at':now(),'status':final_status,'post_id':post_id,'link':link,'text':text,'text_length':len(text),'symbol':symbol,'category':cat,'experiment_id':str(ctx.get('experiment_id') or frozen.get('experiment_id') or ''),'reference_price':frozen.get('reference_price') or ctx.get('reference_price'),'trigger':frozen.get('trigger') or frozen.get('entry'),'invalidation':frozen.get('invalidation'),'targets':frozen.get('targets') or frozen.get('take_profit') or [],'visual_attached':use_image,'visual_path':str(VISUAL) if use_image else None,'editorial_style':str(ctx.get('editorial_style') or ''),'publication_id_verified':bool(post_id)};append(row)
    result={'status':final_status,'checked_at':now(),'post_id':post_id,'link':link,'symbol':symbol,'category':cat,'visual_attached':use_image,'id_verification':'verified' if post_id else 'unknown_after_504'};LIVE.mkdir(parents=True,exist_ok=True);RESULT_PATH.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False));return 0
if __name__=='__main__':sys.exit(main())