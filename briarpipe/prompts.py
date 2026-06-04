"""Prompt construction for the curate and cultivate phases.

Kept separate from the pipeline so the wording can evolve without touching
orchestration, and so prompts can be inspected/tested directly.
"""

from __future__ import annotations

import json
from typing import Any

from .config import Config
from .sources import Item, Source

CURATE_SYSTEM = (
    "You are the editor of a personal newspaper. You work ONLY from the candidate "
    "stories provided — never invent stories or URLs, and never browse beyond what "
    "you are given. Select what matters most to the reader's interests, group it "
    "into the requested sections, and write tight, original summaries. Respond with "
    "JSON only."
)

CULTIVATE_SYSTEM = (
    "You maintain the source base for a personal newspaper. Suggest a SMALL number "
    "of high-quality, specific publication or blog URLs worth adding for the reader's "
    "interests (home pages or feeds, not search queries), and flag existing sources "
    "that look dead or off-topic for removal. Be conservative. Respond with JSON only."
)


def build_curate_prompt(
    config: Config, items: list[Item], state_md: str
) -> str:
    out = config.output
    candidates = [
        {"i": n, "title": it.title, "summary": _clip(it.summary, 400),
         "url": it.url, "source": it.source_url}
        for n, it in enumerate(items)
    ]
    spec = {
        "interests": config.interests,
        "topics": config.topics,
        "voice_and_style": config.style,
        "language": config.language,
        "edition_name": config.edition_name,
        "max_stories": out.max_stories,
        "sections": out.sections,
        "summary_length": out.summary_length,
    }
    return (
        "Compose today's edition from the candidate stories.\n\n"
        f"READER & FORMAT SPEC:\n{json.dumps(spec, ensure_ascii=False, indent=2)}\n\n"
        "WHAT YOU'VE ALREADY COVERED (avoid repeating; build on this so the reader "
        "learns progressively):\n"
        f"{state_md.strip() or '(nothing yet — this is the first edition)'}\n\n"
        f"CANDIDATE STORIES:\n{json.dumps(candidates, ensure_ascii=False)}\n\n"
        "Return JSON with this exact shape:\n"
        "{\n"
        '  "edition": {\n'
        '    "title": str, "intro": str,\n'
        '    "sections": [{"heading": str, "stories": [\n'
        '       {"headline": str, "summary": str, "url": str, "source": str}]}]\n'
        "  },\n"
        '  "state_digest": str  // a TERSE, compact replacement for STATE.md: what has\n'
        "                       // now been covered and where the ongoing threads stand,\n"
        "                       // so the next edition advances instead of repeating.\n"
        "}\n"
        "Write summaries in the reader's voice/style. Use only URLs from the candidates."
    )


def build_cultivate_prompt(config: Config, sources: list[Source]) -> str:
    current = [
        {"feed_url": s.feed_url, "title": s.title, "score": s.score, "tags": s.tags}
        for s in sources
    ]
    spec = {"interests": config.interests, "topics": config.topics}
    return (
        "Review and improve the source base for this reader.\n\n"
        f"READER:\n{json.dumps(spec, ensure_ascii=False, indent=2)}\n\n"
        f"CURRENT SOURCES:\n{json.dumps(current, ensure_ascii=False)}\n\n"
        "Return JSON with this exact shape:\n"
        "{\n"
        '  "add": [str, ...],   // a FEW new site/blog/feed URLs worth adding\n'
        '  "drop": [str, ...]   // feed_url values from CURRENT SOURCES to remove\n'
        "}\n"
        "Prefer specific, durable publications over aggregators. Keep 'add' short."
    )


def parse_json_response(text: str) -> dict[str, Any]:
    """Extract a JSON object from a model response, tolerating code fences/prose."""
    if not text:
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
