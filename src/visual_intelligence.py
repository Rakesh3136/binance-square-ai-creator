from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]; SNAP=ROOT/'data/live/market_snapshot.json'; OUT=ROOT/'data/intelligence/visual_decision.json'
def main():
 d=json.loads(SNAP.read_text()) if SNAP.exists() else {}; decision={'version':1,'type':'none','rules':['Use real OHLCV only.','Never invent chart patterns or levels.']}
 if d.get('top_content_signals'): decision.update({'type':'candlestick_chart','reason':'Market opportunity has verified OHLCV content signals.'})
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(decision,indent=2)); print(json.dumps(decision))
if __name__=='__main__': main()
