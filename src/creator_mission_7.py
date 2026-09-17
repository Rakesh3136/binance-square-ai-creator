"""Creator 7.1 mission and economic decision engine.

Separates verified monetization from proxies and directs the newsroom toward
high-trust, differentiated content that can generate qualified reader intent.
"""
from __future__ import annotations
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RANKING=ROOT/'data/live/opportunity_ranking_6.json';CADENCE=ROOT/'data/live/autonomous_cadence_6.json';IDENTITY=ROOT/'data/live/creator_identity_6_6.json';FEEDBACK=ROOT/'data/intelligence/performance_feedback.json';GROWTH=ROOT/'data/intelligence/creator_growth_system.json';LOG=ROOT/'analytics/publication_log.jsonl';STATE=ROOT/'data/intelligence/creator_mission_7.json';OUT=ROOT/'data/live/creator_mission_7.json'
def load(path):
    try:
        v=json.loads(path.read_text(encoding='utf-8'));return v if isinstance(v,dict) else {}
    except Exception:return {}
def num(v):
    try:return float(v)
    except Exception:return 0.0
def recent_publications(limit=30):
    if not LOG.exists():return []
    rows=[]
    for line in LOG.read_text(encoding='utf-8').splitlines()[-300:]:
        try:r=json.loads(line)
        except Exception:continue
        if isinstance(r,dict) and r.get('status') in {'PUBLISHED_AUTONOMOUSLY','PUBLISHED_VERIFIED_BY_API_RESPONSE','VERIFIED_PUBLISHED'}:rows.append(r)
    return rows[-limit:]
def main():
    now=datetime.now(timezone.utc);ranking=load(RANKING);cadence=load(CADENCE);identity=load(IDENTITY);feedback=load(FEEDBACK);growth=load(GROWTH);previous=load(STATE);posts=recent_publications()
    selected=ranking.get('selected') or {};selected=selected if isinstance(selected,dict) else {};score=num(selected.get('ranker_score') or selected.get('identity_score') or selected.get('score'));category=str(selected.get('category') or selected.get('lane') or '').lower();symbol=str(selected.get('symbol') or '').upper();title=str(selected.get('news_title') or selected.get('title') or '').strip()
    old_start=str(previous.get('sprint',{}).get('started_at') or '')
    try:start=datetime.fromisoformat(old_start.replace('Z','+00:00'))
    except Exception:start=now
    if now-start>=timedelta(days=7):start=now;previous={}
    end=start+timedelta(days=7);verified_revenue=num(previous.get('verified_revenue_usdc'));verified_events=int(num(previous.get('verified_revenue_events')))
    total_views=sum(num(p.get('views')) for p in posts);total_likes=sum(num(p.get('likes')) for p in posts);total_comments=sum(num(p.get('comments')) for p in posts);total_shares=sum(num(p.get('shares')) for p in posts);follower_delta=sum(num(p.get('followers_gained')) for p in posts)
    history_categories=[str(p.get('category') or '').lower() for p in posts[-8:]];history_symbols=[str(p.get('symbol') or '').upper() for p in posts[-8:]];same_category=bool(category and history_categories.count(category)>=3);same_symbol=bool(symbol and history_symbols.count(symbol)>=3)
    quality_signal=num(feedback.get('overall_quality') or feedback.get('quality_score') or feedback.get('score'));growth_score=num(growth.get('growth_score') or growth.get('score'))
    if verified_revenue>0 or verified_events>0:primary_goal='increase_verified_monetization'
    elif category in {'capital_flow_long','capital_flow_short','watchlist','technical_setup','comparison','creator_signal_outcome','follow_up'} and score>=72:primary_goal='capture_high_intent_research_opportunity'
    elif title:primary_goal='turn_fresh_information_into_market_impact_analysis'
    else:primary_goal='run_a_differentiated_learning_experiment'
    if same_category or same_symbol:action='PIVOT';reason='recent output is concentrated; rotate to a different asset or research lane'
    elif score>=100:action='ACT_NOW';reason='high-information opportunity meets the quality floor'
    elif score>=78:action='ACT_IF_FRESH';reason='strong opportunity with sufficient evidence'
    elif score>=60:action='RESEARCH_MORE';reason='promising but evidence or differentiation is not strong enough yet'
    else:action='WAIT';reason='no sufficiently differentiated opportunity'
    monetization_design={'verified_revenue_usdc':verified_revenue,'verified_revenue_events':verified_events,'revenue_is_verified':verified_revenue>0 or verified_events>0,'qualified_reader_intent_is_target':True,'eligible_content_should_use_relevant_cashtag_or_trading_widget':True,'validated_visual_preferred_for_asset_analysis':True,'real_trade_widget_if_verified':True,'avoid_spam_or_duplicate_content':True,'do_not_claim_revenue_from_views_or_likes':True,'do_not_fabricate_reader_trades_or_personal_experience':True}
    experiments=['early_mover_research_radar','catalyst_to_market_impact','capital_flow_explainer','one_chart_one_decision','creator_call_outcome','deep_research_article','live_market_education','controlled_meme']
    used={str(p.get('format') or '') for p in posts[-12:]};next_experiment=next((x for x in experiments if x not in used),experiments[0])
    portfolio={'early_mover_research':0.35,'catalyst_market_impact':0.25,'outcome_accountability':0.15,'deep_research_articles':0.10,'market_education_chart_lessons':0.10,'memes_and_community':0.05}
    mission={'version':'7.1','generated_at':now.isoformat(),'mission':'build legitimate, durable Binance Square income by publishing original high-trust market research that earns qualified reader action and repeat readership','sprint':{'started_at':start.isoformat(),'ends_at':end.isoformat(),'days_remaining':max(0,(end-now).days)},'priority_order':['verified_monetization','reader_value_and_trust','differentiated_research','audience_growth','learning_rate','creative_variation'],'decision':{'action':action,'reason':reason,'primary_goal':primary_goal,'selected_score':score,'selected_category':category,'selected_symbol':symbol or None,'selected_story':title or None,'next_experiment':next_experiment},'economic_state':monetization_design,'content_portfolio_target':portfolio,'observed_proxies':{'recent_published_posts':len(posts),'recent_views_proxy':total_views,'recent_likes_proxy':total_likes,'recent_comments_proxy':total_comments,'recent_shares_proxy':total_shares,'recent_follower_delta_proxy':follower_delta,'quality_signal':quality_signal,'growth_signal':growth_score},'agency_rules':['prefer original why-now analysis over raw price movement','use fresh evidence and explicit confirmation/invalidation conditions','use relevant cashtags/widgets for attribution without clickbait','return to resolved calls and show what was learned','wait when evidence is weak','rotate assets and formats when repetitive','never invent revenue, trades, personal experience or market facts'],'human_safety_boundary':'strategic autonomy does not authorize manipulation, spam, fabricated evidence, financial transactions or guaranteed-return claims'}
    OUT.parent.mkdir(parents=True,exist_ok=True);STATE.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(mission,indent=2,ensure_ascii=False),encoding='utf-8');STATE.write_text(json.dumps(mission,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(mission,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
