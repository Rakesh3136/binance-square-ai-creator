"""Verified prediction ledger and outcome engine."""
from __future__ import annotations
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];LEDGER=ROOT/'analytics/call_ledger.jsonl';SUMMARY=ROOT/'data/intelligence/call_tracker.json';TECH=ROOT/'data/live/technical_enrichment.json';CONTEXT=ROOT/'data/live/publication_context.json';FROZEN=ROOT/'data/live/authoritative_opportunity.json';RESULT=ROOT/'data/live/publication_result.json'
def load(path,default):
    try:
        x=json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else default;return x if isinstance(x,type(default)) else default
    except Exception:return default
def num(v):
    try:return float(v)
    except (TypeError,ValueError):return None
def main():
    context=load(CONTEXT,{});frozen=load(FROZEN,{});tech=load(TECH,{});pub=load(RESULT,{})
    selected=frozen or context;symbol=str(selected.get('symbol_usdt') or selected.get('symbol') or '').upper().replace('$','').replace('USDT','');category=str(selected.get('category') or context.get('category') or '').lower()
    trading_lanes={'technical_setup','high_volatility','top_gainers','top_losers','creator_signal_outcome','capital_flow','capital_flow_setup','conditional_trade'}
    if category not in trading_lanes or not symbol:
        record={'recorded_at':datetime.now(timezone.utc).isoformat(),'status':'NO_EXPLICIT_CALL','reason':'non-trading editorial lane','category':category,'symbol':symbol};SUMMARY.parent.mkdir(parents=True,exist_ok=True);SUMMARY.write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(record));return
    price=num(tech.get('reference_price') or tech.get('current_price') or selected.get('reference_price') or context.get('reference_price'));targets=tech.get('targets') if isinstance(tech.get('targets'),list) else [];invalidation=num(tech.get('invalidation') or tech.get('stop_loss') or tech.get('sl') or selected.get('invalidation'));direction=str(tech.get('direction') or selected.get('direction') or selected.get('side') or '').upper() or 'LONG_BIAS';explicit=bool(price and (targets or invalidation));existing=[]
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding='utf-8').splitlines():
            try:
                r=json.loads(line)
                if isinstance(r,dict):existing.append(r)
            except Exception:pass
    post_id=str(pub.get('post_id') or '').strip() or None;now=datetime.now(timezone.utc);linked=None
    for r in existing:
        if r.get('status')!='OPEN' or str(r.get('symbol') or '')!=symbol:continue
        if post_id and str(r.get('post_id') or '')==post_id:linked=r;break
        if r.get('post_id'):continue
        try:age=now-datetime.fromisoformat(str(r.get('recorded_at')).replace('Z','+00:00'))
        except Exception:age=timedelta(days=99)
        if age<=timedelta(hours=2) and (num(r.get('reference_price')) or 0)==(price or -1):linked=r;break
    record={'recorded_at':now.isoformat(),'symbol':symbol,'category':category,'reference_price':price,'targets':[num(x) for x in targets if num(x) is not None],'invalidation':invalidation,'direction':direction,'post_id':post_id,'status':'OPEN' if explicit else 'NO_EXPLICIT_CALL','verification':'unverified_until_fresh_market_data_confirms_target_or_invalidation','source':'verified technical enrichment + frozen publication context'}
    if linked:
        linked.update({'post_id':post_id or linked.get('post_id'),'category':category});
        lines=[]
        for r in existing:lines.append(json.dumps(linked if r is linked else r,ensure_ascii=False))
        LEDGER.parent.mkdir(parents=True,exist_ok=True);LEDGER.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    elif explicit:
        record['call_id']=f"{symbol}-{now.strftime('%Y%m%dT%H%M%SZ')}";LEDGER.parent.mkdir(parents=True,exist_ok=True)
        with LEDGER.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
    open_calls=[r for r in (existing if existing else []) if r.get('status')=='OPEN']
    if explicit and not linked:open_calls.append(record)
    SUMMARY.parent.mkdir(parents=True,exist_ok=True);SUMMARY.write_text(json.dumps({'updated_at':now.isoformat(),'latest':record,'open_calls':open_calls,'rules':['Never claim a target was hit without fresh verified market data.','Never rewrite reference price, target or invalidation after publication.','Failed setups are reported, never hidden.','Memes never create trading calls.']},indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(record,ensure_ascii=False))
if __name__=='__main__':main()
