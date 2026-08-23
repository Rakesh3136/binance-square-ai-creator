from pathlib import Path
import json
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/intelligence/thesis_ledger.json'
def load():
 try:return json.loads(OUT.read_text())
 except:return {'version':1,'theses':[]}
def main():
 d=load(); d['last_updated']=datetime.now(timezone.utc).isoformat(); d['rules']=['Never claim certainty.','Record the original thesis and later outcome separately.','Revisit unresolved theses when verified new evidence appears.']; OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(d,indent=2)); print(json.dumps(d))
if __name__=='__main__': main()
