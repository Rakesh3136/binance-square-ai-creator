"""Bounded autonomous engineering loop for the creator business layer."""
from __future__ import annotations
import json, os, re, subprocess, sys
from pathlib import Path
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]
POLICY_PATH=ROOT/"config/self_engineer_policy.json"
OUTPUT_PATH=ROOT/"data/live/self_engineering_report.json"
IMMUTABLE={"config/self_engineer_policy.json","src/self_engineer.py","tests/test_self_engineering.py"}
MAX_CONTEXT_CHARS=7000


def load(path, default):
    try: return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception: return default


def api_json(method,url,token,payload=None):
    headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {token}","X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json","User-Agent":"binance-square-self-engineer"}
    body=json.dumps(payload).encode() if payload is not None else None
    with urlopen(Request(url,data=body,headers=headers,method=method),timeout=30) as r:
        raw=r.read().decode(); return json.loads(raw) if raw else {}


def gemini_generate(prompt):
    from google import genai
    client=genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response=client.models.generate_content(model=os.getenv("GEMINI_MODEL","gemini-3.6-flash"),contents=prompt)
    return str(getattr(response,"text","") or "")


def parse_json(text):
    text=text.strip()
    text=re.sub(r"^```(?:json)?\s*|\s*```$","",text)
    try: return json.loads(text)
    except Exception:
        m=re.search(r"\{.*\}",text,re.S)
        if not m: raise ValueError("LLM did not return JSON")
        return json.loads(m.group(0))


def context():
    names=["src/editorial_preflight.py","src/engagement_engine.py","src/creator_intelligence.py","src/multi_agent_creator.py","src/visual_renderer.py"]
    out=[]
    for n in names:
        p=ROOT/n
        if p.exists(): out.append(f"\n---{n}---\n{p.read_text(encoding='utf-8')[:MAX_CONTEXT_CHARS]}")
    return "".join(out)


def diagnostics():
    return {"strategy_memory":load(ROOT/"analytics/strategy_memory.json",{}),"patterns":load(ROOT/"data/intelligence/creator_patterns.json",{}),"feedback":load(ROOT/"data/live/feedback_strategy.json",{}),"preflight":load(ROOT/"data/live/editorial_preflight.json",{})}


def build_prompt(policy):
    return f"""You are the autonomous engineering scientist for a crypto content business.
You have broad BUSINESS-LAYER autonomy: improve prompts, content strategy, scoring, visuals,
experiments, timing, revenue strategy, publishing behavior and creator modules when evidence supports it.
Your goal is sustainable audience growth and monetization, not raw views alone.

Do NOT modify credentials, reveal secrets, disable emergency controls, or change the engineering
policy/agent/tests/workflow infrastructure. Runtime credentials are supplied by the platform.
You may change approved business-layer files and create new creator modules under approved prefixes.
Make one major experiment per cycle. Prefer small, testable changes. Return NO_CHANGE when evidence is weak.

POLICY:\n{json.dumps(policy,indent=2)}
DIAGNOSTICS:\n{json.dumps(diagnostics(),indent=2,ensure_ascii=False)[:30000]}
SOURCE:\n{context()}

Return JSON only: {{"decision":"CHANGE|NO_CHANGE","title":"...","reason":"...","expected_metric":"reply_rate|follower_rate|reliability|diversity|evidence_quality|revenue","files":[{{"path":"src/...py","content":"complete file"}}]}}"""


def contains_credential_literal(content, blocked_tokens):
    # Environment-variable names are safe and are expected in creator code.
    # Reject only actual-looking credential assignments, private-key material,
    # or suspicious bearer/JWT literals. This prevents false positives when the
    # proposed source legitimately contains os.getenv("GEMINI_API_KEY").
    private_key=re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",content,re.I)
    if private_key: return True
    jwt=re.search(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",content)
    if jwt: return True
    for token in blocked_tokens:
        pattern=rf"(?:^|[\s,;(]){re.escape(token)}(?:\s*[:=]\s*|\s*\.setdefault\(\s*)['\"]([^'\"]+)['\"]"
        for m in re.finditer(pattern,content,re.I):
            value=m.group(1)
            if value and not value.startswith(("$","${","os.getenv","env(")) and len(value)>=16:
                return True
    generic=(
        r"(?:api[_-]?key|secret|access[_-]?token|private[_-]?key)\s*=\s*['\"][A-Za-z0-9_\-+/=]{24,}['\"]"
    )
    return bool(re.search(generic,content,re.I))


def validate(proposal,policy):
    if not isinstance(proposal,dict): raise ValueError("proposal must be object")
    if proposal.get("decision")!="CHANGE": return False,"NO_CHANGE"
    files=proposal.get("files")
    if not isinstance(files,list) or not files: raise ValueError("missing files")
    if len(files)>int(policy["max_files_per_cycle"]): raise ValueError("too many files")
    blocked=policy.get("blocked_prefixes",[]); tokens=policy.get("blocked_tokens",[])
    for item in files:
        path=str(item.get("path","")); content=item.get("content")
        if not path or not isinstance(content,str): raise ValueError("invalid file")
        if path in IMMUTABLE or any(path.startswith(x) for x in blocked): raise ValueError(f"blocked path: {path}")
        if not any(path==x or path.startswith(x) for x in policy.get("allowed_prefixes",[])): raise ValueError(f"path not allowed: {path}")
        if contains_credential_literal(content,tokens): raise ValueError(f"credential-like literal in {path}")
    return True,"CHANGE"


def delta(old,new):
    import difflib
    return sum(1 for x in difflib.unified_diff(old.splitlines(),new.splitlines()) if (x.startswith("+") or x.startswith("-")) and not x.startswith(("+++","---")))


def validate_code():
    for cmd in ([sys.executable,"-m","compileall","-q","src"],[sys.executable,"tests/test_self_engineering.py"]):
        p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
        if p.returncode: return False,p.stderr[-2000:]
    return True,"validation passed"


def git(*args): return subprocess.run(["git",*args],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()


def publish_change(proposal):
    token=os.environ.get("GITHUB_TOKEN"); repo=os.getenv("GITHUB_REPOSITORY","Rakesh3136/binance-square-ai-creator")
    if not token: raise RuntimeError("GITHUB_TOKEN missing")
    slug=re.sub(r"[^a-z0-9-]+","-",proposal.get("title","improvement").lower()).strip("-")[:45]
    branch=f"self-engineer/{slug}-{os.getenv('GITHUB_RUN_ID','run')}"
    base=api_json("GET",f"https://api.github.com/repos/{repo}/git/ref/heads/main",token)["object"]["sha"]
    api_json("POST",f"https://api.github.com/repos/{repo}/git/refs",token,{"ref":f"refs/heads/{branch}","sha":base})
    git("checkout","-b",branch)
    for item in proposal["files"]:
        p=ROOT/item["path"]; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(item["content"],encoding="utf-8"); git("add",item["path"])
    git("-c","user.name=creator-engineer","-c","user.email=41898282+github-actions[bot]@users.noreply.github.com","commit","-m",f"Self-engineer: {proposal['title']}")
    git("push","-u","origin",branch)
    pr=api_json("POST",f"https://api.github.com/repos/{repo}/pulls",token,{"title":f"Self-engineer: {proposal['title']}","head":branch,"base":"main","body":proposal.get("reason","")})
    merged=False
    try:
        if load(POLICY_PATH,{}).get("auto_merge"): api_json("PUT",f"https://api.github.com/repos/{repo}/pulls/{pr['number']}/merge",token,{"merge_method":"squash"}); merged=True
    except Exception: pass
    return {"pr_number":pr["number"],"pr_url":pr.get("html_url"),"branch":branch,"merged":merged}


def main():
    policy=load(POLICY_PATH,{})
    report={"status":"STARTED","policy_version":policy.get("version")}
    try:
        proposal=parse_json(gemini_generate(build_prompt(policy)))
        report["proposal"]={k:v for k,v in proposal.items() if k!="files"}
        ok,why=validate(proposal,policy)
        if not ok: report.update(status="NO_CHANGE",reason=why)
        else:
            backups={}
            for item in proposal["files"]:
                p=ROOT/item["path"]; existed=p.exists(); old=p.read_text(encoding="utf-8") if existed else ""
                if delta(old,item["content"])>int(policy["max_changed_lines_per_file"]): raise ValueError(f"change too large: {item['path']}")
                backups[item["path"]]=(existed,old); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(item["content"],encoding="utf-8")
            try: valid,msg=validate_code()
            finally:
                for path,(existed,old) in backups.items():
                    p=ROOT/path
                    if existed: p.write_text(old,encoding="utf-8")
                    elif p.exists(): p.unlink()
            if not valid: report.update(status="REJECTED_VALIDATION",reason=msg)
            else: report.update(status="CHANGE_APPLIED",result=publish_change(proposal),validation=msg)
    except Exception as e: report.update(status="ENGINEERING_ERROR",error=str(e))
    OUTPUT_PATH.parent.mkdir(parents=True,exist_ok=True); OUTPUT_PATH.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8"); print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if report["status"] in {"CHANGE_APPLIED","NO_CHANGE","REJECTED_VALIDATION"} else 1

if __name__=="__main__": raise SystemExit(main())
