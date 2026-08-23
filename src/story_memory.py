from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
MEMORY=ROOT/'data/intelligence/story_memory.json'


def load():
    try: return json.loads(MEMORY.read_text())
    except Exception: return {"version":1,"active_stories":[],"recent_opinions":[],"series":[]}


def save(data):
    MEMORY.parent.mkdir(parents=True, exist_ok=True)
    MEMORY.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def build_context(limit=6):
    d=load()
    stories=d.get('active_stories', [])[-limit:]
    opinions=d.get('recent_opinions', [])[-limit:]
    series=d.get('series', [])
    return {
        'active_stories': stories,
        'recent_opinions': opinions,
        'series': series,
        'rules': d.get('rules', [])
    }


def record_story(story):
    d=load(); story=dict(story)
    story.setdefault('recorded_at', datetime.now(timezone.utc).isoformat())
    d.setdefault('active_stories', []).append(story)
    d['active_stories']=d['active_stories'][-30:]
    save(d)


def record_opinion(opinion):
    d=load(); opinion=dict(opinion)
    opinion.setdefault('recorded_at', datetime.now(timezone.utc).isoformat())
    d.setdefault('recent_opinions', []).append(opinion)
    d['recent_opinions']=d['recent_opinions'][-30:]
    save(d)
