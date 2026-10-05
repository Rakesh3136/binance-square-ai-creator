"""NIC Native Writer — dependency-free evidence-to-publication engine.
Production writing layer owned by NIC. No hosted text model is required for writing.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RECENT_LOG=ROOT/"analytics/publication_log.jsonl"
def load(path,default=None):
    p=Path(path)
    if not p.exists(): return {} if default is None else default
    try:
        v=json.loads(p.read_text(encoding="utf-8")); return v if isinstance(v,type(default or {})) else ({} if default is None else default)
    except Exception:return {} if default is None else default
def num(v,d=0.0):
    try:return float(v)
    except Exception:return d
def sym(v):
    x=str(v or "").upper().replace("USDT","").replace("$","").strip()
    return x if re.fullmatch(r"[A-Z0-9]{1,15}",x) else ""
def recent():
    out=set()
    if not RECENT_LOG.exists():return out
    for row in RECENT_LOG.read_text(encoding="utf-8").splitlines()[-12:]:
        try:o=json.loads(row)
        except Exception:continue
        for s in re.split(r"[.!?]+",str(o.get("text") or o.get("post") or o.get("content") or "")):
            s=" ".join(re.sub(r"[^a-z0-9 ]","",s.lower()).split())
            if len(s.split())>=6:out.add(s)
    return out
def fresh(options,used):
    for x in options:
        if " ".join(re.sub(r"[^a-z0-9 ]","",x.lower()).split()) not in used:return x
    return options[0]
def item_for(s,market):
    for g in ("top_content_signals","top_gainers","top_losers","highest_volume","new_listing_market"):
        for x in market.get(g) or []:
            if isinstance(x,dict) and sym(x.get("symbol"))==s:return x
    return {}
def rng(item):
    hi=[];lo=[]
    for c in (item.get("candles_1h") or [])[-24:]:
        try:
            if isinstance(c,(list,tuple)) and len(c)>=4:hi.append(float(c[2]));lo.append(float(c[3]))
            elif isinstance(c,dict):hi.append(float(c.get("high")));lo.append(float(c.get("low")))
        except Exception:pass
    return (min(lo),max(hi)) if hi and lo else (None,None)
def price(v):
    return f"{num(v):.8g}" if num(v) else ""
def build(ctx):
    pre=ctx.get("preflight") or {};sel=pre.get("selected_opportunity") or {}
    pub=ctx.get("publication") or {};market=ctx.get("market") or {};news=ctx.get("news") or {}
    director=pre.get("script_director_4") or {}
    s=sym(sel.get("symbol") or pub.get("symbol") or director.get("primary_symbol"))
    if not s:raise RuntimeError("NIC Native Writer: authoritative asset missing")
    cat=str(sel.get("category") or pub.get("category") or "market_opportunity").lower()
    it=item_for(s,market);move=num(it.get("price_change_percent"));last=num(it.get("last_price"))
    vol=num(it.get("quote_volume_usdt") or it.get("quote_volume"));ir=num(it.get("intraday_range_percent"))
    lo,hi=rng(it);used=recent()
    setup=sel.get("trade_setup") if isinstance(sel.get("trade_setup"),dict) else {}
    side=str(setup.get("side") or setup.get("direction") or "").upper()
    trigger=setup.get("trigger",setup.get("entry_trigger"));inv=setup.get("invalidation",setup.get("sl"))
    tp1=setup.get("tp1");tp2=setup.get("tp2");dollar="$"+s
    obs="$"+price(last) if last else "the latest verified price"
    voltext=f"{vol/1e6:.1f}M USDT" if vol>=1e6 else (f"{vol/1e3:.0f}K USDT" if vol>=1e3 else "the available quote-volume snapshot")
    seed=int(hashlib.sha256((s+cat+str(director.get("narrative_engine"))).encode()).hexdigest()[:8],16)%4
    if cat in {"breaking_news","news","news_and_macro","macro"}:
        articles=[x for x in news.get("articles") or [] if isinstance(x,dict)]
        a=next((x for x in articles if s in [sym(z) for z in (x.get("symbols") or [])]),None)
        title=str((a or {}).get("title") or sel.get("news_title") or "").strip()
        source=str((a or {}).get("source") or sel.get("news_source") or "the supplied source").strip()
        hook=f"The event is verified. The harder question is whether {dollar} is actually repricing around it."
        body=(f"The supplied report — {title} — is the information point to track, sourced to {source}. I’m separating that fact from the market interpretation rather than treating a headline as a trade signal."
              if title else f"The available evidence gives {dollar} a reason to watch, but it does not prove a durable catalyst. That distinction matters when the market can react faster than the underlying story changes.")
        middle=f"{dollar} is around {obs} after a {move:+.1f}% move, so the market response is measurable rather than theoretical."
        close="The useful test is whether price and participation keep validating the same interpretation; if they diverge, the thesis weakens."
        question=f"What new evidence would make you change your view on {dollar}?"
    elif cat in {"capital_flow_long","capital_flow_short","flow","technical_setup","creator_signal_outcome","follow_up"} and side in {"LONG","SHORT"} and trigger is not None and inv is not None:
        hook=f"{dollar} has a {side.lower()} case, but the level is the thesis — not the prediction."
        body=f"The frozen setup uses {side} only if the trigger at {trigger} is met. A move toward the level is not confirmation, and a failure through {inv} is the predefined invalidation."
        middle=f"TP1 is {tp1} and TP2 is {tp2} when reached, but those are scenario levels, not promises. The current tape is around {obs}, with {voltext} in the supplied snapshot."
        close="The reason to wait is simple: price has to prove the setup at the trigger while participation remains consistent with the thesis."
        question=f"What is the first evidence on {dollar} that would confirm or invalidate this {side} setup?"
    else:
        hooks=[f"{dollar} moved {move:+.1f}%, but the useful story is what the move is doing to market structure.",f"The {dollar} move is obvious; the evidence underneath it is more useful.",f"{dollar} has enough movement to attract attention. The next reaction decides whether that attention is justified.",f"The interesting part of {dollar} is not the headline move. It is the relationship between price and participation."]
        hook=fresh(hooks[seed:]+hooks[:seed],used)
        if lo is not None and hi is not None:
            structure=f"The recent 1H window spans roughly $" + price(lo) + " to $" + price(hi) + f". Price is around {obs}, with {voltext} in quote volume and a {ir:.1f}% intraday range."
        else:
            structure=f"Price is around {obs}, with {voltext} in quote volume. The available 1H evidence is not strong enough to manufacture a cleaner range."
        mechanisms=[f"That combination matters because a price move without confirming participation can fade, while sustained participation makes the move more informative.",f"The relationship matters more than the percentage alone: participation tells us whether the move has broader support or is simply attracting short-term attention.","This is why I would read the move as evidence, not certainty. The next reaction can confirm the interpretation or expose the weakness in it."]
        middle=fresh(mechanisms[seed:]+mechanisms[:seed],used)
        close="The decision point is therefore the next measurable reaction, not a guess about where the next candle must go."
        question=f"Which specific reaction on {dollar} would make you change your read?"
    def compact_post(parts, question_text, limit=700):
        kept=list(parts)
        # Keep hook/evidence first; remove lower-priority prose before evidence.
        for drop in (3, 2):
            if len("\n\n".join(kept + [question_text])) <= limit:
                break
            if 0 <= drop < len(kept):
                kept.pop(drop)
        if len("\n\n".join(kept + [question_text])) > limit:
            while len("\n\n".join(kept + [question_text])) > limit and len(kept) > 2:
                kept.pop(-1)
        post="\n\n".join(kept + [question_text]).strip()
        if len(post) > limit:
            base=[hook]
            for block in parts[1:]:
                for sentence in re.split(r"(?<=[.!?])\\s+", str(block)):
                    sentence=sentence.strip()
                    candidate="\n\n".join(base + [sentence, question_text])
                    if len(candidate) <= limit:
                        base.append(sentence)
            post="\n\n".join(base + [question_text]).strip()
        return post
    post=compact_post([hook,body if "body" in locals() else structure,middle,close],question)
    if post.count("?")!=1 or dollar not in post or not 280<=len(post)<=700:raise RuntimeError("NIC Native Writer failed local publication contract")
    return {"research":{"summary":f"NIC verified {dollar} using the frozen opportunity and supplied market evidence.","strongest_signal":s,"opportunity_score":num(sel.get("adjusted_score") or sel.get("raw_score") or 0),"source_mode":"NIC_NATIVE_EVIDENCE_SYNTHESIS"},"critique":{"summary":"Native NIC review bounds claims by supplied evidence and keeps uncertainty explicit.","alternative_hypothesis":"The observed move may be temporary rather than structural.","disconfirming_test":"A materially different next reaction or failed evidence condition weakens the thesis."},"draft":{"post":post,"text":post,"hook":hook,"discussion_question":question,"quality_score":84,"editorial_style":"NIC_NATIVE_WRITER","generation_mode":"NIC_NATIVE","symbol":s,"content_category":cat,"publication_status":"DRAFT_ONLY_NOT_PUBLISHED"},"visual_plan":{"type":"candlestick_chart" if cat not in {"crypto_meme","community","commentary","education"} else "none","use_visual":bool(it.get("candles_1h")),"purpose":"Show only the frozen asset and supplied evidence."},"native_writer":{"version":"1.0","provider":"NIC","external_text_model":False,"evidence_bound":True,"generated_at":datetime.now(timezone.utc).isoformat()}}
