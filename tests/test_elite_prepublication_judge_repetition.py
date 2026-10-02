import json
import os
import tempfile
from pathlib import Path
import src.elite_prepublication_judge as judge

def test_reusable_disclaimer_is_not_a_repetition_signal():
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'publication_log.jsonl'
        p.write_text(json.dumps({'text':'Alpha moves through resistance. Levels are chart-derived scenarios, not guarantees.'})+'\n',encoding='utf-8')
        old_log=judge.PUBLICATION_LOG
        try:
            judge.PUBLICATION_LOG=p
            draft='Alpha moves through resistance. Levels are chart-derived scenarios, not guarantees. What matters next is follow-through.'
            assert judge.recent_similarity(draft)==[]
        finally:
            judge.PUBLICATION_LOG=old_log

def test_meaningful_repeated_sentence_still_blocks():
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'publication_log.jsonl'
        repeated='Buyers need to hold the recent range before momentum can continue.'
        p.write_text(json.dumps({'text':repeated})+'\n',encoding='utf-8')
        old_log=judge.PUBLICATION_LOG
        try:
            judge.PUBLICATION_LOG=p
            assert repeated.lower() in judge.recent_similarity(repeated)
        finally:
            judge.PUBLICATION_LOG=old_log

print('Elite judge repetition regression tests passed')