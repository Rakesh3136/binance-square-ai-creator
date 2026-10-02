import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import nic_editorial_memory_gate_19 as gate

def test_recent_same_asset_is_blocked(monkeypatch):
    from datetime import datetime, timezone, timedelta
    now=datetime.now(timezone.utc)
    monkeypatch.setattr(gate, 'load', lambda p: {
        'data/live/editorial_preflight.json': {'selected_opportunity': {'symbol':'GTC'}},
        'data/live/publication_context.json': {'symbol':'GTC'},
        'data/live/nic_story_discovery.json': {'selected_lane':'market_setup','story_kind':'market_setup'},
        'data/live/nic_content_craft_9.json': {},
        'data/live/signal_first_routing.json': {},
    }.get(str(p), {}))
    monkeypatch.setattr(gate, 'rows', lambda: [{'status':'PUBLISHED_VERIFIED_BY_API_RESPONSE','symbol':'GTC','published_at':now.isoformat()}])
    assert gate.main() == 0
    result=json.loads(gate.RESULT.read_text())
    assert result['allow'] is False
    assert result['same_asset_posts_24h'] == 1

def test_new_event_can_reopen_asset(monkeypatch):
    from datetime import datetime, timezone
    now=datetime.now(timezone.utc)
    monkeypatch.setattr(gate, 'load', lambda p: {
        'data/live/editorial_preflight.json': {'selected_opportunity': {'symbol':'GTC'}},
        'data/live/publication_context.json': {'symbol':'GTC','catalyst':'new listing announcement'},
        'data/live/nic_story_discovery.json': {'selected_lane':'breaking_news','story_kind':'breaking_news','evidence':['new listing announcement']},
        'data/live/nic_content_craft_9.json': {},
        'data/live/signal_first_routing.json': {},
    }.get(str(p), {}))
    monkeypatch.setattr(gate, 'rows', lambda: [{'status':'PUBLISHED_VERIFIED_BY_API_RESPONSE','symbol':'GTC','published_at':now.isoformat()}])
    assert gate.main() == 0
    result=json.loads(gate.RESULT.read_text())
    assert result['allow'] is True
    assert result['new_event_exception'] is True

if __name__ == '__main__':
    test_recent_same_asset_is_blocked(lambda *a,**k:None)
