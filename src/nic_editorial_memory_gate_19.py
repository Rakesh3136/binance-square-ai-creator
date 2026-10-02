"""NIC 19 — editorial memory, novelty and repetition gate.

Purpose: stop the creator from publishing another near-identical asset story just
because the market scanner selected the same mover again. This is deterministic
and provider-neutral: it reads the publication ledger and current NIC context,
then decides whether a genuinely new story exists.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data/live"
ANALYTICS = ROOT / "analytics"
PREF = LIVE / "editorial_preflight.json"
CONTEXT = LIVE / "publication_context.json"
DISCOVERY = LIVE / "nic_story_discovery.json"
CRAFT = LIVE / "nic_content_craft_9.json"
ROUTING = LIVE / "signal_first_routing.json"
RESULT = LIVE / "nic_editorial_memory_gate_19.json"
LOG = ANALYTICS / "publication_log.jsonl"

# A short cool-down prevents the exact failure visible in the user's feed:
# the same asset being used as a fresh "market moved" story repeatedly within
# minutes. Follow-ups/outcomes/breaking events may bypass it when evidence exists.
ASSET_COOLDOWN_HOURS = 12.0
WINDOW_24H = 24.0
MAX_SAME_ASSET_24H = 2
FOLLOW_UP_KINDS = {
    "follow_up", "outcome_accountability", "breaking_news", "breaking", "research_lesson"
}


def load(path: Path, default=None):
    if default is None: default = {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def symbol(value) -> str:
    s = re.sub(r"USDT$", "", str(value or "").upper().replace("$", "").strip())
    return s if re.fullmatch(r"[A-Z0-9]{1,15}", s) else ""


def rows():
    if not LOG.exists(): return []
    out=[]
    for line in LOG.read_text(encoding="utf-8").splitlines()[-500:]:
        try: row=json.loads(line)
        except Exception: continue
        if isinstance(row,dict) and str(row.get("status") or "").startswith("PUBLISHED"):
            out.append(row)
    return out


def published_at(row):
    try:
        return datetime.fromisoformat(str(row.get("published_at") or row.get("timestamp") or "").replace("Z","+00:00"))
    except Exception:
        return None


def story_kind(discovery, context, craft):
    return str(
        discovery.get("story_kind") or discovery.get("selected_lane") or
        context.get("story_type") or context.get("story_kind") or
        craft.get("story_kind") or craft.get("archetype") or "market_setup"
    ).strip().lower().replace(" ", "_")


def evidence_changed(discovery, context):
    # A materially new event is allowed to reopen an asset. We deliberately
    # require explicit event/news/catalyst evidence instead of assuming that a
    # changed price is a new story.
    keys=("breaking_event","event_id","news_event_id","catalyst","new_information","follow_up_reason")
    for obj in (discovery, context):
        if any(str(obj.get(k) or "").strip() for k in keys): return True
    evidence=discovery.get("evidence")
    if isinstance(evidence,list):
        joined=" ".join(str(x).lower() for x in evidence)
        return any(k in joined for k in ("announcement","listing","delisting","upgrade","hack","exploit","unlock","etf","partnership","proposal","vote","earnings"))
    return False


def main():
    pre=load(PREF); ctx=load(CONTEXT); disc=load(DISCOVERY); craft=load(CRAFT); routing=load(ROUTING)
    selected=pre.get("selected_opportunity") if isinstance(pre.get("selected_opportunity"),dict) else {}
    asset=symbol(ctx.get("symbol") or ctx.get("primary_symbol") or selected.get("symbol"))
    kind=story_kind(disc,ctx,craft)
    now=datetime.now(timezone.utc)
    recent=[]
    for row in rows():
        rs=symbol(row.get("symbol") or row.get("selected_lane_symbol"))
        dt=published_at(row)
        if rs==asset and dt:
            age=now-dt
            if age <= timedelta(hours=WINDOW_24H): recent.append((age,row))
    recent.sort(key=lambda x:x[0])
    same_24=len(recent)
    newest=recent[0][0].total_seconds()/3600 if recent else None
    followup=kind in FOLLOW_UP_KINDS or evidence_changed(disc,ctx)

    allow=True; reasons=[]; score=100
    if not asset:
        allow=False; reasons.append("authoritative asset missing"); score=0
    elif same_24 >= MAX_SAME_ASSET_24H and not followup:
        allow=False; reasons.append(f"asset already published {same_24} times in 24h without a documented new event") ; score-=60
    elif newest is not None and newest < ASSET_COOLDOWN_HOURS and not followup:
        allow=False; reasons.append(f"same asset published {newest:.2f}h ago without a documented new event"); score-=70
    elif newest is not None and newest < ASSET_COOLDOWN_HOURS and followup:
        reasons.append("follow-up/new-event exception requires materially different story evidence")
        score-=10
    if kind in {"market_setup","top_movers","momentum","signal","technical_setup"} and same_24 and not followup:
        # Even when the hard cooldown is not hit, repeated signal-style coverage
        # is penalized. This is the editorial memory layer, not a cosmetic rewrite.
        score-=20
        reasons.append("repeated signal-style lane on recently covered asset")
        if newest is not None and newest < 6:
            allow=False

    if not asset:
        allow=False
    result={
        "version":"19.0",
        "status":"ALLOW" if allow else "SKIP",
        "allow":allow,
        "symbol":asset,
        "story_kind":kind,
        "novelty_score":max(0,score),
        "same_asset_posts_24h":same_24,
        "hours_since_latest_same_asset":round(newest,3) if newest is not None else None,
        "new_event_exception":followup,
        "reasons":reasons or ["no recent same-asset publication conflict"],
        "recent_same_asset":[{
            "post_id":str(r.get("post_id") or r.get("canonical_post_id") or ""),
            "published_at":r.get("published_at") or r.get("timestamp"),
            "story_type":r.get("story_type") or r.get("content_lane") or r.get("category"),
            "hook_type":r.get("hook_type"),
            "visual_type":r.get("visual_type")
        } for _,r in recent[:5]],
        "required_action":"WAIT_FOR_NEW_INFORMATION" if not allow else "PROCEED",
        "provider_independent":True,
        "generated_at":now.isoformat(),
    }
    RESULT.parent.mkdir(parents=True,exist_ok=True); RESULT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    # Keep the routing artifact explicit so downstream components can observe
    # the decision without having to import this module.
    if isinstance(routing,dict):
        routing["editorial_memory_gate_19"]={"allow":allow,"symbol":asset,"novelty_score":result["novelty_score"],"status":result["status"]}
        ROUTING.write_text(json.dumps(routing,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0

if __name__ == "__main__": raise SystemExit(main())
