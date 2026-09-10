"""Creator 5.9 story-specific writing contract.

This stage supplies editorial structure only. It never invents market levels,
trade outcomes, or generic engagement bait.
"""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFLIGHT=ROOT/'data/live/editorial_preflight.json';FEEDBACK=ROOT/'data/intelligence/performance_feedback.json';FLOW=ROOT/'data/live/capital_flow_intelligence.json';OUT=ROOT/'data/live/script_director_4.json'
ARCHETYPES={'event_context_impact':'newsroom','macro_chain':'macro_analyst','momentum_question':'high_energy','contrarian_risk':'contrarian','volatility_then_test':'risk_analyst','data_vs_price':'data_driven','price_discovery':'discovery','level_confirmation':'technical_analyst','call_result_next_test':'accountability','thesis_update':'update','compare_tradeoffs':'debate','one_chart_one_lesson':'teacher','what_to_watch':'conversational','capital_flow_long':'flow_trader','capital_flow_short':'flow_trader','capital_flow':'flow_trader','research_radar':'research_analyst'}
HOOKS={
'newsroom':['The headline changed the story. The market still has to prove the impact.','The event is clear. The harder question is what it changes for price and positioning.','One verified event is colliding with a market that was already positioned.'],
'macro_analyst':['The macro signal matters only if crypto reprices around it.','A macro shift can matter long after the first headline fades.','The useful question is whether this changes the underlying risk regime.'],
'high_energy':['The move is obvious. The follow-through is the evidence.','A sharp move gets attention; the structure after it decides whether it matters.','The first candle tells the story. The next sequence tests it.'],
'contrarian':['The obvious trade has one problem: price still has to confirm it.','A crowded direction is not the same thing as a confirmed setup.','The strongest-looking move can still fail at the wrong level.'],
'risk_analyst':['Volatility tells us where attention is. Confirmation tells us whether it was justified.','The impulse is not the setup. The reaction after it is.','Risk gets clearer when the invalidation level is explicit.'],
'data_driven':['The useful signal is the relationship between the numbers, not one headline figure.','Price and participation are telling us two parts of the same story.','One data point is noise until it changes the interpretation of another.'],
'discovery':['New price discovery creates a test: continuation or rejection?','A new range is only useful once the market shows which side owns it.','The first reaction establishes the range; the next one explains it.'],
'technical_analyst':['There is a level where the chart can settle the argument.','The move has a decision point; that is where the setup becomes testable.','The important part of this chart is not the size of the candle. It is the level that must hold.'],
'accountability':['A thesis becomes valuable when we measure what actually happened next.','The original idea is now testable against the market’s response.','The chart has given us an answer. Now we can measure what it got right.'],
'update':['The market changed enough to force a fresh test of the thesis.','The old setup moved; one part of the thesis still needs proof.','The latest price action narrows the decision.'],
'debate':['Two readings fit the current data. The next evidence should separate them.','The better setup is the one with the clearer evidence, not the louder narrative.','These two assets are telling different stories despite sharing the same market.'],
'teacher':['One chart, one reusable rule: start with the decision point.','A simple chart habit can prevent a lot of bad entries.','This chart illustrates a rule worth keeping for the next setup.'],
'flow_trader':['The useful signal is not BTC alone. It is the divergence between regime, relative strength and participation.','Capital rotation becomes actionable only when the larger regime and the asset-specific evidence agree.','The setup is conditional: the flow has to survive the next confirmation test.'],
'research_analyst':['The opportunity is not the price move. It is the evidence gap around it.','A research anomaly matters only when the evidence behind it survives scrutiny.','The interesting part is what the available evidence says — and what is still missing.']}

def load(p):
    try:
        x=json.loads(p.read_text(encoding='utf-8'));return x if isinstance(x,dict) else {}
    except Exception:return {}
def clean(v):return str(v or '').upper().replace('USDT','').replace('$','').strip()
def choose_question(category,symbol,selected,flow):
    cat=str(category or '').lower();s=clean(symbol)
    setup=selected.get('trade_setup') or {}
    side=str(setup.get('side') or '').upper()
    if cat=='capital_flow_long' or cat=='capital_flow_short' or side in {'LONG','SHORT'}:
        trigger=setup.get('trigger');inv=setup.get('invalidation')
        if trigger is not None and inv is not None:return f'What is the first evidence on ${s} that would confirm or invalidate this {side or "conditional"} setup?'
        return f'What new flow or relative-strength evidence would make you reject ${s} next?'
    if cat in {'breaking_news','news_and_macro','news'}:
        title=str(selected.get('news_title') or '').strip()
        return f'Does the next measurable market response support the thesis that this event matters for ${s}?' if title else f'What evidence would make this ${s} catalyst durable rather than temporary?'
    if cat in {'top_gainers','top_losers','high_volatility'}:return f'Which level or reaction on ${s} would make you change the current read?'
    if cat=='technical_setup':return f'Which fresh ${s} level would you require before treating the setup as confirmed?'
    if cat=='watchlist':return f'Which missing evidence on ${s} would change your view of the opportunity?'
    if cat in {'volume_leaders','data_surprise'}:return f'Which relationship in ${s} data would you trust most to confirm this interpretation?'
    if cat=='new_listings':return f'What would ${s} need to hold after the first impulse before you would trust the move?'
    if cat=='creator_signal_outcome':return f'What should the next measurable test be for ${s} after this outcome?'
    return f'What specific evidence would change your view on ${s} next?'

def main():
    p=load(PREFLIGHT);d=p.get('content_director_4') or {};selected=p.get('selected_opportunity') or {};feedback=load(FEEDBACK);flow=load(FLOW)
    fmt=str(d.get('recommended_format') or '').upper();narrative=str(d.get('narrative_engine') or 'what_to_watch');sym=clean(selected.get('symbol') or (d.get('primary_story') or {}).get('symbol'))
    if not re.fullmatch(r'[A-Z0-9]{1,15}',sym):raise SystemExit('Script Director: authoritative selected symbol is missing or invalid')
    category=str(selected.get('category') or (d.get('primary_story') or {}).get('lane') or '').lower()
    if category in {'capital_flow_long','capital_flow_short'}:narrative=category;fmt='CAPITAL FLOW TRADE SETUP'
    elif category=='watchlist':narrative='research_radar';fmt='MARKET RADAR'
    style=ARCHETYPES.get(narrative,'conversational');learned=(feedback.get('learned_preferences') or {}).get('style') or {};learned_style=str(learned.get('prefer') or '').strip().lower()
    if learned_style and int(learned.get('sample') or 0)>=5 and learned_style in set(ARCHETYPES.values()):style=learned_style
    hooks=[h.replace('${symbol}',f'${sym}') for h in HOOKS.get(style,HOOKS['conversational'])]
    question=choose_question(category,sym,selected,flow)
    seed=hashlib.sha256((sym+fmt+narrative+style).encode()).hexdigest();q_hash=seed[:12]
    story=d.get('primary_story') or {};trade_setup=selected.get('trade_setup') or {}
    visual_symbols=story.get('chart_symbols') or [sym]
    directive={'version':'5.9','format':fmt,'primary_symbol':sym,'narrative_engine':narrative,'creator_archetype':style,'news_title':str(selected.get('news_title') or ''),'news_source':str(selected.get('news_source') or ''),'capital_flow_context':{'market_regime':(flow.get('market_rotation') or {}).get('market_regime'),'leaders':(flow.get('market_rotation') or {}).get('leaders',[]),'laggards':(flow.get('market_rotation') or {}).get('laggards',[]),'selected_trade_setup':trade_setup,'flow_confidence':selected.get('flow_confidence'),'relative_strength_to_btc':selected.get('relative_strength_to_btc'),'flow_proxy_score':selected.get('flow_proxy_score')},'performance_learning':{'preferred_style':learned_style or None,'style_sample':learned.get('sample',0),'preferred_hook_type':((feedback.get('learned_preferences') or {}).get('hook_type') or {}).get('prefer')},'hook_candidates':hooks,'question_candidates':[question],'question_id':q_hash,'writing_contract':['Write one finished Binance Square post, never an outline, briefing or instructions.','Make the selected opportunity the story. Do not switch to a different asset or unrelated fresh news.','The opening must contain a specific observation, tension, contradiction, relationship or decision — not generic “market check” language.','Within the first two lines explain why this exact story matters NOW.','Use a clear sequence: HOOK → NEW INFORMATION → INTERPRETATION → DECISION. Technical: HOOK → EVIDENCE → LEVEL/SCENARIO → QUESTION. News: EVENT → WHY IT MATTERS → MARKET RESPONSE → QUESTION. Flow: REGIME → RELATIVE STRENGTH → FLOW EVIDENCE → CONDITIONAL SETUP → INVALIDATION → QUESTION. Research: ANOMALY → EVIDENCE → MISSING DATA → WATCH CONDITION → QUESTION.','Every paragraph must add new information or a decision. Never paraphrase the headline as the body.','Use one or two strong supplied facts instead of a statistics dump.','Exactly one question, and it must be the supplied story-specific question at the end.','Never use generic questions such as “What do you think?”, “Thoughts?”, “Bullish, bearish, or wait?”, or “Chase, pullback, or wait?”.','For NEWS: use verified event/source only and never infer BTC relevance without supplied evidence.','For TECHNICAL: use only supplied OHLCV levels; do not invent support/resistance, targets or stops.','For CAPITAL FLOW: only use the supplied conditional LONG/SHORT setup. Include trigger, invalidation and TP1/TP2 only when provided; state that they are scenario levels, not guarantees. If side is WAIT, do not create a trade call.','For RESEARCH: missing evidence lowers confidence; use watchlist language rather than inventing a trade setup.','Never write “will pump”, “will dump”, “guaranteed”, or a guaranteed target.','No artificial engagement, no copied wording and no creator imitation.','Use mobile-first paragraphs, varied rhythm and no forced emoji.','Use exact supplied facts only.'],'retention_rules':['Do not start every post with ticker + percentage.','Do not reuse the same hook family in consecutive cycles when history is available.','Create a concrete reason to read the next paragraph.','When useful, create a return reason for a later outcome update.'],'anti_template_rules':['Reject “fresh check”, “quick market check”, “here is what matters”, “the next reaction matters”.','Reject generic CTA questions.','Reject a post whose only insight is that an asset went up/down.'],'story_inputs':{'primary_story':story,'authoritative_selection':selected,'news_title':str(selected.get('news_title') or ''),'news_source':str(selected.get('news_source') or '')},'visual_symbols':visual_symbols,'recommended_question':question}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(directive,indent=2,ensure_ascii=False));p['script_director_4']=directive;p['content_director_instruction']=f'Use authoritative asset ${sym}, format {fmt}, narrative {narrative}, and only these visual symbols: {visual_symbols}.';PREFLIGHT.write_text(json.dumps(p,indent=2,ensure_ascii=False));print(json.dumps({'status':'OK','version':'5.9','format':fmt,'symbol':sym,'narrative_engine':narrative,'creator_archetype':style,'question':question},indent=2,ensure_ascii=False))
if __name__=='__main__':main()