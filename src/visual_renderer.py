import json
from pathlib import Path

import matplotlib.pyplot as plt

REPORT_DIR = Path("data/reports")
VISUAL_DIR = Path("data/visuals")
VISUAL_DIR.mkdir(parents=True, exist_ok=True)


def latest_report() -> Path:
    reports = sorted(REPORT_DIR.glob("*-multi-agent.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        raise RuntimeError("No multi-agent report found")
    return reports[0]


def main() -> None:
    report_path = latest_report()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    plan = report.get("visual_plan") or {}
    market = report.get("live_market_snapshot") or {}

    if not plan.get("use_visual") or plan.get("type") == "none":
        print(json.dumps({"status": "NO_VISUAL_REQUESTED", "report": str(report_path)}, indent=2))
        return

    signals = market.get("top_content_signals") or []
    if not signals:
        print(json.dumps({"status": "NO_MARKET_DATA_FOR_VISUAL", "report": str(report_path)}, indent=2))
        return

    chart_type = plan.get("type")
    title = plan.get("title") or "Market snapshot"
    output = VISUAL_DIR / (report_path.stem + ".png")

    if chart_type in {"market_bar_chart", "market_comparison"}:
        data = signals[:6]
        labels = [str(x.get("symbol", "?")) for x in data]
        values = [float(x.get("price_change_percent", 0)) for x in data]
        plt.figure(figsize=(12, 7))
        plt.bar(labels, values)
        plt.axhline(0, linewidth=1)
        plt.title(title)
        plt.ylabel("24h price change (%)")
        plt.xticks(rotation=35, ha="right")
        plt.tight_layout()
    elif chart_type == "market_range_chart":
        data = signals[:6]
        labels = [str(x.get("symbol", "?")) for x in data]
        lows = [float(x.get("last_price", 0)) - (float(x.get("intraday_range_percent", 0)) * float(x.get("last_price", 0)) / 200) for x in data]
        highs = [float(x.get("last_price", 0)) + (float(x.get("intraday_range_percent", 0)) * float(x.get("last_price", 0)) / 200) for x in data]
        centers = [float(x.get("last_price", 0)) for x in data]
        plt.figure(figsize=(12, 7))
        plt.vlines(range(len(labels)), lows, highs, linewidth=3)
        plt.scatter(range(len(labels)), centers)
        plt.xticks(range(len(labels)), labels, rotation=35, ha="right")
        plt.title(title)
        plt.ylabel("Price / approximate intraday range")
        plt.tight_layout()
    else:
        # Conservative fallback: create a plain text card when the requested chart
        # needs data that are not safely available in the market snapshot.
        plt.figure(figsize=(12, 7))
        plt.axis("off")
        text = plan.get("caption") or plan.get("purpose") or title
        plt.text(0.05, 0.88, title, fontsize=20, va="top", wrap=True)
        plt.text(0.05, 0.72, text, fontsize=13, va="top", wrap=True)
        plt.tight_layout()

    plt.savefig(output, dpi=160, bbox_inches="tight")
    plt.close()

    print(json.dumps({
        "status": "VISUAL_CREATED",
        "type": chart_type,
        "output": str(output),
        "caption": plan.get("caption", ""),
        "alt_text": plan.get("alt_text", ""),
    }, indent=2))


if __name__ == "__main__":
    main()
