"""Plan a diversified Square content portfolio instead of repeating one coin/style."""
from __future__ import annotations
from collections import Counter

LANES={
 'breaking_news':{'goal':'fast verified reaction','formats':['NEWS_REACTION','CHOICE']},
 'top_gainers':{'goal':'discoverability around strong movers','formats':['TOP_MOVERS','BREAKOUT_OR_FAKEOUT']},
 'top_losers':{'goal':'contrarian conversation','formats':['LIQUIDATION_STORY','CHOICE']},
 'volume_anomalies':{'goal':'data curiosity','formats':['DATA_SURPRISE','CHART_CHALLENGE']},
 'new_listings':{'goal':'discovery and education','formats':['DATA_SURPRISE','COIN_VS_COIN']},
 'technical_setups':{'goal':'chart-led discussion','formats':['CHART_CHALLENGE','BREAKOUT_OR_FAKEOUT']},
 'macro_crypto':{'goal':'connect macro/news to crypto','formats':['NEWS_REACTION','CHOICE']},
 'education':{'goal':'evergreen follower value','formats':['DATA_SURPRISE','CHOICE']},
 'comparisons':{'goal':'easy A/B interaction','formats':['COIN_VS_COIN']},
}

def choose_lane(recent_posts:list[dict], fresh_news:int=0)->dict:
    counts=Counter(str(x.get('content_category') or x.get('category') or '').lower() for x in recent_posts)
    # Fresh breaking news gets priority, otherwise favor the least-used lane.
    if fresh_news:
        return {'lane':'breaking_news',**LANES['breaking_news'],'reason':'fresh_verified_news'}
    lane=min(LANES,key=lambda x:counts.get(x,0))
    return {'lane':lane,**LANES[lane],'reason':'portfolio_diversification','recent_count':counts.get(lane,0)}

if __name__=='__main__':
    print(choose_lane([],0))
