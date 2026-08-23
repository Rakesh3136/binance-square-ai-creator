from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]; SNAP=ROOT/'data/live/market_snapshot.json'; OUT=ROOT/'data/intelligence/market_timing.json'
def main():
 d=json.loads(SNAP.read_text()) if SNAP.exists() else {}; items=[]
 for group in ('top_gainers','top_losers','top_content_signals','highest_volume'):
  for x in d.get(group,[]) or []:
   if not isinstance(x,dict): continue
   move=float(x.get('price_change_percent') or 0); vol=float(x.get('quote_volume_usdt') or 0); rng=float(x.get('intraday_range_percent') or 0)
   if abs(move)>=25 and rng>=20: phase='OVERHEATED_OR_SHOCK'
   elif abs(move)>=10 and rng>=10: phase='ACTIVE_TREND'
   elif vol>0 and abs(move)<5: phase='COMPRESSION'
   else: phase='NORMAL'
   items.append({'symbol':x.get('symbol'),'phase':phase,'move':move,'range':rng,'volume':vol})
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps({'version':1,'items':items[:100]},indent=2)); print(json.dumps({'status':'OK','items':len(items)}))
if __name__=='__main__': main()
