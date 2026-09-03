"""Runtime bridge: make Creator Brain + publication context authoritative for Gemini drafting."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'src/multi_agent_creator.py'
BRAIN=ROOT/'data/live/creator_brain_decision.json'
CONTEXT=ROOT/'data/live/publication_context.json'
MARKER='CREATOR_BRAIN_5_1_RUNTIME_BRIDGE'

def read_json(p):
    import json
    try:
        x=json.loads(p.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception:return {}

def main():
    text=TARGET.read_text(encoding='utf-8')
    brain=read_json(BRAIN); ctx=read_json(CONTEXT)
    if not brain or not ctx: raise RuntimeError('Creator Brain 5.1 or publication context missing')
    block=(f"\\n\\n{MARKER}:\\n"
           "The following decision is authoritative for THIS production cycle. Do not choose a different primary asset, story engine, format or visual asset.\\n"
           "CREATOR BRAIN DECISION:\\n"+__import__('json').dumps(brain,ensure_ascii=False,indent=2)+
           "\\nPUBLICATION CONTEXT:\\n"+__import__('json').dumps(ctx,ensure_ascii=False,indent=2)+
           "\\nAUTHORITATIVE DRAFT RULES: The frozen primary asset must remain the cashtag in the final post. Follow the selected story engine and format. Use the selected verified event/source when news is present. Use only the TradingView symbols listed in publication context. Do not invent a second asset. The final text must be a finished post, not instructions to another writer. Exactly one specific question.\\n")
    # Inject immediately before the final prompt's existing PREFLIGHT section.
    pattern=r'(prompt\s*=\s*\(\s*\n\s*"EDITORIAL LANE:)'
    if MARKER not in text:
        text,n=re.subn(pattern, block+r'\1', text, count=1)
        if n!=1: raise RuntimeError('Could not locate Gemini prompt construction')
    TARGET.write_text(text,encoding='utf-8')
    print({'status':'CREATOR_BRAIN_5_1_BRIDGE_APPLIED','already_present':MARKER in text})
if __name__=='__main__':main()
