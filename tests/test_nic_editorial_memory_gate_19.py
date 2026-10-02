import json
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import content_portfolio_guard as guard

def run_case(monkeypatch, candidate, recent):
    data={str(guard.PREFLIGHT): {'selected_opportunity': candidate}, str(guard.DIRECTOR): {'ranked_stories':[candidate]}, str(guard.QUEUE): {'candidates':[]}}
    monkeypatch.setattr(guard,'load',lambda p: data.get(str(p),{}))
    monkeypatch.setattr(guard,'recent_publications',lambda: recent)
    guard.main()
    return json.loads(guard.OUT.read_text())

def test_recent_same_asset_is_blocked(monkeypatch):
    now=datetime.now(timezone.utc).isoformat()
    candidate={'symbol':'GTC','category':'market_setup','ranker_score':100}
    recent=[{'status':'PUBLISHED_VERIFIED_BY_API_RESPONSE','symbol':'GTC','category':'market_setup','published_at':now,'text':'GTC market setup'}]
    result=run_case(monkeypatch,candidate,recent)
    assert result['publish'] is False
    assert any('nic19_' in r for x in result['blocked_candidates'] for r in x['reasons'])

def test_material_new_event_can_reopen_asset(monkeypatch):
    now=datetime.now(timezone.utc).isoformat()
    candidate={'symbol':'GTC','category':'breaking_news','ranker_score':100,'news_title':'GTC new listing announcement'}
    recent=[{'status':'PUBLISHED_VERIFIED_BY_API_RESPONSE','symbol':'GTC','category':'market_setup','published_at':now,'text':'GTC market setup'}]
    result=run_case(monkeypatch,candidate,recent)
    assert result['publish'] is True
    assert result['selected']['symbol']=='GTC'

if __name__=='__main__':
    import pytest; pytest.main([__file__])
