import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATUS = Path("data/live/creator_status.json")
USAGE = Path("analytics/ai_usage.json")
DAILY_LIMIT = int(os.getenv("GEMINI_DAILY_BUDGET", "20"))


def load(path, default):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default


def save_status(status, reason, **extra):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({"updated_at": datetime.now(timezone.utc).isoformat(), "status": status, "reason": reason, **extra}, indent=2), encoding="utf-8")


def run_creator(local_fallback=False):
    if local_fallback: os.environ["LOCAL_FALLBACK"] = "true"
    import multi_agent_creator
    multi_agent_creator.main()


def is_transient_gemini_error(message):
    text = message.lower()
    return any(token in text for token in ("429", "ratelimiterror", "quota", "too_many_requests", "503", "unavailable", "high demand", "temporarily unavailable", "deadline exceeded", "service unavailable"))


def main():
    today = datetime.now(timezone.utc).date().isoformat()
    usage = load(USAGE, {"date": today, "requests": 0})
    if usage.get("date") != today: usage = {"date": today, "requests": 0}
    requests = int(usage.get("requests", 0))

    if requests >= DAILY_LIMIT:
        print(json.dumps({"status": "AI_BUDGET_EXHAUSTED", "requests": requests, "daily_limit": DAILY_LIMIT, "action": "LOCAL_FALLBACK"}, indent=2))
        try:
            run_creator(local_fallback=True)
            save_status("AI_SUCCESS", "Gemini budget exhausted; used quota-safe deterministic creator", requests=requests, daily_limit=DAILY_LIMIT, generation_mode="LOCAL_FALLBACK")
            return 0
        except Exception as exc:
            save_status("AI_FAILED", "Both Gemini and local fallback failed; publication skipped", error=str(exc), requests=requests, daily_limit=DAILY_LIMIT)
            raise

    usage["requests"] = requests + 1
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(usage, indent=2), encoding="utf-8")

    try:
        run_creator(local_fallback=False)
    except Exception as exc:
        message = str(exc)
        # 429/503 and similar provider outages are transient. Never spend a second
        # Gemini request trying to recover; switch immediately to the local creator.
        if is_transient_gemini_error(message):
            print("Transient Gemini provider error detected; switching to local creator without another Gemini request.")
            try:
                run_creator(local_fallback=True)
                save_status("AI_SUCCESS", "Gemini transient failure; used local quota-safe creator", error=message, requests=usage["requests"], daily_limit=DAILY_LIMIT, generation_mode="LOCAL_FALLBACK")
                return 0
            except Exception as fallback_exc:
                save_status("AI_FAILED", "Gemini transient failure and local fallback failed", error=str(fallback_exc), original_error=message, requests=usage["requests"], daily_limit=DAILY_LIMIT)
                raise
        save_status("AI_FAILED", "Creator failed; publication must be skipped", error=message, requests=usage["requests"], daily_limit=DAILY_LIMIT)
        raise

    save_status("AI_SUCCESS", "Fresh Gemini draft generated", requests=usage["requests"], daily_limit=DAILY_LIMIT, generation_mode="GEMINI")
    return 0


if __name__ == "__main__": raise SystemExit(main())
