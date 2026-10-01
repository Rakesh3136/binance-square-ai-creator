import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import mechanism_value_rewriter as m

def test_compaction_does_not_mutate_iteration_list():
    body=('BTC moved 8%. This is context without a hard fact. '
          'The market is reacting. Another fact-free sentence. '
          'Watch the next move.')
    out, bridge, removed=m.compact_body_for_bridge(body,'$BTC','What matters next?')
    assert isinstance(out,str)
    assert isinstance(bridge,str)
    assert isinstance(removed,list)

def test_fact_tokens_survive_compaction():
    body='BTC moved 8%. Traders are watching the reaction. The market remains uncertain. More context here.'
    out, bridge, removed=m.compact_body_for_bridge(body,'$BTC','What matters next?')
    assert m.explicit_facts(out)==m.explicit_facts(body)
