import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main():
    cmd = sys.argv[1]
    if cmd == "manual-topic":
        p = Path("data/live/editorial_preflight.json")
        d = load(p)
        d.update(run_ai=True, reason="manual_topic")
        p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    elif cmd == "gate":
        status = load("data/live/creator_status.json") if Path("data/live/creator_status.json").exists() else {}
        if status.get("status") != "AI_SUCCESS":
            print(json.dumps({"publish": False, "reason": status.get("reason", "no fresh AI draft")}))
            print("publish=false", file=open(os.environ["GITHUB_OUTPUT"], "a"))
            return
        drafts = sorted(Path("data/reports").glob("*multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        draft = drafts[0] if drafts else None
        if not draft or (datetime.now().timestamp() - draft.stat().st_mtime) > 1200:
            print(json.dumps({"publish": False, "reason": "no fresh draft"}))
            print("publish=false", file=open(os.environ["GITHUB_OUTPUT"], "a"))
            return
        data = load(draft)
        r, c, d, v = data.get("research") or {}, data.get("critique") or {}, data.get("draft") or {}, data.get("visual_plan") or {}
        quality = float(d.get("quality_score") or 0)
        opportunity = max(float(r.get("opportunity_score") or 0), float(c.get("revised_opportunity_score") or 0))
        publish = quality >= 85 and opportunity >= 80 and data.get("status") == "DRAFT_ONLY_NOT_PUBLISHED" and bool((d.get("post") or "").strip())
        Path("/tmp/publish_gate.json").write_text(json.dumps({"draft": str(draft), "quality_score": quality, "opportunity_score": opportunity, "publish": publish}, indent=2))
        with open(os.environ["GITHUB_OUTPUT"], "a") as out:
            out.write(f"publish={'true' if publish else 'false'}\n")
            out.write(f"mode={'image' if v.get('use_visual') else 'text'}\n")
        print(json.dumps({"publish": publish, "quality_score": quality, "opportunity_score": opportunity, "mode": "image" if v.get('use_visual') else 'text'}, indent=2))
    elif cmd == "extract":
        d = load(os.environ["DRAFT_PATH"])
        post = ((d.get("draft") or {}).get("post") or "").strip()
        if not post: raise SystemExit("No publishable post")
        Path("/tmp/square-post.txt").write_text(post, encoding="utf-8")
    elif cmd == "record":
        d = load(os.environ["DRAFT_PATH"])
        result = Path("/tmp/publish-result.txt").read_text(encoding="utf-8")
        m = re.search(r"ID:\s*(\S+)", result)
        link = next((x.split("Link:", 1)[1].strip() for x in result.splitlines() if x.startswith("Link:")), None)
        r, draft, visual = d.get("research") or {}, d.get("draft") or {}, d.get("visual_plan") or {}
        strongest = str(r.get("strongest_signal") or "")[:200]
        symbol_match = re.search(r"\b([A-Z]{2,10})USDT\b", strongest.upper())
        symbol = symbol_match.group(1) if symbol_match else None
        if not symbol:
            for candidate in ("BTC", "ETH", "BNB", "XRP", "SOL", "DOGE", "ADA", "AVAX", "LINK", "TRX", "SUI", "TON", "DOT", "LTC", "BCH", "UNI", "XLM", "HBAR", "SHIB"):
                if re.search(rf"(?<![A-Z0-9])\$?{candidate}(?![A-Z0-9])", strongest.upper()):
                    symbol = candidate
                    break
        record = {"published_at": datetime.now(timezone.utc).isoformat(), "post_id": m.group(1) if m else None, "link": link, "symbol": symbol, "topic": strongest, "format": os.environ["MODE"], "hook": draft.get("hook", ""), "quality_score": draft.get("quality_score", 0), "opportunity_score": max(float(r.get("opportunity_score") or 0), float((d.get("critique") or {}).get("revised_opportunity_score") or 0)), "visual_type": visual.get("type", "none"), "status": "PUBLISHED_AUTONOMOUSLY"}
        p = Path("analytics/publication_log.jsonl"); p.parent.mkdir(exist_ok=True)
        with p.open("a", encoding="utf-8") as f: f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
