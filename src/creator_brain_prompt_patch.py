"""Runtime bridge: make Creator Brain + publication context authoritative for Gemini drafting."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'src/multi_agent_creator.py'
BRAIN=ROOT/'data/live/creator_brain_decision.json'
CONTEXT=ROOT/'data/live/publication_context.json'
MARKER='CREATOR_BRAIN_5_1_RUNTIME_BRIDGE'

def read_json(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}

def main():
    text=TARGET.read_text(encoding='utf-8'); brain=read_json(BRAIN); ctx=read_json(CONTEXT)
    if not brain or not ctx: raise RuntimeError('Creator Brain 5.1 or publication context missing')
    if MARKER in text:
        print({'status':'CREATOR_BRAIN_5_1_BRIDGE_ALREADY_PRESENT'})
        return
    bridge=(
        "    brain_context = (\n"
        "        '\\n\\n"+MARKER+":\\n'\n"
        "        'AUTHORITATIVE CREATOR BRAIN DECISION:\\n' + json.dumps(brain, ensure_ascii=False, indent=2) +\n"
        "        '\\nAUTHORITATIVE PUBLICATION CONTEXT:\\n' + json.dumps(ctx, ensure_ascii=False, indent=2) +\n"
        "        '\\nRULE: frozen primary asset, story engine, editorial format and verified chart symbols are authoritative. The final output must be a finished Binance Square post, not instructions to another writer. Use exactly one specific question. Never invent a second asset, news fact, source, price, target, creator call or outcome.\\n'\n"
        "    )\n"
    )
    pattern=r'(\n\s*prompt\s*=\s*\(\s*\n)'
    text,n=re.subn(pattern, '\n'+bridge+r'\1', text, count=1)
    if n!=1: raise RuntimeError('Could not locate Gemini prompt construction')
    text=text.replace('"EDITORIAL LANE:\\n" + instruction+', 'brain_context + "EDITORIAL LANE:\\n" + instruction+', 1)
    TARGET.write_text(text,encoding='utf-8')
    print({'status':'CREATOR_BRAIN_5_1_BRIDGE_APPLIED'})
if __name__=='__main__':main()
