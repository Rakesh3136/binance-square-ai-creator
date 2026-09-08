"""Superhuman Creator Core 1.0.
Builds a decision brief that forces downstream generation to optimize for
reader value, evidence, originality, differentiation and learning rather than
mere publication volume. It does not publish or bypass existing safety gates.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LIVE=ROOT/'data/live'; INTEL=ROOT/'data/intelligence'

def load(path):
    try:
        x=json.loads(path.read_text(encoding='utf-8'))
        return x if isinstance(x,dict) else {}
    except Exception:return {}

def main():
    pre=load(LIVE/'editorial_preflight.json')
    audience=load(LIVE/'creator_22_0_audience_intelligence.json')
    hooks=load(LIVE/'creator_22_2_hook_format_intelligence.json')
    draft=load(LIVE/'creator_22_3_draft_intelligence.json')
    outcomes=load(INTEL/'performance_feedback.json')
    selected=pre.get('selected_opportunity') or {}
    story=pre.get('content_director_4',{}).get('primary_story') or {}
    score=max([float(selected.get(k) or 0) for k in ('selected_score','opportunity_score','adjusted_score','content_signal_score','news_score') if str(selected.get(k) or '').replace('.','',1).isdigit()] or [0])
    brief={
      'version':'1.0','generated_at':datetime.now(timezone.utc).isoformat(),
      'mission':'Maximize reader value and differentiated insight per publication, not publication volume.',
      'selected_story':selected,'primary_story':story,'opportunity_score':score,
      'audience_signals':audience,'hook_signals':hooks,'draft_signals':draft,
      'outcome_feedback':outcomes,
      'editorial_priority':['truth_and_evidence','reader_value','specificity','novelty','clear_why_now','original_angle','conversation_quality','mobile_readability','risk_discipline'],
      'generation_directives':[
        'Find the strongest information advantage in the supplied story; do not merely restate market data.',
        'Explain why this matters now and what changed, with concrete supplied evidence.',
        'Prefer a distinctive thesis, contrast, implication or useful framework over generic commentary.',
        'Write for a skeptical intelligent reader: every important claim needs supplied evidence or careful qualification.',
        'Create multiple genuinely different concepts before selecting one; optimize the selected concept rather than averaging them.',
        'Use a strong first sentence that earns the next sentence without fake urgency.',
        'Give the reader one reusable insight, decision framework, or interpretation they can take away.',
        'End with one precise low-friction question that naturally follows from the analysis.',
        'Never manufacture engagement, certainty, targets, catalysts, sources, events or outcomes.',
        'If the story cannot support exceptional content, recommend WAIT rather than filler.'
      ],
      'red_team_questions':[
        'Would an expert reader learn something here?',
        'Could this post be written about almost any coin? If yes, reject it.',
        'Is the hook supported by the evidence?',
        'Is there a real insight beyond the price move?',
        'Is the conclusion earned by the evidence?',
        'Does the post sound templated or AI-generated?',
        'Is the question genuinely connected to the thesis?',
        'Would removing any paragraph improve the post?'
      ],
      'minimum_publish_standard':{'editorial_quality':85,'evidence_density':80,'specificity':80,'originality':78,'reader_value':82,'genericity_tolerance':0},
      'publish_rule':'A technically valid post is still rejected when it is generic, obvious, repetitive, weakly evidenced or low-value.'
    }
    LIVE.mkdir(parents=True,exist_ok=True); INTEL.mkdir(parents=True,exist_ok=True)
    (LIVE/'superhuman_creator_core.json').write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8')
    (INTEL/'superhuman_creator_core_report.json').write_text(json.dumps(brief,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':'OK','version':'1.0','opportunity_score':score,'minimum_publish_standard':brief['minimum_publish_standard']},indent=2))
if __name__=='__main__':main()
