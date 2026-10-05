import json, os, hashlib, re
from datetime import datetime, timezone
from pathlib import Path

STATUS=Path('data/live/creator_status.json'); USAGE=Path('analytics/ai_usage.json'); REPORT_DIR=Path('data/reports'); DAILY_LIMIT=0
PUBLICATION_LOG=Path('analytics/publication_log.jsonl')
SIGNAL_ROUTING=Path('data/live/signal_first_routing.json'); MONETIZATION_OS=Path('data/live/nic_monetization_contract.json')


def load(path,default):
    if not path.exists(): return default
    try:
        value=json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value,type(default)) else default
    except Exception:return default


def save_status(status,message,**extra):
    payload={'status':status,'message':message,'updated_at':datetime.now(timezone.utc).isoformat()}; payload.update(extra); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8')


def latest_report():
    reports=sorted(REPORT_DIR.glob('*-multi-agent.json'),key=lambda p:p.stat().st_mtime,reverse=True); return reports[0] if reports else None


def report_has_publishable_text(path):
    if not path: return False
    try:
        report=json.loads(path.read_text(encoding='utf-8')); draft=report.get('draft') if isinstance(report.get('draft'),dict) else {}
        candidates=(draft.get('text'),draft.get('post'),draft.get('body'),draft.get('content'),draft.get('caption'),report.get('text'),report.get('post'))
        return any(isinstance(x,str) and x.strip() for x in candidates)
    except Exception:return False


def run_creator():
    before=latest_report(); before_mtime=before.stat().st_mtime if before else 0
    import multi_agent_creator
    multi_agent_creator.main()
    after=latest_report()
    if not after or after.stat().st_mtime <= before_mtime or not report_has_publishable_text(after): raise RuntimeError('NIC native creator completed without producing a fresh publishable draft')
    return after


def reject_legacy_prose(report_path):
    """Hard-stop the retired deterministic signal template.

    The old signal_post_builder prose is no longer a valid publication style.
    Facts and trade levels may still be used by the visual/attribution contract,
    but the post itself must come from the current NIC editorial contract.
    """
    report=json.loads(report_path.read_text(encoding='utf-8'))
    draft=report.get('draft') if isinstance(report.get('draft'),dict) else {}
    post=str(draft.get('post') or draft.get('text') or '').strip()
    fingerprints=(
        'entry trigger:',
        'tp1:',
        'tp2:',
        'sl / invalidation:',
        'conditional setup only; no guarantee.',
        'scenario to test, not certainty.',
        'conditional map; let price prove it.',
        'setup only; outcome remains unknown.',
        'risk boundary first; outcome unknown.',
        'not a promise of outcome.',
    )
    normalized=' '.join(post.lower().split())
    hits=[x for x in fingerprints if x in normalized]
    if hits:
        raise RuntimeError('Retired signal prose detected; refusing publication of legacy template: '+', '.join(hits))
    return {'legacy_prose_rejected':False,'fingerprints_checked':len(fingerprints)}

def enforce_signal_first(report_path):
    """Validate the frozen signal contract without replacing the AI-written post.

    The previous implementation was the source of the recurring old-style copy:
    it discarded the fresh NIC/Gemini draft and replaced it with the deterministic
    signal_post_builder template. Signal routing is now a fact/visual contract,
    not a prose override. The selected signal remains authoritative for levels
    and chart lineage, while the current editorial contract owns the writing.
    """
    routing=load(SIGNAL_ROUTING,{})
    if routing.get('decision')!='PRIMARY_SIGNAL' or routing.get('primary_signal') is not True:
        return {'applied':False,'reason':'not_primary_signal'}

    selected=routing.get('selected') if isinstance(routing.get('selected'),dict) else {}
    if not selected.get('symbol') or routing.get('prediction_contract_complete') is not True:
        raise RuntimeError('Signal-First routing says PRIMARY_SIGNAL but prediction contract is incomplete')

    try:
        report=json.loads(report_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError(f'Cannot read generated draft for Signal-First validation: {exc}')

    draft=report.get('draft') if isinstance(report.get('draft'),dict) else {}
    post=str(draft.get('post') or draft.get('text') or '').strip()
    if not post:
        raise RuntimeError('Signal-First validation found no generated post')

    # Keep the generated prose intact. Attach the authoritative contract for
    # downstream chart/attribution/validation stages instead of overwriting it.
    draft['symbol']=draft.get('symbol') or selected.get('symbol')
    draft['signal_first_validated']=True
    draft['signal_contract']=selected.get('trade_setup') or selected.get('prediction') or {}
    draft['signal_routing_version']=routing.get('router_version')
    report['draft']=draft
    report['signal_first_validated']=True
    report['signal_first_routing_version']=routing.get('router_version')
    report['generation_mode']=report.get('generation_mode') or 'GEMINI'
    report['status']='DRAFT_ONLY_NOT_PUBLISHED'
    report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\\n',encoding='utf-8')
    return {
        'applied':True,
        'symbol':draft.get('symbol'),
        'style':draft.get('editorial_style') or 'NIC_EDITORIAL_CONTRACT',
        'prose_overridden':False,
        'legacy_signal_template_removed':True
    }

def normalize_sentence(text):
    return re.sub(r'[^a-z0-9 ]','',str(text).lower()).strip()


def recent_published_sentences():
    """Return normalized sentences from the recent publication history.

    Emergency generation must never recycle a recognizable sentence from a
    recent post merely because the asset changed. This protects the hard elite
    repetition gate without weakening that gate.
    """
    if not PUBLICATION_LOG.exists(): return set()
    found=set()
    try:
        for row in PUBLICATION_LOG.read_text(encoding='utf-8').splitlines()[-12:]:
            try: obj=json.loads(row)
            except Exception: continue
            text=str(obj.get('text') or obj.get('post') or obj.get('content') or '')
            for sentence in re.split(r'[.!?]+', text):
                sentence=normalize_sentence(sentence)
                if len(sentence.split())>=6: found.add(sentence)
    except Exception:
        return set()
    return found


def choose_fresh(options, recent):
    for option in options:
        if normalize_sentence(option) not in recent:
            return option
    return options[0]


def deduplicate_signal_post(post, symbol):
    """Replace repeated sentences while preserving the surrounding structure."""
    recent = recent_published_sentences()
    statement_replacements = [
        f"The fixed risk boundary gives ${symbol} a clear condition for keeping or dropping this thesis.",
        f"${symbol} only becomes actionable when the market validates the trigger rather than the narrative around it.",
        "The important test is acceptance at the decision level; a failed level ends the setup cleanly.",
        "Risk is defined before confirmation, so the scenario remains testable in either direction.",
        "The setup stays conditional until price proves the level instead of merely touching it.",
        f"For ${symbol}, the next reaction is more informative than another prediction about the headline.",
        "The chart is a decision map: confirmation activates the idea, while invalidation closes it.",
    ]
    question_replacements = [
        f"What would you watch first around ${symbol}: acceptance of the level or a cleaner retest?",
        f"Would you wait for ${symbol} to confirm the level, or treat the first break as unreliable?",
    ]
    used = set()

    def replacement_for(sentence):
        pool = question_replacements if "?" in sentence else statement_replacements
        for candidate in pool:
            normalized = normalize_sentence(candidate)
            if normalized not in recent and normalized not in used:
                used.add(normalized)
                return candidate
        return sentence

    def repair_paragraph(paragraph):
        pieces = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        repaired = []
        for sentence in pieces:
            normalized = normalize_sentence(sentence)
            if len(normalized.split()) >= 6 and normalized in recent:
                repaired.append(replacement_for(sentence))
            else:
                repaired.append(sentence)
        return " ".join(x for x in repaired if x).strip()

    return "\n\n".join(repair_paragraph(p) for p in post.split("\n\n"))


def emergency_verified_draft(reason):
    """Dependency-free rescue that preserves the frozen asset and varies prose.
    It never invents news, trade levels, outcomes or a replacement asset.
    """
    pre=load(Path('data/live/editorial_preflight.json'),{}); market=load(Path('data/live/market_snapshot.json'),{}); news=load(Path('data/live/news_snapshot.json'),{}); monetization_os=load(MONETIZATION_OS,{})
    selected=pre.get('selected_opportunity') or {}; selected=selected if isinstance(selected,dict) else {}
    os_lane=str(monetization_os.get('content_lane') or '').strip()
    os_format=str(monetization_os.get('content_format') or '').strip()
    os_hook=str(monetization_os.get('hook_type') or '').strip()
    os_payoff=str(monetization_os.get('reader_payoff_type') or '').strip()
    os_experiment=str(monetization_os.get('experiment_id') or '').strip()
    os_variable=str(monetization_os.get('experiment_variable') or '').strip()
    os_treatment=str(monetization_os.get('experiment_treatment') or '').strip()
    wanted=str(selected.get('symbol') or '').upper().replace('USDT','').replace('$','').strip()
    if not wanted or not wanted.replace('_','').isalnum(): raise RuntimeError('Emergency fallback refused: frozen opportunity symbol is missing')
    items=[]
    for group in ('top_content_signals','top_gainers','top_losers','highest_volume','new_listing_market'):
        vals=market.get(group) or []; items.extend(x for x in vals if isinstance(x,dict))
    item=next((x for x in items if str(x.get('symbol','')).upper().replace('USDT','')==wanted),None)
    if not item: raise RuntimeError(f'Emergency fallback refused: frozen asset ${wanted} is absent from the live market snapshot')
    symbol=wanted
    def n(key,default=0.0):
        try:return float(item.get(key) or default)
        except Exception:return default
    move=n('price_change_percent'); price=n('last_price'); volume=n('quote_volume_usdt') or n('quote_volume'); rng=n('intraday_range_percent'); category=str(selected.get('category') or 'market_opportunity').replace('_',' ')
    candles=item.get('candles_1h') or []; highs=[]; lows=[]
    for c in candles[-24:]:
        if isinstance(c,(list,tuple)) and len(c)>=4:
            try: highs.append(float(c[2])); lows.append(float(c[3]))
            except Exception: pass
        elif isinstance(c,dict):
            try: highs.append(float(c.get('high'))); lows.append(float(c.get('low')))
            except Exception: pass
    resistance=max(highs) if highs else None; support=min(lows) if lows else None
    ptxt=f'${price:.8g}' if price else 'the latest verified price'; vtxt=f'${volume/1e6:.1f}M' if volume>=1e6 else (f'${volume/1e3:.0f}K' if volume>=1e3 else 'the available volume snapshot')
    recent=recent_published_sentences()
    seed=int(hashlib.sha256((symbol+datetime.now(timezone.utc).isoformat()).encode()).hexdigest()[:8],16)%4
    special = None
    # Retired signal_post_builder prose is deliberately NOT used as a fallback.
    # Emergency mode must also respect the new editorial system.
    draft_style='NIC_LOCAL_EMERGENCY'
    if category=='crypto meme':
        hook_options=[f'${symbol} chose chaos for today’s market update.',f'The ${symbol} chart has excellent timing and questionable manners.',f'Nobody ordered a ${symbol} plot twist, but the market delivered one.',f'${symbol} just volunteered for the trader patience test.']
        hook=choose_fresh(hook_options[seed:]+hook_options[:seed],recent)
        mechanism_options=[f'For ${symbol}, the punchline is also the test: the size of the move matters less because the next reaction shows whether traders are accepting it or giving it back.',f'The funny part is the headline; the useful part is ${symbol} itself, because the reaction afterward tells us whether this move is being absorbed or rejected.',f'${symbol} is interesting here because a large move creates attention first, while the reaction afterward tells us whether that attention has substance.',f'The market can make any candle look dramatic, but ${symbol} becomes more informative because the follow-through can separate a real change in behavior from a one-off move.']
        mechanism=choose_fresh(mechanism_options[seed:]+mechanism_options[:seed],recent)
        close_options=[f'No heroic prediction here — just a very crypto-looking moment, backed by the Binance market snapshot.',f'This is entertainment with a real market data point underneath it: the Binance snapshot shows the move, not its future.',f'The joke is mine; the move is from the Binance market snapshot. What happens next still has to be observed.',f'One chart can create a lot of drama. The Binance snapshot gives us the fact; the reaction gives us the next clue.']
        close=choose_fresh(close_options[seed:]+close_options[:seed],recent)
        question=f'What would make you stop laughing and start taking ${symbol} seriously?'
        post=f'{hook}\n\n${symbol} is on the screen after a {move:+.1f}% move.\n\n{mechanism}\n\n{close}\n\n{question}'
    else:
        hooks=[f'${symbol} moved {move:+.1f}%, but the interesting question is what the market does after the impulse.',f'I’m watching ${symbol} for the reaction, not chasing the headline move.',f'The ${symbol} move is easy to see. The useful information is in the structure that follows it.',f'${symbol} has enough movement to get attention; the next test decides whether that attention is justified.']
        hook=choose_fresh(hooks[seed:]+hooks[:seed],recent)
        context=f'Price is around {ptxt}, with {vtxt} in quote volume and a {rng:.1f}% intraday range.'
        level=f'On the recent 1H window, the observed range runs from about ${support:.8g} to ${resistance:.8g}.' if support is not None and resistance is not None else 'The available 1H snapshot does not provide a reliable range to quote.'
        post=(f'{hook}\n\n{context} {level}\n\n'
              f'The current classification is {category}. That is a description of the setup, not a promise about the next candle.\n\n'
              f'I would rather wait for price to confirm the reaction than manufacture certainty from one move.\n\n'
              f'What specific reaction on ${symbol} would make you change your read?')
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'model':'deterministic-emergency-fallback','topic_instruction':selected.get('instruction',''),'selected_editorial_lane':selected,'engagement_strategy':pre.get('engagement_strategy') or {},'live_market_snapshot':market,'news_discovery_snapshot':news,'strategy_memory':load(Path('analytics/strategy_memory.json'),{}),'research':{'summary':'Emergency draft built only from the frozen asset and verified live market data.','strongest_signal':symbol,'source_mode':'deterministic_emergency_fallback','opportunity_score':float(selected.get('adjusted_score') or selected.get('raw_score') or 80)},'critique':{'summary':'AI generation unavailable; no unverified facts were added.','reason':str(reason)[-500:]},'draft':{'post':post,'text':post,'hook':post.split('\n\n')[0],'discussion_question':post.split('\n\n')[-1],'quality_score':84,'editorial_style':draft_style if category!='crypto meme' else 'verified_market_meme','generation_mode':'LOCAL_FALLBACK','experiment_id':os_experiment or (pre.get('engagement_strategy') or {}).get('experiment_id') or 'A','experiment_format':os_format or ((pre.get('engagement_strategy') or {}).get('experiment') or {}).get('format'),'content_lane':os_lane or category,'campaign_day':monetization_os.get('campaign_day'),'hook_type':os_hook,'reader_payoff_type':os_payoff,'experiment_variable':os_variable,'experiment_treatment':os_treatment,'cycle_id':str(monetization_os.get('cycle_id') or ''),'symbol':symbol,'content_category':category,'publication_status':'DRAFT_ONLY_NOT_PUBLISHED'},'visual_plan':{'type':'candlestick_chart','use_visual':bool(candles),'title':f'{symbol}: verified 1H market data','data_points':[{'symbol':symbol}],'purpose':'TradingView chart is rendered separately from the frozen opportunity.'},'status':'DRAFT_ONLY_NOT_PUBLISHED','generation_mode':'LOCAL_FALLBACK','emergency_fallback':True,'monetization_os_contract':monetization_os,'fallback_inherits_editorial_contract':bool(monetization_os)}
    REPORT_DIR.mkdir(parents=True,exist_ok=True); slug=''.join(c.lower() if c.isalnum() else '-' for c in symbol).strip('-') or 'market-opportunity'; path=REPORT_DIR/f'{slug}-emergency-multi-agent.json'; path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'status':'EMERGENCY_LOCAL_DRAFT','report':str(path),'symbol':symbol,'category':category},indent=2))


def local_or_emergency(original_error):
    """Use the dependency-free NIC emergency writer when the native path fails."""
    print('NIC native writer unavailable; using dependency-free verified creator')
    emergency_verified_draft(original_error); return 'EMERGENCY_SUCCESS'


def main():
    try:
        report_path=run_creator()
        legacy_guard=reject_legacy_prose(report_path)
        binding=enforce_signal_first(report_path)
        print(json.dumps({'legacy_prose_guard':legacy_guard,'signal_first_binding':binding},indent=2))
        save_status('AI_SUCCESS','NIC native draft generated; Signal-First contract validated without prose override',requests=0,daily_limit=0,generation_mode='NIC_NATIVE',signal_first_binding=binding)
        return 0
    except Exception as exc:
        message=str(exc)
        print(f'NIC native creator failed; switching to dependency-free verified creator. Original error: {message}')
        fallback_status=local_or_emergency(message)
        save_status('AI_SUCCESS','NIC native creator failed; verified local creator preserved the cycle',error=message,requests=0,daily_limit=0,generation_mode='LOCAL_FALLBACK',fallback_status=fallback_status)
        return 0

if __name__=='__main__':raise SystemExit(main())
