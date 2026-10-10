import sys
from pathlib import Path
sys.path.insert(0,'src')
import nic22_opportunity_diversity_engine as n

def test_story_profiles_are_distinct():
    assert len(n.STORY_TYPES)==8
    assert len(set(n.CHART_PROFILES.values()))==8

def test_hard_block():
    assert n.ASSET_HARD_BLOCK_COUNT==2
    assert n.ASSET_COOLDOWN_HOURS>=48

def test_blocked_confirmation_removes_trade_candidates():
    candidates=[
        (90, {'category':'technical_setup','symbol':'KAIA'}),
        (70, {'category':'top_gainers','symbol':'MITO'}),
        (60, {'category':'research_edge','symbol':'BTC'}),
    ]
    kept, reason=n.apply_confirmation_policy(candidates, {'status':'BLOCKED','selected_opportunity':None})
    assert [c['symbol'] for _,c in kept] == ['BTC']
    assert reason == 'no_confirmed_trade_candidate; editorial_only'

def test_confirmed_symbol_is_authoritative():
    candidates=[
        (99, {'category':'technical_setup','symbol':'KAIAUSDT'}),
        (75, {'category':'technical_setup','symbol':'MITO'}),
    ]
    kept, reason=n.apply_confirmation_policy(candidates, {
        'status':'CONFIRMED','selected_opportunity':{'symbol':'MITO','confirmation_status':'CONFIRMED_EARLY_SETUP'}
    })
    assert [c['symbol'] for _,c in kept] == ['MITO']
    assert reason == 'confirmed_symbol_authoritative'

def test_no_confirmation_never_falls_back_to_trade_setup():
    candidates=[(99, {'category':'technical_setup','symbol':'KAIA'})]
    kept, reason=n.apply_confirmation_policy(candidates, {'status':'BLOCKED'})
    assert kept == []
    assert reason == 'no_confirmed_candidate; trade_publication_blocked'

def test_workflow_selection_artifact_contract():
    assert n.SELECTION_OUT.as_posix() == 'data/live/nic22_opportunity_selection.json'
    assert n.OUT.as_posix() == 'data/live/nic22_opportunity_diversity.json'

if __name__=='__main__':
    test_story_profiles_are_distinct()
    test_hard_block()
    test_blocked_confirmation_removes_trade_candidates()
    test_confirmed_symbol_is_authoritative()
    test_no_confirmation_never_falls_back_to_trade_setup()
    test_workflow_selection_artifact_contract()
    print('NIC 22.1 tests passed')
