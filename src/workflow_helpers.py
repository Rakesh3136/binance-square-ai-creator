import json
import os
import re
import subprocess
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
        accepted_statuses = {"AI_SUCCESS", "LOCAL_FALLBACK_SUCCESS"}
        if status.get("status") not in accepted_statuses:
            print(json.dumps({"publish": False, "reason": status.get("reason", "no fresh AI draft")}))
            print("publish=false", file=open(os.environ["GITHUB_OUTPUT"], "a"))
            return
        drafts = sorted(Path("data/reports").glob("*multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        draft = drafts[0] if drafts else None
        if not draft or (datetime.now().timestamp() - draft.stat().st_mtime) > 1200:
            print(json.dumps({"publish": False, "reason": "no fresh draft"}))
            print("publish=false", file=open(os.environ["GITHUB_OUTPUT"], "a"))
            return

        # Creator Intelligence 2.0 is deliberately allowed to reject the draft.
        # It may also make safe editorial repairs before this gate evaluates it.
        subprocess.run([sys.executable, "src/creator_intelligence_2.py"], check=False)
        data = load(draft)
        r = data.get("research") or {}
        c = data.get("critique") or {}
        d = data.get("draft") or {}
        v = data.get("visual_plan") or {}
        selected = data.get("selected_editorial_lane") or {}
        preflight = load("data/live/editorial_preflight.json") if Path("data/live/editorial_preflight.json").exists() else {}
        preflight_selected = preflight.get("selected_opportunity") or {}
        post = str(d.get("post") or d.get("text") or "").strip()
        if not post:
            print(json.dumps({"publish": False, "reason": "draft has no post text"}))
            print("publish=false", file=open(os.environ["GITHUB_OUTPUT"], "a"))
            return
        try:
            from engagement_quality_gate import evaluate
            interaction_gate = evaluate(post, v)
        except Exception as exc:
            interaction_gate = {"score": 0, "publish": False, "reasons": [f"quality_gate_error:{type(exc).__name__}"]}

        intelligence = {}
        intel_path = Path("data/live/creator_intelligence_2.json")
        if intel_path.exists():
            try:
                intelligence = load(intel_path)
            except Exception:
                intelligence = {}
        explicit_quality = float(d.get("quality_score") or 0)
        if explicit_quality <= 0:
            explicit_quality = float(interaction_gate.get("score") or 0)
        quality = explicit_quality
        generation_mode = str(d.get("generation_mode") or data.get("generation_mode") or status.get("generation_mode") or "GEMINI").upper()
        quality_threshold = 72

        opportunity_values = []
        for obj, keys in (
            (r, ("opportunity_score", "adjusted_score", "engagement_score")),
            (c, ("revised_opportunity_score", "opportunity_score", "adjusted_score", "engagement_score")),
            (selected, ("adjusted_score", "raw_score", "engagement_score")),
            (preflight_selected, ("adjusted_score", "raw_score", "content_signal_score", "engagement_score")),
        ):
            if isinstance(obj, dict):
                for key in keys:
                    try:
                        value = float(obj.get(key) or 0)
                    except (TypeError, ValueError):
                        value = 0
                    if value > 0:
                        opportunity_values.append(value)
        opportunity = max(opportunity_values, default=0.0)

        intelligence_ok = intelligence.get("publish_recommendation") is True
        publish = (
            quality >= quality_threshold
            and opportunity >= 72
            and data.get("status") == "DRAFT_ONLY_NOT_PUBLISHED"
            and interaction_gate.get("publish") is True
            and intelligence_ok
        )
        gate_record = {
            "draft": str(draft),
            "quality_score": quality,
            "quality_threshold": quality_threshold,
            "generation_mode": generation_mode,
            "opportunity_score": opportunity,
            "opportunity_sources": {
                "research": r.get("opportunity_score"),
                "critique": c.get("revised_opportunity_score"),
                "selected_editorial_lane": selected.get("adjusted_score"),
                "preflight_selected_opportunity": preflight_selected.get("adjusted_score"),
            },
            "creator_intelligence_2": intelligence,
            "interaction_gate": interaction_gate,
            "publish": publish,
            "creator_status": status.get("status"),
            "reason": "publish_eligible" if publish else "gate_rejected",
        }
        Path("/tmp/publish_gate.json").write_text(json.dumps(gate_record, indent=2))
        Path("data/live/engagement_gate.json").write_text(json.dumps(interaction_gate, indent=2), encoding="utf-8")
        with open(os.environ["GITHUB_OUTPUT"], "a") as out:
            out.write(f"publish={'true' if publish else 'false'}\n")
            out.write(f"mode={'image' if v.get('use_visual') else 'text'}\n")
        print(json.dumps({
            "publish": publish,
            "quality_score": quality,
            "quality_threshold": quality_threshold,
            "generation_mode": generation_mode,
            "opportunity_score": opportunity,
            "opportunity_sources": gate_record["opportunity_sources"],
            "creator_intelligence_2": intelligence,
            "interaction_gate": interaction_gate,
            "mode": "image" if v.get("use_visual") else "text",
            "editorial_style": d.get("editorial_style", ""),
        }, indent=2))
    elif cmd == "extract":
        d = load(os.environ["DRAFT_PATH"])
        post = ((d.get("draft") or {}).get("post") or (d.get("draft") or {}).get("text") or "").strip()
        if not post:
            raise SystemExit("No publishable post")
        Path("/tmp/square-post.txt").write_text(post, encoding="utf-8")
        out = Path("data/live/publish_text.txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(post, encoding="utf-8")
        print(json.dumps({"status":"POST_TEXT_EXTRACTED","path":str(out),"characters":len(post)}))
    elif cmd == "record":
        d = load(os.environ["DRAFT_PATH"])
        result = Path("/tmp/publish-result.txt").read_text(encoding="utf-8")
        m = re.search(r"ID:\s*(\S+)", result)
        link = next((x.split("Link:", 1)[1].strip() for x in result.splitlines() if x.startswith("Link:")), None)
        r = d.get("research") or {}; draft = d.get("draft") or {}; visual = d.get("visual_plan") or {}; selected = d.get("selected_editorial_lane") or {}; engagement = d.get("engagement_strategy") or {}
        strongest = str(r.get("strongest_signal") or "")[:300]; symbol = None
        lane_symbol = str(selected.get("symbol") or "").upper(); lane_match = re.search(r"\b([A-Z0-9]{2,12})USDT\b", lane_symbol)
        if lane_match: symbol = lane_match.group(1)
        elif lane_symbol and re.fullmatch(r"[A-Z0-9]{2,10}", lane_symbol): symbol = lane_symbol
        if not symbol:
            symbol_match = re.search(r"\b([A-Z]{2,10})USDT\b", strongest.upper()); symbol = symbol_match.group(1) if symbol_match else None
        intelligence = d.get("creator_intelligence_2") or {}
        record = {"published_at":datetime.now(timezone.utc).isoformat(),"post_id":m.group(1) if m else None,"link":link,"symbol":symbol,"topic":strongest,"content_category":selected.get("category") or "unknown","selected_lane_symbol":selected.get("symbol"),"format":os.environ.get("MODE","unknown"),"editorial_style":draft.get("editorial_style",""),"hook":draft.get("hook",""),"discussion_question":draft.get("discussion_question",""),"experiment_id":engagement.get("experiment_id") or selected.get("experiment_id"),"experiment_format":(engagement.get("experiment") or {}).get("format"),"timing_hypothesis":(d.get("distribution_strategy") or {}).get("timing_hypothesis"),"quality_score":draft.get("quality_score",0),"opportunity_score":max(float(r.get("opportunity_score") or 0),float((d.get("critique") or {}).get("revised_opportunity_score") or 0),float(selected.get("adjusted_score") or 0)),"visual_type":visual.get("type","none"),"intelligence_score":intelligence.get("score"),"status":"PUBLISHED_AUTONOMOUSLY"}
        p=Path("analytics/publication_log.jsonl"); p.parent.mkdir(exist_ok=True)
        with p.open("a",encoding="utf-8") as f: f.write(json.dumps(record,ensure_ascii=False)+"\n")
        print(json.dumps(record,indent=2,ensure_ascii=False))

if __name__ == "__main__":
    main()
