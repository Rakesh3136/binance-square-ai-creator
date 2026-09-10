"""Single Binance Square publication adapter with durable experiment metadata."""
from __future__ import annotations
import json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1];LIVE=ROOT/'data/live';ANALYTICS=ROOT/'analytics';PAYLOAD_PATH=LIVE/'publication_payload.json';LOG_PATH=ANALYTICS/'publication_log.jsonl';RESULT_PATH=LIVE/'publication_result.json';CONTEXT_PATH=LIVE/'publication_context.json';FROZEN_PATH=LIVE/'authoritative_opportunity.json';ENDPOINT='https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add'

def now():return datetime.now(timezone.utc).isoformat()
def load(p):
    try:
        x=json.loads(Path(p).read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}
def append(row):
    ANALYTICS.mkdir(parents=True,exist_ok=True)
    with LOG_PATH.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
def fail(message,code):
    result={'status':code,'message':message,'checked_at':now(),'endpoint':ENDPOINT,'post_id':None,'link':None};LIVE.mkdir(parents=True,exist_ok=True);RESULT_PATH.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False));return 2

def main():
    key=os.getenv('BINANCE_SQUARE_OPENAPI_KEY','').strip()
    if not key:return fail('BINANCE_SQUARE_OPENAPI_KEY is not configured','PUBLISHER_NOT_CONFIGURED')
    try:
        payload=load(PAYLOAD_PATH);text=payload.get('text') or payload.get('bodyTextOnly') or payload.get('content');text=str(text or '').strip()
        if not text:raise RuntimeError('publication text is empty')
        if len(text)>10000:raise RuntimeError(f'publication text is too long ({len(text)})')
        body=json.dumps({'bodyTextOnly':text},ensure_ascii=False).encode('utf-8');req=Request(ENDPOINT,data=body,method='POST',headers={'X-Square-OpenAPI-Key':key,'Content-Type':'application/json','clienttype':'binanceSkill','User-Agent':'binance-square-ai-creator/1.0'})
        with urlopen(req,timeout=30) as response:raw=response.read().decode('utf-8',errors='replace')
        response=json.loads(raw)
    except HTTPError as e:
        try:detail=e.read().decode('utf-8',errors='replace')[:1000]
        except Exception:detail=str(e)
        append({'timestamp':now(),'status':'PUBLISH_FAILED','post_id':None,'link':None,'error':f'HTTP {e.code}: {detail}'});return fail(f'HTTP {e.code}: {detail}','PUBLISH_FAILED')
    except (URLError,TimeoutError) as e:
        append({'timestamp':now(),'status':'PUBLISH_UNKNOWN','post_id':None,'link':None,'error':str(e)});return fail(str(e),'PUBLISH_UNKNOWN')
    except Exception as e:
        append({'timestamp':now(),'status':'PUBLISH_FAILED','post_id':None,'link':None,'error':str(e)});return fail(str(e),'PUBLISH_FAILED')
    code=str(response.get('code',''));data=response.get('data') if isinstance(response.get('data'),dict) else {};post_id=str(data.get('id') or data.get('contentId') or '').strip()
    if code!='000000' or not post_id:
        message=str(response.get('message') or f'Binance response code={code!r} without post id');append({'timestamp':now(),'status':'PUBLISH_REJECTED','post_id':None,'link':None,'error':message,'api_code':code});return fail(message,'PUBLISH_REJECTED')
    ctx=load(CONTEXT_PATH);frozen=load(FROZEN_PATH);link=f'https://www.binance.com/square/post/{post_id}'
    row={'timestamp':now(),'published_at':now(),'status':'PUBLISHED_VERIFIED_BY_API_RESPONSE','post_id':post_id,'link':link,'api_code':code,'text_length':len(text),'text':text,'symbol':str(ctx.get('symbol') or frozen.get('symbol') or '').upper().replace('$','').replace('USDT',''),'category':str(ctx.get('category') or frozen.get('category') or ''),'experiment_id':str(ctx.get('experiment_id') or frozen.get('experiment_id') or ''),'reference_price':frozen.get('reference_price') or ctx.get('reference_price'),'trigger':frozen.get('trigger') or frozen.get('entry'),'invalidation':frozen.get('invalidation'),'targets':frozen.get('targets') or frozen.get('take_profit') or [],'visual_type':str(ctx.get('visual_type') or ''),'hook_type':str(ctx.get('hook_type') or ''),'editorial_style':str(ctx.get('editorial_style') or '')}
    append(row);result={'status':row['status'],'checked_at':now(),'post_id':post_id,'link':link,'api_code':code,'symbol':row['symbol'],'category':row['category'],'experiment_id':row['experiment_id']};RESULT_PATH.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False));return 0
if __name__=='__main__':sys.exit(main())
