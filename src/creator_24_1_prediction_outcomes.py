"""Creator 24.1 — fresh-data prediction outcome verifier.

Evaluates OPEN calls against fresh Binance 1H candles. A call can only become
WIN, LOSS or INVALIDATED when the candle path objectively crosses the frozen
levels. Ambiguous candles remain OPEN. The original prediction is immutable.
"""
from __future__ import annotations
import json, urllib.parse, urllib.request, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; LEDGER=ROOT/'analytics/call_ledger.jsonl'; OUT=ROOT/'analytics/prediction_outcomes.jsonl'; SUMMARY=ROOT/'data/intelligence/prediction_outcomes.json'
BASES=['https://data-api.binance.vision','https://api-gcp.binance.com','https://api1.binance.com']

def num(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def candles(symbol):
    q=urllib.parse.urlencode({'symbol':symbol+'USDT','interval':'1h','limit':3})
    last=None
    for base in BASES:
        try:
            req=urllib.request.Request(base+'/api/v3/klines?'+q,headers={'User-Agent':'binance-square-ai-creator/24.1','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read().decode('utf-8'))
        except Exception as e:last=e
    raise RuntimeError(str(last))

def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def candle_time(row):
    try:
        return datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc)
    except Exception:
        return None


def ordered_outcome(direction, candles, trigger, targets, invalidation, created_at):
    direction = str(direction or "").upper()
    if direction not in {"LONG", "SHORT"}:
        return "OPEN", None, "invalid direction"

    trigger = num(trigger)
    invalidation = num(invalidation)
    targets = [num(x) for x in (targets or []) if num(x) is not None]
    if trigger is None or invalidation is None or not targets:
        return "OPEN", None, "missing frozen setup levels"

    start_time = parse_time(created_at)
    usable = []
    for row in candles:
        ct = candle_time(row)
        if ct is not None and start_time is not None and ct <= start_time:
            continue
        if ct is not None:
            usable.append((ct, row))
    usable.sort(key=lambda x: x[0])
    if not usable:
        return "OPEN", None, "no candles after prediction creation time"

    activated = False
    for _, row in usable:
        high = num(row[2])
        low = num(row[3])
        if high is None or low is None:
            continue

        if not activated:
            trigger_hit = high >= trigger if direction == "LONG" else low <= trigger
            if not trigger_hit:
                # A stop/target before activation is irrelevant: the conditional
                # trade never existed yet.
                continue
            activated = True

        stop_hit = low <= invalidation if direction == "LONG" else high >= invalidation
        target_hits = []
        for idx, target in enumerate(targets, start=1):
            hit = high >= target if direction == "LONG" else low <= target
            if hit:
                target_hits.append((idx, target))

        if stop_hit and target_hits:
            return "AMBIGUOUS", None, "same completed candle crossed both invalidation and target; intrabar order unknown"
        if stop_hit:
            return "INVALIDATED", None, "post-trigger candle crossed frozen invalidation"
        if target_hits:
            idx, target = target_hits[0]
            return "WIN", target, f"post-trigger candle crossed TP{idx}"

    return "OPEN", None, "trigger not crossed, or no post-trigger terminal level crossed"


def main():
    calls=[]
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict) and x.get('status')=='OPEN':
                    calls.append(x)
            except Exception:
                pass

    now=datetime.now(timezone.utc).isoformat()
    outcomes=[]
    errors=[]

    existing_ids=set()
    if OUT.exists():
        for line in OUT.read_text(encoding='utf-8').splitlines():
            try:
                x=json.loads(line)
                if str(x.get('call_id') or ''):
                    existing_ids.add(str(x.get('call_id')))
            except Exception:
                pass

    for call in calls:
        cid=str(call.get('call_id') or '')
        symbol=str(call.get('symbol') or '').upper()
        direction=str(call.get('direction') or '').upper()
        targets=[num(x) for x in call.get('targets',[]) if num(x) is not None]
        inv=num(call.get('invalidation'))
        ref=num(call.get('reference_price'))
        created_at=call.get('created_at') or call.get('signal_created_at') or call.get('opened_at')

        if not cid or not symbol or ref is None or not targets or inv is None:
            continue

        try:
            raw=candles(symbol, limit=48)
        except Exception as e:
            errors.append({'call_id':cid,'error':str(e)})
            continue

        usable_rows=[r for r in raw if isinstance(r,list) and len(r)>6]
        if not usable_rows:
            continue

        outcome, hit_target, reason=ordered_outcome(
            direction, usable_rows,
            call.get('trigger') or call.get('entry_trigger') or call.get('entry'),
            targets, inv, created_at
        )

        # Only append terminal outcomes once. OPEN/AMBIGUOUS states may be
        # re-evaluated in a later cycle, while terminal calls are immutable.
        if outcome in {'WIN','INVALIDATED'} and cid in existing_ids:
            continue

        latest_high=max(num(r[2]) for r in usable_rows if num(r[2]) is not None)
        latest_low=min(num(r[3]) for r in usable_rows if num(r[3]) is not None)
        row={
            'evaluated_at':now,
            'call_id':cid,
            'post_id':call.get('post_id'),
            'symbol':symbol,
            'direction':direction,
            'reference_price':ref,
            'trigger':num(call.get('trigger') or call.get('entry_trigger') or call.get('entry')),
            'targets':targets,
            'invalidation':inv,
            'observed_high':latest_high,
            'observed_low':latest_low,
            'outcome':outcome,
            'hit_target':hit_target,
            'reason':reason,
            'source':'fresh Binance 1H OHLCV',
            'evaluator_version':'25.0-trigger-first-state-machine',
            'prediction_immutable':True
        }
        if outcome == 'OPEN':
            # Do not append an unbounded stream of identical OPEN rows.
            previous=[x for x in jsonl(OUT) if str(x.get('call_id') or '')==cid]
            if previous:
                last=previous[-1]
                if last.get('outcome')=='OPEN':
                    continue
        outcomes.append(row)

    if outcomes:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        with OUT.open('a',encoding='utf-8') as f:
            for x in outcomes:
                f.write(json.dumps(x,ensure_ascii=False)+'\n')

    all_rows=[]
    if OUT.exists():
        for line in OUT.read_text(encoding='utf-8').splitlines():
            try:
                all_rows.append(json.loads(line))
            except Exception:
                pass

    terminal=[x for x in all_rows if x.get('outcome') in {'WIN','INVALIDATED','AMBIGUOUS'}]
    report={
        'version':'25.0-trigger-first-state-machine',
        'checked_at':now,
        'open_calls_seen':len(calls),
        'new_outcomes':len(outcomes),
        'wins':sum(x.get('outcome')=='WIN' for x in all_rows),
        'invalidated':sum(x.get('outcome')=='INVALIDATED' for x in all_rows),
        'ambiguous':sum(x.get('outcome')=='AMBIGUOUS' for x in all_rows),
        'terminal_outcomes':len(terminal),
        'errors':errors,
        'rules':[
            'A conditional prediction cannot win unless its entry trigger is crossed first.',
            'Pre-trigger target/stop touches do not resolve a call.',
            'If one completed candle crosses both target and invalidation, the result is AMBIGUOUS because intrabar order is unknown.',
            'Frozen reference/trigger/targets/invalidation remain immutable.',
            'No result is declared without fresh Binance OHLCV.'
        ]
    }
    SUMMARY.parent.mkdir(parents=True,exist_ok=True)
    SUMMARY.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    try:
        subprocess.run(['python',str(ROOT/'src/public_prediction_proof.py')],cwd=ROOT,check=False)
    except Exception:
        pass
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0

if __name__=='__main__':main()
