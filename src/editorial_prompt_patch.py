from pathlib import Path
import re

P = Path("src/multi_agent_creator.py")
text = P.read_text(encoding="utf-8")

# This patch must be resilient to earlier prompt edits. The previous version
# required an exact old WRITING string and crashed when the base prompt changed.
writing = (
    "WRITING: Write like a sharp human newsroom/trader, not a template generator. "
    "Normal target 450-900 characters; use more only when a real news story needs context. "
    "Structure: STOP-SCROLL HOOK -> VERIFIED EVENT/OBSERVATION -> WHY NOW -> EVIDENCE -> "
    "MARKET IMPACT -> WHAT THE CHART SAYS -> BULL/BEAR SCENARIOS -> NEXT WATCH -> ONE SPECIFIC QUESTION. "
    "If fresh news is selected, the first 1-2 lines MUST communicate the actual event and source context; "
    "never open with a generic price recap. Separate FACT from INTERPRETATION. Use varied sentence length, "
    "natural transitions, precise numbers, and mobile-friendly paragraphs. For technical setups, include "
    "current price/support/resistance and only data-supported target/invalidation. Levels are scenarios, "
    "never guarantees. Avoid repetitive emoji, canned phrases and generic 'what do you think?' questions."
)

style = (
    "STYLE ROTATION: Treat each post as a new story. Never reuse the same hook, cadence, paragraph order, "
    "emoji pattern, question, or opening phrase within the recent-post memory. Rotate newsroom BREAKING NEWS, "
    "macro reaction, news+chart, top mover, volume anomaly, liquidation, new listing, technical challenge, "
    "comparison, creator-call outcome, follow-up and education. The strongest story wins; do not force every "
    "cycle into a coin-price recap."
)

# Replace the current WRITING/STYLE lines regardless of which earlier version exists.
text, n_writing = re.subn(r"(?m)^WRITING:.*$", writing, text, count=1)
text, n_style = re.subn(r"(?m)^STYLE ROTATION:.*$", style, text, count=1)

if n_writing == 0:
    raise RuntimeError("Could not locate WRITING rule in multi_agent_creator.py")
if n_style == 0:
    raise RuntimeError("Could not locate STYLE ROTATION rule in multi_agent_creator.py")

rules = """
NEWSROOM WRITING: When selected_opportunity contains news_title/news_source, treat it as a NEWS STORY. Lead with the actual verified event, naturally attribute the source, explain why it matters now, then connect it to market reaction. Do not use the canned opener 'The headline is only half the story' or any equivalent. Do not merely paraphrase the headline; add verified context and interpretation. For macro stories such as gold/silver, explain the macro driver and compare relevant assets when evidence supports it.

VISUAL STORYBOARD: The attached image must be useful, not decorative. For a news/comparison story with two relevant assets, request a two-panel official TradingView image with one clean chart per asset. For gold/silver use OANDA:XAUUSD and OANDA:XAGUSD. For crypto use the exact relevant Binance symbols. No custom panels, maps, technical boxes or overlays may cover candles. Never fabricate a chart.

ARTICLE-STYLE POST: When the publication mode is article, write like a compact news article in the Square feed: strong headline-like first line, short paragraphs, evidence, interpretation, market implications, scenarios and one specific question. Do not compress a real breaking event into a two-line price recap.

FACT DISCIPLINE: Never invent sources, quotes, numbers, prices, volume, targets, creator calls or outcomes. If a source is only a discovery lead, do not present unverified claims as fact. Never promise profit or guaranteed 10x/20x returns.
"""

if "NEWSROOM WRITING:" not in text:
    marker = "Return ONLY valid JSON with research, critique, draft and visual_plan fields."
    if marker not in text:
        raise RuntimeError("Editorial system prompt closing marker not found")
    text = text.replace(marker, rules + "\n" + marker, 1)

P.write_text(text, encoding="utf-8")
print({
    "status": "EDITORIAL_DIRECTOR_PATCH_APPLIED",
    "version": "4.2-newsroom-robust",
    "writing_replaced": bool(n_writing),
    "style_replaced": bool(n_style),
})
