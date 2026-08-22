"""Autonomous engineering loop for the creator.

The agent may propose and merge small, tested improvements, but it cannot edit
workflow/auth/publishing infrastructure or its own safety policy. It uses one
LLM request per cycle and falls back to an evidence-only NO_CHANGE decision.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/self_engineer_policy.json"
MEMORY_PATH = ROOT / "analytics/strategy_memory.json"
PATTERNS_PATH = ROOT / "data/intelligence/creator_patterns.json"
FEEDBACK_PATH = ROOT / "data/live/feedback_strategy.json"
PREFLIGHT_PATH = ROOT / "data/live/editorial_preflight.json"
OUTPUT_PATH = ROOT / "data/live/self_engineering_report.json"

IMMUTABLE = {
    "config/self_engineer_policy.json",
    "src/self_engineer.py",
    "tests/test_self_engineering.py",
}
MAX_CONTEXT_CHARS = 12000


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def api_json(method: str, url: str, token: str, payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2026-03-10",
        "Content-Type": "application/json",
        "User-Agent": "binance-square-self-engineer",
    }
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=body, headers=headers, method=method)
    with urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def github_repo():
    repo = os.getenv("GITHUB_REPOSITORY", "Rakesh3136/binance-square-ai-creator")
    return repo


def gemini_generate(prompt: str) -> str:
    """Use the installed google-genai SDK with a single request."""
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(model=model, contents=prompt)
    return str(getattr(response, "text", "") or "")


def parse_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise ValueError("LLM did not return JSON")
        return json.loads(match.group(0))


def source_context():
    files = [
        "src/editorial_preflight.py",
        "src/engagement_engine.py",
        "src/creator_intelligence.py",
        "src/multi_agent_creator.py",
        "src/visual_renderer.py",
    ]
    chunks=[]
    for rel in files:
        p=ROOT/rel
        if p.exists():
            text=p.read_text(encoding="utf-8")
            chunks.append(f"\n--- {rel} ---\n{text[:MAX_CONTEXT_CHARS]}\n")
    return "".join(chunks)


def diagnostics():
    memory=load(MEMORY_PATH,{})
    patterns=load(PATTERNS_PATH,{})
    feedback=load(FEEDBACK_PATH,{})
    preflight=load(PREFLIGHT_PATH,{})
    return {
        "strategy_memory": memory,
        "creator_patterns_summary": {
            "sample_count": patterns.get("sample_count",0),
            "our_baseline": patterns.get("our_baseline",{}),
            "top_archetypes": patterns.get("performance_by_archetype",[])[:8],
            "our_formats": patterns.get("our_account_performance_by_format",[])[:8],
        },
        "feedback": feedback,
        "preflight": {
            "selected_opportunity": preflight.get("selected_opportunity"),
            "recent_topic_counts": preflight.get("recent_topic_counts",{}),
            "recent_category_counts": preflight.get("recent_category_counts",{}),
        },
    }


def build_prompt():
    policy=load(POLICY_PATH,{})
    diag=diagnostics()
    return f"""You are the engineering scientist for a crypto content creator.
Your job is to identify ONE high-confidence engineering improvement from real diagnostics.
Do not optimize for raw views alone: prioritize replies, follower conversion, originality,
content diversity, evidence quality, and reliability.

SAFETY CONTRACT:
- You may modify at most {policy.get('max_files_per_cycle',2)} files.
- Only paths explicitly allowed below may change.
- Never change workflow files, publishing/authentication code, secrets, the safety policy,
  this agent, or tests.
- Never add tokens, credentials, environment secrets, shell downloads, network calls,
  arbitrary subprocess execution, or code that publishes directly.
- Make ONE major behavioral change per cycle.
- Prefer small local logic/prompt/config improvements.
- If evidence is insufficient, return NO_CHANGE.
- Return COMPLETE replacement file contents, not a diff.

ALLOWED PATHS:
{json.dumps(policy.get('allowed_prefixes',[]), indent=2)}

DIAGNOSTICS:
{json.dumps(diag, indent=2, ensure_ascii=False)[:30000]}

CURRENT SOURCE CONTEXT:
{source_context()}

Return JSON only in this exact shape:
{{
  "decision": "CHANGE" or "NO_CHANGE",
  "title": "short change title",
  "reason": "evidence-based reason",
  "expected_metric": "reply_rate|follower_rate|reliability|diversity|evidence_quality",
  "files": [{{"path":"src/...py","content":"complete file content"}}],
  "validation": ["python -m py_compile ..."]
}}
"""


def validate(proposal, policy):
    if not isinstance(proposal, dict): raise ValueError("proposal must be an object")
    if proposal.get("decision") != "CHANGE": return False, "NO_CHANGE"
    files=proposal.get("files")
    if not isinstance(files,list) or not files: raise ValueError("missing files")
    if len(files) > int(policy["max_files_per_cycle"]): raise ValueError("too many files")
    blocked=list(policy.get("blocked_prefixes",[]))
    tokens=list(policy.get("blocked_tokens",[]))
    for item in files:
        path=str(item.get("path", ""))
        content=item.get("content")
        if not path or not isinstance(content,str): raise ValueError("invalid file item")
        if path in IMMUTABLE: raise ValueError(f"immutable path: {path}")
        if any(path.startswith(x) for x in blocked): raise ValueError(f"blocked path: {path}")
        if not any(path == x or path.startswith(x) for x in policy.get("allowed_prefixes",[])):
            raise ValueError(f"path not allowed: {path}")
        if any(token in content for token in tokens): raise ValueError(f"secret-like token in {path}")
        if len(content.splitlines()) > 1200: raise ValueError(f"file too large: {path}")
    return True, "CHANGE"


def changed_lines(original: str, new: str) -> int:
    import difflib
    diff=difflib.unified_diff(original.splitlines(),new.splitlines())
    return sum(1 for line in diff if (line.startswith("+") or line.startswith("-")) and not line.startswith(("+++","---")))


def apply_locally(files, policy):
    backups={}
    for item in files:
        path=item["path"]; target=ROOT/path
        old=target.read_text(encoding="utf-8") if target.exists() else ""
        delta=changed_lines(old,item["content"])
        if delta > int(policy["max_changed_lines_per_file"]):
            raise ValueError(f"change too large for {path}: {delta} lines")
        backups[path]=old
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(item["content"],encoding="utf-8")
    return backups


def restore(backups):
    for path,old in backups.items():
        (ROOT/path).write_text(old,encoding="utf-8")


def validate_code():
    commands=[
        [sys.executable,"-m","compileall","-q","src"],
        [sys.executable,"tests/test_self_engineering.py"],
    ]
    for cmd in commands:
        proc=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
        if proc.returncode != 0:
            return False, f"{cmd}: {proc.stdout[-1000:]} {proc.stderr[-2000:]}"
    return True,"validation passed"


def git(*args):
    return subprocess.run(["git",*args],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()


def create_branch_and_pr(proposal, policy):
    token=os.environ.get("GITHUB_TOKEN")
    if not token: raise RuntimeError("GITHUB_TOKEN missing")
    repo=github_repo()
    branch="self-engineer/"+re.sub(r"[^a-z0-9-]+","-",proposal.get("title","improvement").lower()).strip("-")[:45]
    branch += "-" + os.environ.get("GITHUB_RUN_ID","run")
    base_sha=api_json("GET",f"https://api.github.com/repos/{repo}/git/ref/heads/main",token)["object"]["sha"]
    api_json("POST",f"https://api.github.com/repos/{repo}/git/refs",token,{"ref":f"refs/heads/{branch}","sha":base_sha})
    git("checkout","-b",branch)
    for item in proposal["files"]:
        path=item["path"]; target=ROOT/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(item["content"],encoding="utf-8")
        git("add",path)
    git("-c","user.name=creator-engineer","-c","user.email=41898282+github-actions[bot]@users.noreply.github.com","commit","-m",f"Self-engineer: {proposal['title']}")
    git("push","-u","origin",branch)
    pr=api_json("POST",f"https://api.github.com/repos/{repo}/pulls",token,{"title":f"Self-engineer: {proposal['title']}","head":branch,"base":"main","body":f"## Autonomous engineering improvement\n\n{proposal.get('reason','')}\n\nExpected metric: `{proposal.get('expected_metric','')}`\n\nValidation passed locally before this PR was created."})
    if policy.get("auto_merge"):
        try:
            api_json("PUT",f"https://api.github.com/repos/{repo}/pulls/{pr['number']}/merge",token,{"merge_method":"squash"})
            merged=True
        except Exception:
            merged=False
    else: merged=False
    return {"branch":branch,"pr_number":pr["number"],"pr_url":pr.get("html_url"),"merged":merged}


def main():
    policy=load(POLICY_PATH,{})
    OUTPUT_PATH.parent.mkdir(parents=True,exist_ok=True)
    if not policy.get("enabled",False):
        print("Self engineering disabled"); return 0
    report={"status":"STARTED","policy_version":policy.get("version")}
    try:
        prompt=build_prompt()
        raw=gemini_generate(prompt)
        proposal=parse_json(raw)
        report["proposal"]={k:v for k,v in proposal.items() if k!="files"}
        ok,reason=validate(proposal,policy)
        if not ok:
            report.update({"status":"NO_CHANGE","reason":reason}); OUTPUT_PATH.write_text(json.dumps(report,indent=2),encoding="utf-8"); print(json.dumps(report,indent=2)); return 0
        backups=apply_locally(proposal["files"],policy)
        valid,msg=validate_code()
        restore(backups)
        if not valid:
            report.update({"status":"REJECTED_VALIDATION","reason":msg}); OUTPUT_PATH.write_text(json.dumps(report,indent=2),encoding="utf-8"); print(json.dumps(report,indent=2)); return 0
        result=create_branch_and_pr(proposal,policy)
        report.update({"status":"CHANGE_APPLIED","result":result,"validation":msg})
    except Exception as exc:
        report.update({"status":"ENGINEERING_ERROR","error":str(exc)})
    OUTPUT_PATH.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if report["status"] in {"CHANGE_APPLIED","NO_CHANGE","REJECTED_VALIDATION"} else 1


if __name__=="__main__": raise SystemExit(main())
