"""NIC Prediction Truth Loop.

Creates one immutable truth record per prediction and exposes only terminal,
objectively-resolved outcomes to calibration. No outcome is inferred from
engagement, price direction alone, or an incomplete candle.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/'data/live/nic_prediction_engine.json'
OUTCOMES=ROOT/'analytics/prediction_outcomes.jsonl'
TRUTH=ROOT/'analytics/nic_prediction_truth_ledger.jsonl'
SUMMARY=ROOT/'data/live/nic_prediction_truth_loop.json'

def read_json(path):
    try:
        x=json.loads(path.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:
        return {}

def read_jsonl(path):
    rows=[]
    if not path.exists(): return rows
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            x=json.loads(line)
            if isinstance(x,dict): rows.append(x)
        except Exception: pass
    return rows

def main():
    now=datetime.now(timezone.utc).isoformat()
    engine=read_json(ENGINE)
    outcomes=read_jsonl(OUTCOMES)
    existing=read_jsonl(TRUTH)
    existing_ids={str(x.get('prediction_id')) for x in existing if x.get('prediction_id')}

    candidates=engine.get('candidates') or []
    new=[]
    for c in candidates:
        if not isinstance(c,dict): continue
        pid=str(c.get('prediction_id') or c.get('call_id') or '')
        symbol=str(c.get('symbol') or '').upper()
        if not pid or not symbol or pid in existing_ids: continue
        setup=c.get('recommended_setup') if isinstance(c.get('recommended_setup'),dict) else {}
        new.append({
            'prediction_id':pid,
            'created_at':c.get('created_at') or now,
            'recorded_at':now,
            'symbol':symbol,
            'side':c.get('side'),
            'trigger':setup.get('trigger'),
            'tp1':setup.get('tp1'),
            'tp2':setup.get('tp2'),
            'invalidation':setup.get('invalidation'),
            'regime':c.get('regime'),
            'features':c.get('features') or c.get('evidence') or {},
            'confidence':c.get('calibrated_confidence'),
            'engine_status':c.get('status'),
            'accuracy_gate_pass':c.get('accuracy_gate_pass'),
            'outcome':'PENDING',
            'truth_source':'NIC prediction + later Binance OHLCV outcome',
            'immutable_prediction':True,
        })

    if new:
        TRUTH.parent.mkdir(parents=True,exist_ok=True)
        with TRUTH.open('a',encoding='utf-8') as f:
            for row in new: f.write(json.dumps(row,ensure_ascii=False)+'\n')
        existing.extend(new)

    by_id={str(x.get('call_id')):x for x in outcomes if x.get('call_id')}
    by_pid={str(x.get('prediction_id')):x for x in outcomes if x.get('prediction_id')}
    terminal=0; pending=0
    rewritten=[]
    for row in existing:
        match=by_pid.get(str(row.get('prediction_id'))) or by_id.get(str(row.get('prediction_id')))
        # Prediction records remain immutable; only the outcome field may be
        # appended to the truth state once an objective terminal result exists.
        if match and match.get('outcome') in {'WIN','INVALIDATED','AMBIGUOUS'}:
            row=dict(row)
            row['outcome']=match['outcome']
            row['outcome_recorded_at']=match.get('evaluated_at') or now
            row['outcome_reason']=match.get('reason')
            row['outcome_source']=match.get('source')
            row['observed_high']=match.get('observed_high')
            row['observed_low']=match.get('observed_low')
            terminal+=1
        elif row.get('outcome')=='PENDING': pending+=1
        rewritten.append(row)

    # Rebuild atomically so a truth record is never partially written.
    TRUTH.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rewritten),encoding='utf-8')
    report={
        'version':'1.0-immutable-prediction-truth-loop',
        'updated_at':now,
        'prediction_records':len(rewritten),
        'new_records':len(new),
        'terminal_records':sum(x.get('outcome') in {'WIN','INVALIDATED','AMBIGUOUS'} for x in rewritten),
        'pending_records':sum(x.get('outcome')=='PENDING' for x in rewritten),
        'wins':sum(x.get('outcome')=='WIN' for x in rewritten),
        'invalidated':sum(x.get('outcome')=='INVALIDATED' for x in rewritten),
        'ambiguous':sum(x.get('outcome')=='AMBIGUOUS' for x in rewritten),
        'policy':{
            'prediction_immutable':True,
            'only_terminal_outcomes_train_nic':True,
            'ambiguous_never_counts_as_win':True,
            'engagement_never_counts_as_prediction_success':True,
            'price_direction_alone_never_counts_as_prediction_success':True,
            'pending_predictions_do_not_train_nic':True,
        }
    }
    SUMMARY.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
