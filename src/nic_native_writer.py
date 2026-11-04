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
        # Publication records can store the rendered post and the editorial
        # question separately. Inspect both so a question cannot be recycled
        # merely because the logger omitted it from the post text field.
        candidates=(o.get("text"),o.get("post"),o.get("content"),o.get("discussion_question"),o.get("reader_question"))
        for candidate in candidates:
            for s in re.split(r"[.!?]+",str(candidate or "")):
                s=" ".join(re.sub(r"[^a-z0-9 ]","",s.lower()).split())
                if len(s.split())>=6:out.add(s)
    return out
def fresh(options,used):
    for x in options:
        if " ".join(re.sub(r"[^a-z0-9 ]","",x.lower()).split()) not in used:return x
    return options[0]
def fresh_question(options,used,seed):
    if not options:
        raise RuntimeError("no_fresh_reader_question_variant")
    offset=int(seed or 0)%len(options)
    ordered=list(options[offset:])+list(options[:offset])
    for option in ordered:
        normalized=" ".join(re.sub(r"[^a-z0-9 ]","",option.lower()).split())
        # Compare normalized whole questions and conservative containment.
        # Some historical loggers append punctuation or surrounding post copy;
        # exact-only matching allowed the same reader prompt to slip through.
        if normalized not in used and not any(
            len(seen) >= 24 and (normalized in seen or seen in normalized)
            for seen in used
        ):
            return option
    raise RuntimeError("no_fresh_reader_question_variant")
def question_options_for(story_type,s):
    variants={
        "breakout_retest":[
            f"What would confirm that ${s} is holding the retest?",
            f"Which reaction would tell you the ${s} breakout is failing?",
            f"How long would you want ${s} to hold above the old ceiling?",
            f"What price action would make you stop trusting the ${s} retest?",
        ],
        "rejection_invalidation":[
            f"Which rejection would make you abandon the ${s} thesis?",
            f"What evidence would show the ${s} failure level is being respected?",
            f"At what point would you stop treating this ${s} move as a valid setup?",
            f"What would make the ${s} rejection more convincing than the bounce?",
        ],
        "range_structure":[
            f"Which side of the ${s} range needs to hold before you trust the move?",
            f"What would prove that ${s} has escaped the range rather than faked out?",
            f"Would you wait for a retest before trusting a ${s} range break?",
            f"Which reaction would invalidate the current ${s} range read?",
        ],
        "trend_continuation":[
            f"What would tell you the ${s} trend is continuing rather than exhausting?",
            f"Which pullback level would change your view on ${s} continuation?",
            f"What follow-through would you need before trusting the ${s} trend?",
            f"What would make you downgrade the ${s} continuation thesis?",
        ],
        "momentum_volume":[
            f"What volume change would make you trust the next ${s} move?",
            f"Which price-and-volume reaction would invalidate the ${s} momentum read?",
            f"Would you trust ${s} without volume follow-through?",
            f"What would show that participation is fading in ${s}?",
        ],
        "relative_strength":[
            f"What would show that ${s} is losing its relative strength?",
            f"Which comparison would you use to test ${s} against the broader market?",
            f"How many sessions would you need before trusting ${s} outperformance?",
            f"What would make you treat the ${s} strength as temporary?",
        ],
        "research_edge":[
            f"Which new evidence would change your interpretation of ${s}?",
            f"What would you verify first before trusting the ${s} thesis?",
            f"Which competing explanation deserves the next check on ${s}?",
            f"What missing data would most change your read on ${s}?",
        ],
        "post_mortem_lesson":[
            f"What would you carry forward from the ${s} setup into the next trade?",
            f"Which part of the ${s} thesis would you test differently next time?",
            f"What evidence mattered most in judging the ${s} reaction?",
            f"Which lesson from ${s} would change your next decision?",
        ],
    }
    return variants.get(story_type,[
        f"What new evidence would change your view on ${s}?",
        f"Which part of the ${s} thesis would you verify first?",
        f"What would make you reconsider the current ${s} read?",
        f"Which next reaction matters most for ${s}?",
    ])
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
    strategy_runtime=ctx.get("creator_strategy_runtime") or {}
    strategy_id=str(ctx.get("iteration_strategy_id") or strategy_runtime.get("strategy_id") or "asset_specific_research_edge")
    period_learning=ctx.get("creator_period_learning") or {}
    tier_comparison=period_learning.get("reward_tier_cohort_comparison") or {}
    high_cohort=tier_comparison.get("high_reward_creator_periods") or {}
    lower_cohort=tier_comparison.get("lower_reward_creator_periods") or {}
    high_rates=(high_cohort.get("cohort") or {}).get("rates") or {}
    lower_rates=(lower_cohort.get("cohort") or {}).get("rates") or {}
    cohort_guidance=None
    cohort_comparison_ready=(
        tier_comparison.get("status")=="DESCRIPTIVE_COMPARISON_AVAILABLE"
        and int(high_cohort.get("cohort",{}).get("post_count") or 0)>=5
        and int(lower_cohort.get("cohort",{}).get("post_count") or 0)>=5
    )
    # Apply a cohort pattern only when it appears across a minimum of five posts
    # in both creator tiers. This is a presentation hypothesis, not post-level reward attribution.
    if cohort_comparison_ready and period_learning.get("learning_status") == "COHORT_HYPOTHESES_READY":
        high_sources=num(high_rates.get("has_source_link"))
        low_sources=num(lower_rates.get("has_source_link"))
        high_numbers=num(high_rates.get("has_numeric_evidence"))
        low_numbers=num(lower_rates.get("has_numeric_evidence"))
        high_questions=num(high_rates.get("has_question"))
        low_questions=num(lower_rates.get("has_question"))
        high_risk=num(high_rates.get("has_risk_or_invalidation_language"))
        low_risk=num(lower_rates.get("has_risk_or_invalidation_language"))
        # The current leaderboard study showed stronger question and risk/
        # invalidation signals in the higher-reward creator-period cohort.
        # These are descriptive format hypotheses, never post-level attribution.
        if high_questions >= low_questions + 0.15 and high_risk >= low_risk + 0.15:
            cohort_guidance="risk_aware_discussion"
        elif high_sources >= low_sources + 0.2 and high_numbers >= low_numbers + 0.2:
            cohort_guidance="evidence_led"
    s=sym(sel.get("symbol") or pub.get("symbol") or director.get("primary_symbol"))
    if not s:raise RuntimeError("NIC Native Writer: authoritative asset missing")
    cat=str(sel.get("category") or pub.get("category") or "market_opportunity").lower()
    timing_state=str(pub.get("timing_state") or "").upper()
    research_observation=pub.get("research_observation") if isinstance(pub.get("research_observation"),dict) else {}
    it=item_for(s,market);move=num(it.get("price_change_percent"));last=num(it.get("last_price"))
    vol=num(it.get("quote_volume_usdt") or it.get("quote_volume"));ir=num(it.get("intraday_range_percent"))
    lo,hi=rng(it);used=recent()
    setup=sel.get("trade_setup") if isinstance(sel.get("trade_setup"),dict) else {}
    side=str(setup.get("side") or setup.get("direction") or "").upper()
    trigger=setup.get("trigger",setup.get("entry_trigger"));inv=setup.get("invalidation",setup.get("sl"))
    tp1=setup.get("tp1");tp2=setup.get("tp2");dollar="$"+s
    obs="$"+price(last) if last else "the latest verified price"
    voltext=f"{vol/1e6:.1f}M USDT" if vol>=1e6 else (f"{vol/1e3:.0f}K USDT" if vol>=1e3 else "the available quote-volume snapshot")
    iteration_seed=ctx.get("iteration_seed")
    seed=(int(iteration_seed)%4) if iteration_seed is not None else int(hashlib.sha256((s+cat+str(director.get("narrative_engine"))).encode()).hexdigest()[:8],16)%4
    story_type=str(director.get("story_type") or sel.get("story_type") or director.get("narrative_engine") or strategy_runtime.get("selected_story_type") or "research_edge").strip().lower().replace(" ","_")
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
        question=fresh_question([
            f"What new evidence would make you change your view on {dollar}?",
            f"Which part of the supplied report would you verify first for {dollar}?",
            f"What market reaction would confirm the report is changing {dollar}?",
            f"What would show that the {dollar} reaction is fading rather than repricing?",
        ],used,seed)
    elif cat in {"capital_flow_long","capital_flow_short","flow","technical_setup","creator_signal_outcome","follow_up"} and side in {"LONG","SHORT"} and trigger is not None and inv is not None:
        trade_styles=[
            (f"${dollar}: the setup is conditional, not a call to chase.",f"The ${side} thesis only activates at ${trigger}. Until price reaches and holds that area, the signal is incomplete.",f"If it triggers, TP1 is ${tp1} and TP2 is ${tp2}. If ${inv} fails, the thesis is invalidated. Current price is ${obs}; the snapshot shows ${voltext} of quote volume.","The useful edge here is waiting for confirmation instead of paying for the move before the market proves it.",f"What price action at ${trigger} would make you trust the ${side} case for ${dollar}?"),
            (f"The interesting question on ${dollar} is not whether it is up or down; it is whether the market can prove this level.",f"For a ${side} scenario, ${trigger} is the decision point. A move near it is only preparation; acceptance beyond it is the confirmation condition.",f"The risk boundary is ${inv}. TP1/TP2 sit at ${tp1} and ${tp2}. Those levels describe the scenario, not a guaranteed path. Price is currently ${obs}.","That makes the invalidation more important than the target: it tells us when the thesis stops making sense.",f"If ${dollar} rejects ${trigger}, what would that tell you about this ${side} thesis?"),
            (f"I would not chase ${dollar} here. I would wait for the market to answer one specific question.",f"Can price establish the ${side} setup through ${trigger}? If not, there is no reason to force the signal.",f"The predefined failure point is ${inv}; the scenario targets are ${tp1} and ${tp2}. The current snapshot has price near ${obs} with ${voltext} in quote volume.","Waiting is part of the setup. A missed trade is cheaper than inventing confirmation.",f"How much follow-through would you need after ${trigger} before treating this as a valid ${side} setup?"),
            (f"${dollar} has a clean conditional setup, but the condition comes first.",f"The evidence is actionable only if ${trigger} is reached and the ${side.lower()} case holds there.",f"Invalidation sits at ${inv}; TP1 is ${tp1} and TP2 is ${tp2}. Current price is ${obs}, so the distance to the decision point still matters.","If the trigger never confirms, the correct outcome is no trade — not a rewritten signal.",f"What would make you abandon the ${dollar} setup before it reaches the first target?")
        ]
        hook,body,middle,close,_style_question=trade_styles[seed % len(trade_styles)]
        question=fresh_question([style[4] for style in trade_styles],used,seed)
    elif cat in {"research_insight", "market_mechanism", "data_surprise"} and timing_state == "EXHAUSTED":
        # An exhausted move may still support an explanatory research post, but
        # it must never be framed as a fresh setup or turned into entry levels.
        move_text=f"{move:+.1f}% in 24 hours" if move else "sharply over the measured period"
        range_text=f" and a {ir:.1f}% intraday range" if ir else ""
        hook="$"+s+f" has already moved {move_text}; the evidence gap now matters more than the headline."
        body=f"The snapshot shows price near {obs}, {voltext} in quote volume{range_text}. Those figures describe volatility and participation, not a confirmed catalyst."
        missing=research_observation.get("missing_evidence") if isinstance(research_observation.get("missing_evidence"),list) else []
        missing_map={"market_cap":"market cap","fdv":"FDV","circulating_supply":"circulating supply","product_adoption":"adoption","revenue_or_fees":"fees/revenue","holder_concentration":"holder concentration","unlocks":"unlock schedules","security_audits":"security checks","external_news_corroboration":"external corroboration"}
        gaps=[missing_map.get(str(x),str(x).replace("_"," ")) for x in missing]
        gap_text=", ".join(gaps[:6]) if gaps else "fundamental and independent-source corroboration"
        news_count=research_observation.get("news_count")
        official_count=research_observation.get("official_evidence_count")
        corroboration="No independent news corroboration is recorded. " if news_count == 0 and official_count == 0 else "Independent corroboration is not yet established in this research record. "
        middle=f"No independent catalyst is confirmed; {gap_text} remain unverified. Demand, short covering and thin liquidity remain competing explanations."
        close="Trader test: if price reverses as volume fades, the demand thesis weakens; follow-through needs independent catalyst evidence."
        question=fresh_question([
            "Which missing data would you verify first for $"+s+"?",
            "What independent source would most change your read on $"+s+"?",
            "Which competing explanation should be tested first for $"+s+"?",
            "What evidence would make you downgrade the $"+s+" thesis?",
        ],used,seed)
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
        hooks,mechanism,_template_question=story_templates.get(story_type,default)
        question=fresh_question(question_options_for(story_type,s),used,seed)
        hook=fresh(hooks[seed:]+hooks[:seed],used)
        if lo is not None and hi is not None:
            structure=f"The recent 1H window spans roughly $" + price(lo) + " to $" + price(hi) + f". Price is around {obs}, with {voltext} in quote volume and a {ir:.1f}% intraday range."
        else:
            structure=f"Price is around {obs}, with {voltext} in quote volume; the available 1H evidence does not justify inventing a cleaner range."
        middle=f"{mechanism} The current snapshot puts {dollar} around {obs}, with {voltext} in quoted volume."
        body=structure
        close="That keeps the read falsifiable: the next measurable reaction either supports the structure or weakens it."
        question=question
    # Make the four bounded iterations materially different in their evidence
    # angle, not merely different in paragraph order. This branch is intentionally
    # limited to research-led stories; conditional setup levels and verified news
    # facts above remain untouched.
    if cat in {"research_insight", "market_mechanism", "data_surprise"}:
        price_fact = f"price near {obs}" if last else "no verified last price in the current packet"
        move_fact = f"a {move:+.1f}% 24-hour move" if move else "no verified 24-hour percentage move"
        volume_fact = f"{voltext} in quote volume" if vol else "no usable quote-volume figure"
        if strategy_id == "asset_specific_research_edge":
            middle_options = [
                f"The asset-specific evidence is {price_fact}; that is the observation this ${s} thesis must explain.",
                f"For ${s}, the central research question is whether {price_fact} is supported by a separate catalyst.",
            ]
            close_options = [
                f"This remains a ${s}-specific hypothesis; new evidence about this asset should change the read, not a recycled market narrative.",
                f"The conclusion should stay limited to ${s}: if fresh asset-level evidence disagrees, the explanation needs to change.",
            ]
        elif strategy_id == "evidence_led_research":
            middle_options = [
                f"The measurable snapshot records {move_fact}, {price_fact}, and {volume_fact}; these are observations, not a causal explanation.",
                f"Evidence first: {price_fact}, {move_fact}, and {volume_fact}. The figures describe the snapshot without proving why the move occurred.",
            ]
            close_options = [
                "Those measurements establish what the snapshot contains, not what caused it; an independent source or later observation is needed to test the explanation.",
                "Do not turn correlation into a catalyst claim: the next independent observation must support the mechanism before the conclusion gets stronger.",
            ]
        elif strategy_id == "structure_and_confirmation":
            if lo is not None and hi is not None:
                structure_fact = f"The observed 1H range is ${price(lo)} to ${price(hi)}, with {price_fact}."
            else:
                structure_fact = f"A reliable 1H high-low range is not present in this packet; the only safe reference is {price_fact}."
            middle_options = [
                structure_fact + " The next reaction should be judged against that observed boundary.",
                structure_fact + " A single print does not establish acceptance beyond the range.",
            ]
            close_options = [
                "A move beyond an observed boundary matters only if price can hold there; a quick return inside weakens the interpretation.",
                "Treat the range as context, not a prediction: acceptance and a retest would add evidence, while rejection would weaken the thesis.",
            ]
        elif strategy_id == "participation_and_relative_strength":
            middle_options = [
                f"The participation record contains {volume_fact} alongside {move_fact}; without a comparable baseline, unusual accumulation is not established.",
                f"The available participation evidence is {volume_fact}. It can be described, but not called expanding or unusually strong without a baseline.",
            ]
            close_options = [
                "Volume is an observation, not proof of buyer strength; compare a later snapshot before calling participation persistent.",
                "If the next price move lacks supporting participation evidence, the strength narrative should remain unproven.",
            ]
        else:
            middle_options = [middle]
            close_options = [close]
        middle = fresh(middle_options, used)
        close = fresh(close_options, used)
        # Preserve the explicit high-earner cohort hypothesis when it is present.
        # Strategy diversity must not silently erase the learned risk-aware
        # discussion cue that the existing creator-period regression protects.
        if cohort_guidance == "risk_aware_discussion":
            close = (
                "Trader test: if price reverses as volume fades, the demand thesis "
                "weakens; follow-through needs independent catalyst evidence."
            )

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
    # Choose the presentation order from the idea's strategy, not one universal template.
    evidence_block=body if "body" in locals() else structure
    layouts={
        "catalyst_context_and_counterpoint": [hook, middle, evidence_block, close],
        "evidence_led_research": [evidence_block, hook, middle, close],
        "structure_and_confirmation": [hook, evidence_block, close, middle],
        "participation_and_relative_strength": [middle, hook, evidence_block, close],
        "asset_specific_research_edge": [hook, evidence_block, middle, close],
    }
    parts=layouts.get(strategy_id, [hook, evidence_block, middle, close])
    # Compact research observations can lead with evidence instead of forcing every
    # post into the same five-part sequence.
    if strategy_id == "evidence_led_research" and seed % 2 == 0:
        parts=[evidence_block, hook, middle]
    cohort_learning_applied=False
    if cohort_guidance=="evidence_led" and strategy_id not in {"catalyst_context_and_counterpoint"}:
        parts=[evidence_block,hook,middle,close]
        cohort_learning_applied=True
    elif cohort_guidance=="risk_aware_discussion":
        # Convert the observed cohort pattern into a useful, asset-specific test.
        # Do not copy creator wording or imply that the cohort reward was earned
        # by any particular post.
        if not (timing_state == "EXHAUSTED" and cat in {"research_insight", "market_mechanism", "data_surprise"}):
            close=("For traders, define the failure condition before acting: if price loses the "
                   "observed structure while participation fades, the thesis weakens; reassess "
                   "only when fresh evidence supports it.")
        # Keep the learned reader-payoff sentence attached to the analysis block:
        # the compacting routine may otherwise drop the final block on longer posts.
        parts=[hook,evidence_block,middle + " " + close]
        cohort_learning_applied=True
    # Exactly one genuine reader question belongs at the end. Any rhetorical
    # question mark inside a hook/body is converted to sentence punctuation.
    parts=[re.sub(r"\?+", ".", str(part)).strip() for part in parts]
    question=str(question or "").strip().rstrip(" ?.")+"?"
    post=compact_post(parts,question)
    contract_checks = {
        "character_count": len(post),
        "minimum_characters": 280,
        "maximum_characters": 700,
        "question_count": post.count("?"),
        "required_question_count": 1,
        "cashtag_present": dollar.lower() in post.lower(),
    }
    contract_failures = []
    if not 280 <= len(post) <= 700:
        contract_failures.append("length_out_of_bounds")
    if post.count("?") != 1:
        contract_failures.append("must_have_exactly_one_reader_question")
    if dollar.lower() not in post.lower():
        contract_failures.append("missing_selected_asset_cashtag")
    if contract_failures:
        detail = {"status": "LOCAL_CONTRACT_REJECTED", "failures": contract_failures,
                  "checks": contract_checks, "strategy": strategy_id, "story_type": story_type}
        raise RuntimeError("NIC Native Writer local contract rejected: " + json.dumps(detail, sort_keys=True))
    return {"research":{"summary":f"NIC verified {dollar} using the frozen opportunity and supplied market evidence.","strongest_signal":s,"opportunity_score":num(sel.get("adjusted_score") or sel.get("raw_score") or 0),"source_mode":"NIC_NATIVE_EVIDENCE_SYNTHESIS"},"critique":{"summary":"Native NIC review bounds claims by supplied evidence and keeps uncertainty explicit.","alternative_hypothesis":"The observed move may be temporary rather than structural.","disconfirming_test":"A materially different next reaction or failed evidence condition weakens the thesis."},"draft":{"post":post,"text":post,"hook":hook,"discussion_question":question,"quality_score":84,"editorial_style":"NIC_NATIVE_WRITER","generation_mode":"NIC_NATIVE","symbol":s,"content_category":cat,"publication_status":"DRAFT_ONLY_NOT_PUBLISHED"},"visual_plan":{"type":"candlestick_chart" if cat not in {"crypto_meme","community","commentary","education"} else "none","use_visual":bool(it.get("candles_1h")),"purpose":"Show only the frozen asset and supplied evidence."},"native_writer":{"version":"1.1","provider":"NIC","external_text_model":False,"evidence_bound":True,"creator_period_learning_status":period_learning.get("learning_status","NOT_AVAILABLE"),"creator_period_learning_applied":cohort_learning_applied,"creator_period_learning_rule":cohort_guidance if cohort_learning_applied else None,"creator_period_reward_granularity":"creator_period_only","generated_at":datetime.now(timezone.utc).isoformat()}}
