"""Render a curated edition into Markdown.

The curate step returns a plain dict (parsed from the model's JSON); this turns it
into the dated Markdown file that lands in ``editions/`` and feeds every gateway.
Rendering is intentionally dumb and deterministic — all the editorial judgment
already happened upstream.
"""

from __future__ import annotations

from typing import Any

EDITIONS_DIR = "editions"


def edition_path(date: str) -> str:
    return f"{EDITIONS_DIR}/{date}.md"


def render_markdown(edition: dict[str, Any]) -> str:
    """Build the Markdown body for one edition dict.

    Expected shape::

        {
          "title": str, "date": "YYYY-MM-DD", "intro": str,
          "sections": [
            {"heading": str,
             "stories": [{"headline", "summary", "url", "source"}]}
          ]
        }
    """
    title = edition.get("title") or "briarPipe"
    date = edition.get("date") or ""
    lines: list[str] = [f"# {title}"]
    if date:
        lines.append(f"\n*{date}*")

    intro = (edition.get("intro") or "").strip()
    if intro:
        lines.append("")
        lines.append(intro)

    for section in edition.get("sections") or []:
        heading = (section.get("heading") or "").strip()
        stories = section.get("stories") or []
        if not heading and not stories:
            continue
        lines.append("")
        lines.append(f"## {heading}" if heading else "##")
        for story in stories:
            lines.append("")
            lines.append(_render_story(story))

    return "\n".join(lines).rstrip() + "\n"


def _render_story(story: dict[str, Any]) -> str:
    headline = (story.get("headline") or "Untitled").strip()
    url = (story.get("url") or "").strip()
    summary = (story.get("summary") or "").strip()
    source = (story.get("source") or "").strip()

    title_md = f"### [{headline}]({url})" if url else f"### {headline}"
    parts = [title_md]
    if summary:
        parts.append("")
        parts.append(summary)
    if source:
        parts.append("")
        parts.append(f"— *{source}*")
    return "\n".join(parts)
