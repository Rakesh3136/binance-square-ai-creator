import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATUS = Path("data/live/creator_status.json")
USAGE = Path("analytics/ai_usage.json")
# Keep this aligned with the currently observed Gemini free-tier request ceiling.
# The workflow can lower it via GEMINI_DAILY_BUDGET without changing code.
DAILY_LIMIT = int(os.getenv("GEMINI_DAILY_BUDGET", "20"))


def load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_status(status, reason, **extra):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reason": reason,
        **extra,
    }, indent=2), encoding="utf-8")


def main():
    today = datetime.now(timezone.utc).date().isoformat()
    usage = load(USAGE, {"date": today, "requests": 0})
    if usage.get("date") != today:
        usage = {"date": today, "requests": 0}

    if int(usage.get("requests", 0)) >= DAILY_LIMIT:
        save_status("AI_BUDGET_EXHAUSTED", "Daily safety budget reached", requests=usage["requests"], daily_limit=DAILY_LIMIT)
        print(json.dumps({"status": "AI_BUDGET_EXHAUSTED", "requests": usage["requests"], "daily_limit": DAILY_LIMIT}, indent=2))
        return 0

    # Count the attempt before calling Gemini so repeated failures cannot burn
    # an unlimited number of requests in a workflow loop.
    usage["requests"] = int(usage.get("requests", 0)) + 1
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(usage, indent=2), encoding="utf-8")

    try:
        import multi_agent_creator
        multi_agent_creator.main()
    except Exception as exc:
        message = str(exc)
        if "429" in message or "RateLimitError" in message or "quota" in message.lower():
            save_status("AI_QUOTA_EXHAUSTED", "Gemini quota/rate limit; no draft is publishable", error=message, requests=usage["requests"], daily_limit=DAILY_LIMIT)
            print(json.dumps({"status": "AI_QUOTA_EXHAUSTED", "error": message}, indent=2))
            return 0
        save_status("AI_FAILED", "Creator failed; publication must be skipped", error=message)
        raise

    save_status("AI_SUCCESS", "Fresh Gemini draft generated", requests=usage["requests"], daily_limit=DAILY_LIMIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
