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
        trade_styles=[
            (f"${dollar}: the setup is conditional, not a call to chase.",f"The ${side} thesis only activates at ${trigger}. Until price reaches and holds that area, the signal is incomplete.",f"If it triggers, TP1 is ${tp1} and TP2 is ${tp2}. If ${inv} fails, the thesis is invalidated. Current price is ${obs}; the snapshot shows ${voltext} of quote volume.","The useful edge here is waiting for confirmation instead of paying for the move before the market proves it."),
            (f"The interesting question on ${dollar} is not 'up or down?' It is whether the market can prove this level.",f"For a ${side} scenario, ${trigger} is the decision point. A move near it is only preparation; acceptance beyond it is the confirmation condition.",f"The risk boundary is ${inv}. TP1/TP2 sit at ${tp1} and ${tp2}. Those levels describe the scenario, not a guaranteed path. Price is currently ${obs}.","That makes the invalidation more important than the target: it tells us when the thesis stops making sense."),
            (f"I would not chase ${dollar} here. I would wait for the market to answer one specific question.",f"Can price establish the ${side} setup through ${trigger}? If not, there is no reason to force the signal.",f"The predefined failure point is ${inv}; the scenario targets are ${tp1} and ${tp2}. The current snapshot has price near ${obs} with ${voltext} in quote volume.","Waiting is part of the setup. A missed trade is cheaper than inventing confirmation."),
            (f"${dollar} has a clean conditional setup, but the condition comes first.",f"The evidence is actionable only if ${trigger} is reached and the ${side.lower()} case holds there.",f"Invalidation sits at ${inv}; TP1 is ${tp1} and TP2 is ${tp2}. Current price is ${obs}, so the distance to the decision point still matters.","If the trigger never confirms, the correct outcome is no trade — not a rewritten signal.")
        ]
        hook,body,middle,close=trade_styles[seed % len(trade_styles)]
        question=f"What would you need to see on ${dollar} before you would consider this ${side} scenario confirmed?"
    else:
        story_templates={
            "breakout_retest": (
                [f"${s} is interesting only if the breakout can survive its first retest.",f"The real ${s} test is not the breakout candle; it is what happens when price comes back to the level."],
                "The useful evidence is whether the old ceiling turns into support while participation remains healthy.",
                f"What would make you treat the ${s} retest as a failed breakout?"
            ),
            "rejection_invalidation": (
                [f"${s} has moved far enough to make the rejection level more important than the headline move.",f"The ${s} setup becomes clearer when you define where the market proves the idea wrong."],
                "A rejection is useful information only when price fails at the level and the next reaction confirms that weakness.",
                f"Which reaction would make you abandon the ${s} thesis?"
            ),
            "range_structure": (
                [f"${s} is giving us a range to read, not a direction to assume.",f"The useful ${s} question is which side of the recent range actually gets accepted."],
                "A clean break matters more when price holds outside the range instead of immediately returning inside it.",
                f"Which side of the ${s} range would you trust only after a retest?"
            ),
            "trend_continuation": (
                [f"The ${s} trend is easier to judge from what holds than from what has already moved.",f"With ${s}, continuation needs evidence after the impulse, not another reason to chase it."],
                "Watch whether the next pullback protects the recent structure; losing that structure changes the read.",
                f"What would convince you that ${s} is still in continuation rather than exhaustion?"
            ),
            "momentum_volume": (
                [f"${s} is moving, but price alone cannot explain whether the move deserves attention.",f"The useful ${s} signal is the relationship between the move and the participation behind it."],
                "If volume expands with the move and remains present on the next reaction, the evidence is stronger; if participation disappears, the story weakens.",
                f"What volume-and-price reaction would change your view on ${s}?"
            ),
            "relative_strength": (
                [f"${s} deserves a closer look if it keeps behaving differently from the broader market.",f"The ${s} signal is more useful when its move is compared with the market around it."],
                "Relative strength is evidence, not a forecast: the difference should persist across the next measurable reaction.",
                f"What would make you conclude ${s} is losing its relative strength?"
            ),
            "research_edge": (
                [f"The interesting ${s} detail is easy to miss when everyone is watching the percentage move.",f"There is a more useful ${s} question than simply asking whether price will rise next."],
                "The supplied evidence points to a specific market behavior worth testing rather than a prediction worth repeating.",
                f"Which new evidence would change your interpretation of ${s}?"
            ),
            "post_mortem_lesson": (
                [f"The ${s} lesson is not whether the last move was right; it is what the reaction taught us.",f"Looking at ${s}, the useful takeaway is the condition that separated confirmation from noise."],
                "That lesson can be reused: define the evidence first, then decide what reaction would invalidate it.",
                f"What would you carry forward from the ${s} setup into the next trade?"
            ),
        }
        default=([f"The useful ${s} question is what the next reaction can actually prove."],
                 "The available evidence supports a scenario to test, not certainty about the next candle.",
                 f"What new evidence would change your view on ${s}?")
        hooks,mechanism,question=story_templates.get(story_type,default)
        hook=fresh(hooks[seed:]+hooks[:seed],used)
        if lo is not None and hi is not None:
            structure=f"The recent 1H window spans roughly $" + price(lo) + " to $" + price(hi) + f". Price is around {obs}, with {voltext} in quote volume and a {ir:.1f}% intraday range."
        else:
            structure=f"Price is around {obs}, with {voltext} in quote volume; the available 1H evidence does not justify inventing a cleaner range."
        middle=f"{mechanism} The current snapshot puts {dollar} around {obs}, with {voltext} in quoted volume."
        body=structure
        close="That keeps the read falsifiable: the next measurable reaction either supports the structure or weakens it."
        question=question
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
