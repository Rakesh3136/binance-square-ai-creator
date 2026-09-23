"""TypeSafe AI Jev System-One decision layer."""
from __future__ import annotations
import json, os, urllib.error, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/live/jev_decision.json'
URL=os.getenv('JEV_API_URL','https://api.typesafe.ai/v1/systemone').strip()
MODEL=os.getenv('JEV_MODEL','jev-latest').strip()

def _key(): return (os.getenv('TYPESAFE_API_KEY') or os.getenv('JEV_API_KEY') or '').strip()
def _post(payload,key):
    req=urllib.request.Request(URL,data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','Accept':'application/json','User-Agent':'binance-square-ai-creator/jev-gate'},method='POST')
    with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read().decode())
def _answer(resp,name):
    a=(resp.get('data') or {}).get('answers') if isinstance(resp,dict) else None
    if not isinstance(a,dict): a=resp.get('answers') if isinstance(resp,dict) else {}
    return a.get(name) if isinstance(a,dict) and isinstance(a.get(name),dict) else {}

def evaluate(*,symbol,category,post,direction,entry,tp1,tp2,sl,opportunity_score,quality_score,evidence,deterministic_ok):
    key=_key(); result={'enabled':bool(key),'provider':'TypeSafe AI','endpoint':URL,'model':MODEL,'status':'disabled_no_api_key' if not key else 'error','publish':bool(deterministic_ok),'confidence':0.0,'action':'local_gates_only','jev_authoritative':False}
    if not key:
        OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2)); return result
    payload={'model':MODEL,'state':{'symbol':symbol,'category':category,'direction':direction,'entry_trigger':entry,'tp1':tp1,'tp2':tp2,'sl':sl,'opportunity_score':opportunity_score,'quality_score':quality_score,'evidence':evidence[-12:],'deterministic_gates_passed':deterministic_ok,'post_excerpt':post[:2400]},'questions':{'action':{'type':'choice','options':['publish','review','block'],'instructions':'Choose the appropriate publication action after reviewing the supplied evidence.'},'evidence_sufficient':{'type':'noul','instructions':'Is the supplied evidence sufficient to support the stated conditional trading setup?'},'setup_quality':{'type':'score','instructions':'Score the overall quality of the supplied setup for publication.','criteria':['weak','fair','good','strong','exceptional']}}}
    try:
        resp=_post(payload,key); action=_answer(resp,'action'); ev=_answer(resp,'evidence_sufficient'); q=_answer(resp,'setup_quality'); choice=str(action.get('choice') or action.get('value') or '').lower(); conf=float(action.get('confidence') or ev.get('confidence') or 0); prob=ev.get('noul'); prob=float(prob) if prob is not None else None; publish=bool(deterministic_ok and choice=='publish' and conf>=.70 and (prob is None or prob>=.70)); result.update({'status':'ok','publish':publish,'action':choice or 'unknown','confidence':conf,'evidence_probability':prob,'setup_quality':q.get('score') or q.get('value'),'jev_authoritative':True,'raw':resp})
    except urllib.error.HTTPError as exc:
        try: detail=exc.read().decode(errors='replace')[:1000]
        except Exception: detail=''
        result.update({'status':'unavailable_auth' if exc.code in {401,403} else 'unavailable_http','error':f'HTTPError: {exc.code} {exc.reason}','error_detail':detail,'publish':bool(deterministic_ok),'action':'local_gates_only','confidence':0.0})
    except (urllib.error.URLError,TimeoutError) as exc: result.update({'status':'unavailable_transport','error':f'{type(exc).__name__}: {exc}','publish':bool(deterministic_ok),'action':'local_gates_only','confidence':0.0})
    except Exception as exc: result.update({'status':'error','error':f'{type(exc).__name__}: {exc}','publish':False})
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)); return result

if __name__=='__main__': print(json.dumps({'status':'module_ready','api_configured':bool(_key()),'endpoint':URL,'model':MODEL},indent=2))
