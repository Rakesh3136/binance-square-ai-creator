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

def test_workflow_selection_artifact_contract():
    assert n.SELECTION_OUT.as_posix() == 'data/live/nic22_opportunity_selection.json'
    assert n.OUT.as_posix() == 'data/live/nic22_opportunity_diversity.json'

if __name__=='__main__':
    test_story_profiles_are_distinct()
    test_hard_block()
    test_workflow_selection_artifact_contract()
    print('NIC 22.1 tests passed')
