"""NIC 24.2 — Evidence-to-Content Integrity Gate.

Deterministic publication guard. The editorial draft may express the selected
opportunity in natural language, but it cannot change the authoritative asset,
decision, regime, trade contract, evidence time, or visual contract.

Shadow-safe by default. Set NIC24_2_ENFORCE=true to block publication.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/"data/live"
REPORTS=ROOT/"data/reports"
OUT=LIVE/"nic24_2_evidence_content_integrity.json"
MAX_MARKET_AGE_MINUTES=float(os.getenv("NIC24_2_MAX_MARKET_AGE_MINUTES","45"))
MAX_EVIDENCE_AGE_MINUTES=float(os.getenv("NIC24_2_MAX_EVIDENCE_AGE_MINUTES","180"))

TRADE_LANES={"technical_setup","high_volatility","top_gainers","top_losers",
             "capital_flow_long","capital_flow_short","creator_signal_outcome",
             "conditional_trade","follow_up"}
WATCH_STATES={"WATCH_ONLY","NO_TRADE","HOLD","WAIT","WATCH","NO-TRADE","NO TRADE"}
CERTAINTY_PATTERNS=[
    r"\bguaranteed\b", r"\bguarantee\b", r"\bcertain\b",
    r"\bwill (?:go|rise|pump|fall|drop|hit)\b", r"\bdefinitely\b",
    r"\bno doubt\b", r"\beasy profit\b", r"\bcan'?t lose\b", r"\brisk[- ]free\b",
]
HISTORICAL_CLAIM_PATTERNS=[
    r"\bwin[- ]rate\b", r"\bprofitable\b", r"\bbacktest(?:ed|ing)?\b",
    r"\bhistoric(?:al)?(?:ly)?\b.{0,40}\b(?:win|profit|return)\b",
    r"\b(?:returned|made|earned)\s+\d+(?:\.\d+)?\s*%",
]
DIRECTION_WORDS={"LONG","SHORT","BULLISH","BEARISH","UPSIDE","DOWNSIDE"}

def load(path, default=None):
    try:
        value=json.loads(Path(path).read_text(encoding="utf-8"))
        if default is None:
            return value if isinstance(value,dict) else {}
        return value if isinstance(value,type(default)) else default
    except Exception:
        return {} if default is None else default

def iso_dt(value):
    try: return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception: return None

def age_minutes(value):
    dt=iso_dt(value)
    return None if dt is None else (datetime.now(timezone.utc)-dt).total_seconds()/60.0

def norm_symbol(value):
    s=str(value or "").upper().replace("BINANCE:","").replace("$","").strip()
    return s[:-4] if s.endswith("USDT") else s

def report_path():
    explicit=os.getenv("DRAFT_PATH","").strip()
    if explicit:
        p=Path(explicit)
        if not p.exists(): raise SystemExit("DRAFT_PATH does not exist: "+explicit)
        return p
    reports=sorted(REPORTS.glob("*-multi-agent.json"),key=lambda p:p.stat().st_mtime,reverse=True)
    if not reports: raise SystemExit("No draft report found")
    return reports[0]

def draft_text(path):
    data=load(path,{})
    draft=data.get("draft") if isinstance(data.get("draft"),dict) else {}
    return data,draft,str(draft.get("post") or draft.get("text") or draft.get("content") or "").strip()

def selected_contract(frozen, context, preflight, draft_data=None):
    selected=preflight.get("selected_opportunity") if isinstance(preflight.get("selected_opportunity"),dict) else {}
    symbol=norm_symbol(frozen.get("symbol") or context.get("symbol") or selected.get("symbol"))
    category=str(frozen.get("category") or context.get("category") or selected.get("category") or "").lower()
    regime=str(frozen.get("regime") or context.get("market_phase") or "").upper()
    decision=str(frozen.get("decision") or frozen.get("state") or frozen.get("strategy_state") or "").upper()
    direction=str(frozen.get("direction") or selected.get("direction") or "").upper()
    levels={}
    for key in ("entry_trigger","entry","trigger","tp1","tp2","target","sl","invalidation","support","resistance","current_price"):
        value=frozen.get(key)
        if value is None: value=selected.get(key)
        if value is not None:
            try: levels[key]=float(value)
            except (TypeError,ValueError): pass
    setup=frozen.get("trade_setup") if isinstance(frozen.get("trade_setup"),dict) else {}
    for key in ("entry_trigger","trigger","tp1","tp2","target","sl","invalidation","support","resistance","current_price"):
        if key not in levels and setup.get(key) is not None:
            try: levels[key]=float(setup[key])
            except (TypeError,ValueError): pass
    # The technical enricher freezes its candle-derived levels in the current
    # draft artifact. Use these only to fill fields absent from the upstream
    # opportunity contract; never let editorial prose provide replacement values.
    draft_data=draft_data if isinstance(draft_data,dict) else {}
    draft=draft_data.get("draft") if isinstance(draft_data.get("draft"),dict) else {}
    enriched=draft.get("technical_levels") if isinstance(draft.get("technical_levels"),dict) else {}
    research=draft_data.get("research") if isinstance(draft_data.get("research"),dict) else {}
    chart_levels=research.get("chart_levels") if isinstance(research.get("chart_levels"),dict) else {}
    for source in (chart_levels,enriched):
        for key in ("entry_trigger","entry","trigger","tp1","tp2","target","sl","invalidation","support","resistance","current_price"):
            if key not in levels and source.get(key) is not None:
                try: levels[key]=float(source[key])
                except (TypeError,ValueError): pass
    if not direction:
        direction=str(enriched.get("direction") or chart_levels.get("direction") or "").upper()
    return {"symbol":symbol,"category":category,"regime":regime,"decision":decision,
            "direction":direction,"levels":levels,
            "confidence":frozen.get("confidence",selected.get("confidence")),
            "conditional":frozen.get("conditional",True),
            "not_a_guarantee":frozen.get("not_a_guarantee",True)}

def extract_cashtags(text):
    return sorted({m.group(1).upper() for m in re.finditer(r"\$([A-Z][A-Z0-9]{0,14})\b",text.upper())})

def extract_labeled_numbers(text):
    found=[]
    pattern=r"(?i)\b(entry(?:\s+trigger)?|trigger|tp1|tp2|target(?:\s*\d+)?|take\s*profit|sl|stop\s*loss|invalidation|support|resistance|price)\b\s*[:=\-]?\s*\$?([0-9]+(?:\.[0-9]+)?)"
    for m in re.finditer(pattern,text):
        try: found.append((m.group(1).lower().replace(" ","_"),float(m.group(2))))
        except ValueError: pass
    return found

def equivalent_number(a,b): return abs(a-b)<=max(1e-9,abs(b)*0.002)

def tokens(text):
    return set(x for x in re.findall(r"[a-z0-9$]+",str(text).lower()) if len(x)>2)

def text_similarity(a,b):
    aa=tokens(a); bb=tokens(b)
    return len(aa&bb)/len(aa|bb) if aa|bb else 0.0

def recent_posts():
    p=ROOT/"analytics/publication_log.jsonl"
    if not p.exists(): return []
    out=[]
    for line in p.read_text(encoding="utf-8").splitlines()[-30:]:
        try:
            row=json.loads(line)
            if isinstance(row,dict):
                post=str(row.get("post") or row.get("text") or row.get("draft") or "").strip()
                if post: out.append(post)
        except Exception: pass
    return out[-8:]

def extract_percent_claims(text,symbol):
    if not symbol: return []
    pattern=r"(?i)\$?"+re.escape(symbol)+r"[^\n%]{0,120}([+-]\d+(?:\.\d+)?)%"
    return [float(m.group(1)) for m in re.finditer(pattern,text)]

def regime_contradictions(regime,text):
    r=str(regime or "").upper()
    low=str(text).lower()
    rules={
        "BREAKOUT_EXPANSION":(["range-bound","range bound","mean reversion","reversal confirmed"],["breakout confirmed","breakout","expansion"]),
        "TREND_CONTINUATION":(["trend reversal confirmed","mean reversion"],["trend","continuation","pullback"]),
        "MEAN_REVERSION":(["breakout confirmed","trend continuation confirmed"],["reversion","oversold","overbought"]),
        "MOMENTUM":(["range-bound","range bound"],["momentum","acceleration","impulse"]),
        "RANGE":(["breakout confirmed","trend continuation confirmed"],["range","sideways","consolidation"]),
    }
    forbidden,_=rules.get(r,([],[]))
    return [x for x in forbidden if x in low]

def main():
    path=report_path()
    data,draft,text=draft_text(path)
    frozen=load(LIVE/"authoritative_opportunity.json",{})
    context=load(LIVE/"publication_context.json",{})
    preflight=load(LIVE/"editorial_preflight.json",{})
    regime=load(LIVE/"nic24_regime_strategy_router.json",{})
    plan=load(LIVE/"nic24_1_strategy_content_plan.json",{})
    prediction=load(LIVE/"nic_prediction_engine.json",{})
    market=load(LIVE/"market_snapshot.json",{})
    visual=load(LIVE/"validate_trade_visual_contract.json",{})
    contract=selected_contract(frozen,context,preflight,data)
    failures=[]; warnings=[]; checks={}
    sym=contract["symbol"]

    if not text: failures.append("empty_draft")
    draft_symbol=norm_symbol(draft.get("symbol") or data.get("symbol"))
    checks["authoritative_symbol"]={"selected":sym,"draft_symbol":draft_symbol or None}
    if sym and draft_symbol and sym!=draft_symbol:
        failures.append(f"asset_drift:frozen={sym}:draft={draft_symbol}")

    allowed={sym} if sym else set()
    for x in context.get("headline_assets") or []:
        s=norm_symbol(x)
        if s: allowed.add(s)
    for x in context.get("chart_symbols") or []:
        s=norm_symbol(x)
        if s: allowed.add(s)
    foreign=[x for x in extract_cashtags(text) if x not in allowed]
    checks["cashtags"]={"allowed":sorted(allowed),"foreign":foreign}
    if foreign: failures.append("unauthorized_coin:"+",".join(foreign))

    state_values={contract["decision"],str(frozen.get("strategy") or "").upper(),
                  str(frozen.get("lane") or "").upper(),str(frozen.get("category") or "").upper()}
    watch=bool(state_values & WATCH_STATES)
    for source in (frozen,preflight.get("selected_opportunity") or {}):
        for key in ("decision","state","strategy_state","recommendation","trade_state"):
            if str(source.get(key) or "").upper() in WATCH_STATES: watch=True
    trade_terms=bool(re.search(r"(?i)\b(?:enter|entry|buy|sell|short|long|tp1|tp2|take\s*profit|stop\s*loss|invalidation)\b",text))
    checks["watch_only_guard"]={"watch_state":watch,"trade_terms_present":trade_terms}
    if watch and trade_terms: failures.append("watch_only_or_no_trade_promoted_to_trade")

    labeled=extract_labeled_numbers(text); mismatches=[]
    for label,value in labeled:
        candidates=[label]
        if label.startswith("target"): candidates+=["target","tp1","tp2"]
        if label=="take_profit": candidates+=["tp1","tp2","target"]
        if label in ("stop_loss","invalidation"): candidates+=["sl","invalidation"]
        if label=="trigger": candidates+=["entry_trigger","entry"]
        if label=="price": candidates+=["current_price"]
        expected=next((contract["levels"][k] for k in candidates if k in contract["levels"]),None)
        if expected is None: mismatches.append({"label":label,"value":value,"expected":None})
        elif not equivalent_number(value,expected): mismatches.append({"label":label,"value":value,"expected":expected})
    checks["labeled_numbers"]={"found":labeled,"mismatches":mismatches}
    if mismatches: failures.append("trade_or_market_number_mismatch")

    direction_hits=sorted({w for w in DIRECTION_WORDS if re.search(r"(?i)\b"+re.escape(w)+r"\b",text)})
    contradictions=regime_contradictions(contract["regime"],text)
    checks["regime_language_contradictions"]={"regime":contract["regime"],"contradictions":contradictions}
    if contradictions: failures.append("regime_language_contradiction:"+",".join(contradictions))
    expected=contract["direction"].replace("_BIAS","")
    contradictory={"LONG":{"SHORT","BEARISH","DOWNSIDE"},"SHORT":{"LONG","BULLISH","UPSIDE"}}.get(expected,set())
    bad=sorted(set(direction_hits)&contradictory)
    if bad: failures.append("direction_contradiction:"+",".join(bad))
    checks["direction"]={"authoritative":contract["direction"],"draft_hits":direction_hits}

    certainty=[p for p in CERTAINTY_PATTERNS if re.search(p,text,re.I)]
    checks["certainty_language"]=certainty
    if certainty and bool(contract.get("not_a_guarantee",True)): failures.append("unsupported_certainty_language")

    historical=[p for p in HISTORICAL_CLAIM_PATTERNS if re.search(p,text,re.I)]
    checks["historical_performance_claims"]=historical
    if historical:
        ledger_path=ROOT/"analytics/call_ledger.jsonl"
        if not ledger_path.exists(): failures.append("unsupported_historical_performance_claim")
        else: warnings.append("historical_performance_claim_requires_verified_ledger_attribution")

    ages={}
    for name,obj,field in (
        ("market_snapshot",market,"generated_at"),("publication_context",context,"locked_at"),
        ("regime",regime,"generated_at"),("content_plan",plan,"generated_at"),
        ("prediction",prediction,"generated_at")):
        ages[name]=age_minutes(obj.get(field))
    checks["evidence_ages_minutes"]=ages
    if ages["market_snapshot"] is None: failures.append("missing_market_timestamp")
    elif ages["market_snapshot"]>MAX_MARKET_AGE_MINUTES: failures.append("stale_market_data")
    for name in ("regime","content_plan","prediction"):
        if ages[name] is not None and ages[name]>MAX_EVIDENCE_AGE_MINUTES: warnings.append("stale_"+name)

    routes=regime.get("routes") if isinstance(regime.get("routes"),list) else []
    route=[r for r in routes if norm_symbol(r.get("symbol"))==sym]
    checks["regime_binding"]={"symbol":sym,"matching_routes":len(route),
                              "plan_matches":any(norm_symbol(p.get("symbol"))==sym for p in plan.get("plans") or [])}
    if not route and contract["category"] in TRADE_LANES:
        warnings.append("no_matching_regime_route_for_trade_lane")
    for p in plan.get("plans") or []:
        if norm_symbol(p.get("symbol"))==sym and contract["regime"] and str(p.get("regime") or "").upper()!=contract["regime"]:
            failures.append("regime_content_plan_mismatch")

    pct_claims=extract_percent_claims(text,sym)
    market_move=None
    for group in ("top_content_signals","top_gainers","top_losers","highest_volume","new_listing_market"):
        for item in market.get(group) or []:
            if isinstance(item,dict) and norm_symbol(item.get("symbol"))==sym:
                try: market_move=float(item.get("price_change_percent"))
                except (TypeError,ValueError): market_move=None
                break
        if market_move is not None: break
    checks["market_percent_claims"]={"claims":pct_claims,"authoritative":market_move}
    if market_move is not None and pct_claims:
        bad=[x for x in pct_claims if abs(x-market_move)>max(2.0,abs(market_move)*0.25)]
        if bad: failures.append("market_percent_claim_mismatch")
    
    recent=recent_posts()
    similarities=[round(text_similarity(text,p),4) for p in recent]
    max_similarity=max(similarities,default=0.0)
    checks["recent_post_similarity"]={"max":max_similarity,"threshold":0.86}
    if max_similarity>=0.86: failures.append("draft_too_similar_to_recent_post")

    if visual:
        vsyms={norm_symbol(x) for x in (visual.get("post_tickers") or visual.get("chart_symbols") or []) if norm_symbol(x)}
        if vsyms and sym not in vsyms: failures.append("chart_symbol_mismatch")
        vtf=str(visual.get("timeframe") or visual.get("chart_timeframe") or "").upper()
        ctf=str((context.get("visual_decision") or {}).get("timeframe") or "").upper()
        if vtf and ctf and vtf!=ctf: failures.append("chart_timeframe_mismatch")
    else:
        warnings.append("visual_contract_not_available_at_nic24_2")
    checks["visual_contract"]=visual or {"status":"NOT_AVAILABLE"}

    thesis_key=str(frozen.get("signal_thesis_key") or frozen.get("thesis_key") or "").strip()
    if thesis_key and thesis_key.lower() not in text.lower(): warnings.append("thesis_key_not_literal_in_draft")

    result={"schema":"NIC-24.2-EVIDENCE-TO-CONTENT-INTEGRITY","version":"24.2.1",
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "mode":"enforce" if os.getenv("NIC24_2_ENFORCE","false").lower()=="true" else "shadow",
            "passed":not failures,"publish":not failures,"draft_path":str(path),
            "authoritative":{"symbol":sym,"category":contract["category"],"direction":contract["direction"],
                             "decision":contract["decision"],"regime":contract["regime"],"levels":contract["levels"]},
            "checks":checks,"failures":failures,"warnings":warnings,
            "policy":[
                "Frozen opportunity is authoritative; editorial generation cannot introduce a different primary asset.",
                "Explicit trade levels and market numbers must match the frozen contract.",
                "WATCH_ONLY/NO_TRADE/HOLD/WAIT cannot be promoted into a trade recommendation.",
                "Unsupported certainty and unsupported historical-performance claims are blocked.",
                "Market evidence must be fresh enough for publication.",
                "Regime routing informs presentation but cannot override the authoritative decision.",
                "Chart symbol/timeframe must agree with the publication contract when available.",
                "NIC 24.2 never rewrites market facts; it only passes, warns, or blocks."
            ]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if failures and os.getenv("NIC24_2_ENFORCE","false").lower()=="true": raise SystemExit(24)

if __name__=="__main__": main()
