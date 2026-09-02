"""Hard publication integrity gate for Creator 4.2.
Blocks stale/contradictory market claims and repetitive low-value copy before
TradingView rendering/publishing. It never repairs a factual mismatch silently.
"""
from __future__ import annotations
import json,re
from pathlib import Path
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[1]
MARKET=ROOT/"data/live/market_snapshot.json"
NEWS=ROOT/"data/live/news_snapshot.json"
PREFLIGHT=ROOT/"data/live/editorial_preflight.json"
REPORT_DIR=ROOT/"data/reports"
OUT=ROOT/"data/live/content_integrity_gate.json"
PUBLICATIONS=ROOT/"analytics/publication_log.jsonl"

GENERIC_HOOKS={
 "fresh check","quick market check","the headline is only half the story",
 "this is the crypto story i'm watching right now"
}
NEWS_REQUIRED_WORDS={"source:","reported","announced","according to","news"}

def load(p,default=None):
    try:
        x=json.loads(Path(p).read_text(encoding="utf-8"))
        return x if isinstance(x,type(default or {})) else ({} if default is None else default)
    except Exception:return {} if default is None else default

def latest_report():
    rs=sorted(REPORT_DIR.glob("*-multi-agent.json"),key=lambda p:p.stat().st_mtime,reverse=True)
    return rs[0] if rs else None

def symbol_of(s):
    s=re.sub(r"USDT$","",str(s or "").upper().replace("$","").replace("BINANCE:","")).strip()
    return s if re.fullmatch(r"[A-Z0-9]{1,15}",s) else ""

def find_market_item(market,symbol):
    target=symbol+"USDT"
    for group in ("top_content_signals","top_gainers","top_losers","highest_volume","new_listing_market"):
        for x in market.get(group) or []:
            if isinstance(x,dict) and str(x.get("symbol","")).upper()==target:
                return x
    return None

def extract_primary_move(text,symbol):
    prefix=r"\$"+re.escape(symbol)
    m=re.search(prefix+r"[^\n%]{0,120}([+-]\d+(?:\.\d+)?)%",text.upper())
    return float(m.group(1)) if m else None

def recent_hooks():
    hooks=[]
    if not PUBLICATIONS.exists(): return hooks
    cutoff=datetime.now(timezone.utc)-timedelta(hours=36)
    for line in PUBLICATIONS.read_text(encoding="utf-8").splitlines()[-80:]:
        try:
            r=json.loads(line)
            dt=datetime.fromisoformat(str(r.get("published_at","")).replace("Z","+00:00"))
            if dt<cutoff: continue
            h=str(r.get("hook") or "").strip().lower()
            if h: hooks.append(re.sub(r"\s+"," ",h))
        except Exception: pass
    return hooks

def similarity(a,b):
    wa=set(re.findall(r"[a-z0-9$]+",a.lower()))
    wb=set(re.findall(r"[a-z0-9$]+",b.lower()))
    return len(wa&wb)/max(1,len(wa|wb))

def main():
    report=latest_report()
    if not report: raise SystemExit("No fresh draft report")
    data=load(report); draft=data.get("draft") or {}
    text=str(draft.get("post") or draft.get("text") or "").strip()
    pre=load(PREFLIGHT); selected=pre.get("selected_opportunity") or {}
    context=load(ROOT/"data/live/publication_context.json"); market=load(MARKET); news=load(NEWS)
    sym=symbol_of(selected.get("symbol") or selected.get("topic") or context.get("symbol") or draft.get("symbol"))
    failures=[]; warnings=[]

    if not text: failures.append("empty_post")
    if not sym: failures.append("missing_primary_symbol")
    if text.count("?")!=1: failures.append("question_count_must_equal_one")

    hook=(text.splitlines()[0].strip().lower() if text else "")
    if any(g in hook for g in GENERIC_HOOKS): failures.append("generic_repetitive_hook")

    selected_news=bool(selected.get("news_title") or context.get("news_title"))
    # When news is authoritative, prevent the model from inventing unrelated cashtags.
    allowed_news_symbols=set()
    for raw in (selected.get("news_symbols") or []):
        sx=symbol_of(raw)
        if sx: allowed_news_symbols.add(sx)
    allowed_symbols={sym} | allowed_news_symbols
    cashtags={m.upper() for m in re.findall(r"\$([A-Z][A-Z0-9]{0,14})\b", text.upper())}
    foreign=sorted(x for x in cashtags if x not in allowed_symbols)
    if selected_news and foreign:
        failures.append("foreign_cashtag_not_supported_by_story:" + ",".join(foreign))
    if selected_news:
        title=str(selected.get("news_title") or context.get("news_title") or "").strip()
        if title and title.lower() not in text.lower():
            failures.append("selected_news_headline_not_present")
        if not any(k in text.lower() for k in NEWS_REQUIRED_WORDS):
            warnings.append("news_source_context_not_explicit")

    item=find_market_item(market,sym) if sym else None
    if item and sym:
        market_move=float(item.get("price_change_percent") or 0)
        claimed=extract_primary_move(text,sym)
        if claimed is not None:
            delta=abs(claimed-market_move)
            if delta>5.0:
                failures.append("market_move_mismatch:claimed="+format(claimed,".4g")+",snapshot="+format(market_move,".4g")+",delta="+format(delta,".4g"))
            elif delta>2.0:
                warnings.append("market_move_near_mismatch:claimed="+format(claimed,".4g")+",snapshot="+format(market_move,".4g"))
        price=float(item.get("last_price") or 0)
        if price<=0: failures.append("invalid_authoritative_market_price")
    elif sym:
        failures.append("authoritative_market_item_missing")

    hooks=recent_hooks()
    near=[]
    if hook:
        for h in hooks:
            sim=similarity(hook,h)
            if sim>=0.68: near.append((round(sim,2),h))
    if near: failures.append("hook_too_similar_to_recent_post")
    if hook in {h.lower() for h in hooks}: failures.append("duplicate_hook")

    low_value_phrases=("move is strong enough to watch","confirmation matters more than chasing it","which signal are you watching next")
    if sum(1 for p in low_value_phrases if p in text.lower())>=2:
        failures.append("low_information_fallback_copy")

    result={
      "version":"4.2","generated_at":datetime.now(timezone.utc).isoformat(),
      "publish":not failures,"symbol":sym,"selected_news":selected_news,
      "failures":failures,"warnings":warnings,"hook_similarity_matches":near[:5],
      "authoritative_price_change":float(item.get("price_change_percent") or 0) if item else None,
      "claimed_price_change":extract_primary_move(text,sym) if sym else None,
      "policy":["Never publish contradictory market figures.","Never silently overwrite factual claims to make them pass.","Never publish a generic repeated hook when a fresh angle is available.","News-selected posts must retain the actual headline.","One real question per post."]}

    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if failures: raise SystemExit(1)

if __name__=="__main__": raise SystemExit(main())
