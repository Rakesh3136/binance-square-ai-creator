import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATUS = Path("data/live/creator_status.json")
USAGE = Path("analytics/ai_usage.json")
DAILY_LIMIT = int(os.getenv("GEMINI_DAILY_BUDGET", "20"))


def load(path, default):
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def save_status(status, reason, **extra):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "reason": reason,
                **extra,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def run_creator(local_fallback=False):
    if local_fallback:
        os.environ["LOCAL_FALLBACK"] = "true"
    else:
        os.environ.pop("LOCAL_FALLBACK", None)
    import multi_agent_creator
    multi_agent_creator.main()


def main():
    today = datetime.now(timezone.utc).date().isoformat()
    usage = load(USAGE, {"date": today, "requests": 0})
    if usage.get("date") != today:
        usage = {"date": today, "requests": 0}
    requests = int(usage.get("requests", 0))

    # Production must not lose a post merely because Gemini is unavailable,
    # returns malformed JSON, the SDK changes, or another provider error occurs.
    # Spend at most one Gemini request, then use the verified-data local creator.
    if requests >= DAILY_LIMIT:
        print(
            json.dumps(
                {
                    "status": "AI_BUDGET_EXHAUSTED",
                    "requests": requests,
                    "daily_limit": DAILY_LIMIT,
                    "action": "LOCAL_FALLBACK",
                },
                indent=2,
            )
        )
        try:
            run_creator(local_fallback=True)
            save_status(
                "AI_SUCCESS",
                "Gemini daily budget exhausted; used quota-safe deterministic creator",
                requests=requests,
                daily_limit=DAILY_LIMIT,
                generation_mode="LOCAL_FALLBACK",
            )
            return 0
        except Exception as exc:
            save_status(
                "AI_FAILED",
                "Gemini budget exhausted and local fallback failed; publication skipped",
                error=str(exc),
                requests=requests,
                daily_limit=DAILY_LIMIT,
                generation_mode="LOCAL_FALLBACK",
            )
            raise

    usage["requests"] = requests + 1
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(usage, indent=2), encoding="utf-8")

    try:
        run_creator(local_fallback=False)
    except Exception as exc:
        message = str(exc)
        print(
            "Gemini creator failed; switching immediately to the local verified-data creator. "
            f"Original error: {message}"
        )
        try:
            run_creator(local_fallback=True)
            save_status(
                "AI_SUCCESS",
                "Gemini creator failed; used local quota-safe creator without another Gemini request",
                error=message,
                requests=usage["requests"],
                daily_limit=DAILY_LIMIT,
                generation_mode="LOCAL_FALLBACK",
            )
            return 0
        except Exception as fallback_exc:
            save_status(
                "AI_FAILED",
                "Gemini creator failed and local fallback failed; publication skipped",
                error=str(fallback_exc),
                original_error=message,
                requests=usage["requests"],
                daily_limit=DAILY_LIMIT,
                generation_mode="LOCAL_FALLBACK",
            )
            raise

    save_status(
        "AI_SUCCESS",
        "Fresh Gemini draft generated",
        requests=usage["requests"],
        daily_limit=DAILY_LIMIT,
        generation_mode="GEMINI",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
