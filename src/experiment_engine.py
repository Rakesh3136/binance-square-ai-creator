from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/intelligence/experiment_queue.json'
FORMATS=['CHOICE','CHART CHALLENGE','COIN VS COIN','DATA SURPRISE','BREAKOUT OR FAKEOUT','NEWS REACTION','LIQUIDATION STORY','TOP MOVERS']
def main():
 d={'version':1,'queue':[{'id':f'EXP-{i+1:02d}','format':f,'status':'READY'} for i,f in enumerate(FORMATS)]}; OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(d,indent=2)); print(json.dumps(d))
if __name__=='__main__': main()
