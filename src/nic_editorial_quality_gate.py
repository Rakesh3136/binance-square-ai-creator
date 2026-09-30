"""NIC Editorial Quality 3.2 + Conversion Intelligence 6.2.
Reader-facing gate with bounded, evidence-derived conversion repair.
The gate may recover an asset reference only from authoritative draft/contract
metadata or an explicit cashtag already present in the draft; it never invents
an asset. It never simulates clicks, trades, urgency, or revenue.
"""
from __future__ import annotations
import json, re, os
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
DRAFT=Path(os.getenv("DRAFT_PATH",""))
CONTRACT=ROOT/"data/live/nic_monetization_contract.json"
OUT=ROOT/"data/live/nic_editorial_quality_gate.json"
CONVERSION_OUT=ROOT/"data/live/nic_conversion_contract.json"
MAX_CHARS=740
INTERNAL_PATTERNS=[
    r"(?im)^\s*(?:attention|quality|engagement|opportunity|editorial)\s+score\s*[:=]\s*[^\n]+\n?",
    r"(?im)^\s*(?:experiment|campaign|cycle)\s*(?:id|day)?\s*[:=]\s*[^\n]+\n?",
    r"(?im)^\s*(?:generation_mode|content_lane|reader_payoff_type|hook_type)\s*[:=]\s*[^\n]+\n?",
]
GENERIC_OPENERS=[r"^For \$?[A-Z0-9]{2,15}, that matters because",r"^\$?[A-Z0-9]{2,15} is moving, but the useful signal is",r"^The \$?[A-Z0-9]{2,15} move is easy to see\."]
TRADE_PRESSURE=re.compile(r"\b(buy now|sell now|guaranteed|guarantee|100%|can't lose|must buy|must sell|urgent)\b",re.I)
ACTION_WORDS=re.compile(r"\b(inspect|check|compare|watch|verify|track|review|monitor|see|look|test|confirm|observe|follow)\b",re.I)
TICKER=re.compile(r"\$([A-Z][A-Z0-9]{1,14})\b",re.I)
def load_json(p):
    try:
        x=json.loads(p.read_text(encoding="utf-8")); return x if isinstance(x,dict) else {}
    except Exception: return {}
def resolve():
    if DRAFT and DRAFT.exists(): return DRAFT
    reports=sorted((ROOT/"data/reports").glob("*-multi-agent.json"),key=lambda p:p.stat().st_mtime_ns,reverse=True)
    if not reports: raise SystemExit("NIC editorial gate: no draft found")
    return reports[0]
def clean(text):
    text=str(text or "").strip()
    for pat in INTERNAL_PATTERNS: text=re.sub(pat,"",text)
    return re.sub(r"\n{3,}","\n\n",text).strip()
def normalize_asset(raw):
    return re.sub(r"[^A-Z0-9]","",str(raw or "").upper().replace("USDT",""))
def resolve_asset(contract,draft,text):
    """Resolve only from explicit authoritative metadata or an existing cashtag."""
    for raw in (contract.get("asset"),draft.get("asset"),draft.get("symbol"),draft.get("ticker")):
        a=normalize_asset(raw)
        if a: return a,"metadata"
    m=TICKER.search(text.upper())
    if m: return m.group(1).upper(),"draft_cashtag"
    return "","unknown"
def conversion_repair(text,asset):
    asset=normalize_asset(asset)
    if not asset: return text,[]
    repairs=[]; cashtag="$"+asset
    if not re.search(r"\$"+re.escape(asset)+r"\b",text,re.I):
        additions=[f"Check {cashtag} against the evidence above and watch whether the stated checkpoint confirms or rejects the thesis.",f"Review {cashtag} against the evidence above; the next checkpoint should confirm or reject the thesis."]
        for add in additions:
            candidate=text.rstrip()+"\n\n"+add
            if len(candidate)<=MAX_CHARS:
                text=candidate; repairs.append("asset_reference_and_action_bridge"); break
    if not ACTION_WORDS.search(text):
        add=f"Watch {cashtag} against the stated evidence and next checkpoint."
        candidate=text.rstrip()+"\n\n"+add
        if len(candidate)<=MAX_CHARS:
            text=candidate; repairs.append("reader_action_bridge")
    return text,repairs
def main():
    path=resolve(); report=load_json(path); draft=report.get("draft") if isinstance(report.get("draft"),dict) else {}
    text=str(draft.get("post") or draft.get("text") or "").strip()
    if not text: raise SystemExit("NIC editorial gate: empty draft")
    before=text; text=clean(text)
    if not text: raise SystemExit("NIC editorial gate: internal-only draft")
    contract=load_json(CONTRACT); lane=str(contract.get("content_lane") or draft.get("content_lane") or "market_setup")
    asset,asset_source=resolve_asset(contract,draft,text)
    text,conversion_repairs=conversion_repair(text,asset)
    asset_ok=bool(asset and re.search(r"\$"+re.escape(asset)+r"\b",text,re.I))
    opener=text.split("\n\n",1)[0]; generic=any(re.search(p,opener,re.I) for p in GENERIC_OPENERS)
    if text.count("?")>1:
        last=text.rfind("?"); text=text[:last].replace("?"," .")+text[last:]
    action_signal=bool(ACTION_WORDS.search(text))
    trade_pressure=bool(TRADE_PRESSURE.search(text))
    conversion_status="PASS" if asset_ok and action_signal and not trade_pressure else "BLOCK"
    conversion={"version":"6.2","status":conversion_status,"checked_at":datetime.now(timezone.utc).isoformat(),"asset":asset,"asset_source":asset_source,"cashtag":"$"+asset if asset else None,"content_lane":lane,"repair_count":len(conversion_repairs),"repairs":conversion_repairs,"reader_payoff_type":str(contract.get("reader_payoff_type") or draft.get("reader_payoff_type") or ""),"evidence":{"asset_reference_present":asset_ok,"reader_action_signal_present":action_signal,"trade_pressure_detected":trade_pressure,"reader_interaction_is_not_inferred":True,"views_are_not_revenue":True,"verified_reward_required":True},"contract":{"interaction_goal":"truthful inspection of the relevant asset surface","cashtag_is_contextual_bridge":True,"no_fake_urgency":True,"no_trade_guarantee":True,"no_synthetic_clicks_or_trades":True}}
    draft.update({"text":text,"post":text,"content_lane":lane,"resolved_asset":asset,"reader_facing_sanitized":True,"internal_telemetry_removed":before!=text,"template_opening_detected":generic,"question_count":text.count("?")})
    ok=text.count("?")==1 and len(text)<=MAX_CHARS and conversion_status=="PASS"
    report["nic_editorial_quality_gate"]={"version":"3.2+6.2","status":"PASS" if ok else "BLOCK","lane":lane,"resolved_asset":asset,"asset_source":asset_source,"template_opening_detected":generic,"internal_telemetry_removed":before!=text,"conversion_repairs":conversion_repairs,"checked_at":datetime.now(timezone.utc).isoformat(),"conversion_status":conversion_status,"rules":{"internal_telemetry_reader_hidden":True,"max_characters":MAX_CHARS,"exactly_one_question":True,"no_fact_invention":True,"truthful_reader_action_required":True,"no_trade_pressure":True}}
    if len(text)>MAX_CHARS or text.count("?")!=1: raise SystemExit("NIC editorial gate: copy must be <=740 characters and contain exactly one question")
    if conversion_status!="PASS": raise SystemExit("NIC conversion gate: post needs a relevant asset reference and a truthful reader-action signal, with no trade pressure")
    report["draft"]=draft; path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report["nic_editorial_quality_gate"],indent=2)+"\n",encoding="utf-8"); CONVERSION_OUT.write_text(json.dumps(conversion,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"editorial":report["nic_editorial_quality_gate"],"conversion":conversion},indent=2))
if __name__=="__main__": main()
