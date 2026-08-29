"""Bounded AI coding agent: turns repair evidence into a reviewable patch.

The agent may generate a unified diff, but it cannot push, merge, alter secrets,
change GitHub Actions permissions, or deploy. The resulting patch is handed to
repair_sandbox.py for isolated validation.
"""
from __future__ import annotations
import json, os, re, subprocess
from datetime import datetime, timezone
from pathlib import Path
from google import genai

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'data/intelligence/self_repair_report.json'
OUT=ROOT/'data/intelligence/ai_code_patch.json'
MODEL=os.getenv('GEMINI_MODEL','gemini-3.6-flash')
FORBIDDEN=('secrets','credentials','\.github/workflows','deploy','publish')

def read_json(p):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except Exception:return {}

def repo_diff():
 p=subprocess.run(['git','diff','--','src','tests','test'],cwd=ROOT,text=True,capture_output=True)
 return p.stdout[-12000:]

def main():
 evidence=read_json(REPORT)
 prompt=f'''You are a senior software maintenance engineer. Diagnose the supplied repair evidence and propose ONE minimal, testable code patch. Do not invent files or APIs. Preserve existing behavior except where required to fix the evidence. Never modify secrets, credentials, deployment/publishing permissions, or GitHub Actions. Return ONLY a unified diff in a fenced diff block. Evidence: {json.dumps(evidence)[:12000]} Existing source diff: {repo_diff()}'''
 key=os.getenv('GEMINI_API_KEY')
 if not key:
  result={'status':'BLOCKED','reason':'GEMINI_API_KEY unavailable'}
 else:
  try:
   client=genai.Client(api_key=key); r=client.models.generate_content(model=MODEL,contents=prompt)
   text=getattr(r,'text','') or ''
   m=re.search(r'```diff\s*(.*?)```',text,re.S)
   patch=(m.group(1).strip() if m else '')
   bad=any(re.search(x,patch,re.I) for x in FORBIDDEN)
   if not patch or bad: result={'status':'BLOCKED','reason':'empty or forbidden patch'}
   elif len(patch.splitlines())>250: result={'status':'BLOCKED','reason':'patch exceeds 250 lines'}
   else: result={'status':'PATCH_READY','patch':patch,'model':MODEL}
  except Exception as e: result={'status':'BLOCKED','reason':f'{type(e).__name__}: {e}'}
 result['generated_at']=datetime.now(timezone.utc).isoformat();OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'status':result['status']}))
if __name__=='__main__':main()
