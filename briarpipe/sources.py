"""The source base: discovery, persistence, and fetching.

A *source* is a feed briarPipe already trusts. The base is a small, durable list
that grows through deliberate cultivation — never through open-ended crawling.
Fetching candidate stories from known feeds is cheap and uses no model tokens;
only curation and cultivation spend the budget.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from typing import Any, Callable, Iterable
from urllib.parse import urljoin, urlparse

# Common locations to probe when a site advertises no feed via <link>.
COMMON_FEED_PATHS = (
    "/feed",
    "/feed/",
    "/feed.xml",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/index.xml",
)

_FEED_MIME_HINTS = ("rss", "atom", "xml")

# Injectable I/O so the parsing logic stays unit-testable offline.
Fetcher = Callable[[str], str]


@dataclass
class Source:
    """A trusted feed in the base."""

    url: str  # the site/page the feed belongs to
    feed_url: str  # the actual RSS/Atom URL
    title: str = ""
    added: str = ""  # ISO date the source entered the base
    last_used: str = ""  # ISO date it last contributed a story
    score: float = 1.0  # health/usefulness, nudged during cultivation
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Source":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class Item:
    """A candidate story pulled from a feed (pre-curation)."""

    title: str
    url: str
    summary: str = ""
    published: str = ""
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- persistence -------------------------------------------------------------


def sources_to_json(sources: Iterable[Source]) -> dict[str, Any]:
    return {"sources": [s.to_dict() for s in sources]}


def sources_from_json(data: dict[str, Any] | None) -> list[Source]:
    if not data:
        return []
    return [Source.from_dict(s) for s in data.get("sources", [])]


# --- discovery ---------------------------------------------------------------


class _FeedLinkParser(HTMLParser):
    """Collects <link rel="alternate" type="application/rss+xml"> hrefs."""

    def __init__(self) -> None:
        super().__init__()
        self.feeds: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        rel = a.get("rel", "").lower()
        typ = a.get("type", "").lower()
        href = a.get("href", "")
        if not href:
            return
        if "alternate" in rel and any(h in typ for h in _FEED_MIME_HINTS):
            self.feeds.append(href)


def parse_feed_links(html: str, base_url: str) -> list[str]:
    """Return absolute feed URLs advertised by ``<link>`` tags in ``html``."""
    parser = _FeedLinkParser()
    try:
        parser.feed(html)
    except Exception:  # malformed markup shouldn't crash discovery
        pass
    return _dedupe([urljoin(base_url, h) for h in parser.feeds])


def looks_like_feed(text: str) -> bool:
    """Cheap sniff: does this body look like RSS/Atom rather than a web page?"""
    head = text.lstrip()[:512].lower()
    return "<rss" in head or "<feed" in head or "<rdf" in head


def discover_feeds(
    url: str,
    fetch: Fetcher | None = None,
    probe_common: bool = True,
) -> list[str]:
    """Find feed URLs for a site: advertised ``<link>``s first, then common paths."""
    fetch = fetch or _default_fetch
    found: list[str] = []
    try:
        html = fetch(url)
    except Exception:
        html = ""
    if html:
        if looks_like_feed(html):
            return [url]  # the seed URL was itself a feed
        found.extend(parse_feed_links(html, url))

    if not found and probe_common:
        root = _root(url)
        for path in COMMON_FEED_PATHS:
            candidate = urljoin(root, path)
            try:
                body = fetch(candidate)
            except Exception:
                continue
            if body and looks_like_feed(body):
                found.append(candidate)
                break
    return _dedupe(found)


def bootstrap_sources(
    seed_urls: Iterable[str],
    fetch: Fetcher | None = None,
    today: str | None = None,
) -> list[Source]:
    """Turn a list of seed site URLs into discovered, deduped :class:`Source`s."""
    today = today or _dt.date.today().isoformat()
    out: list[Source] = []
    seen: set[str] = set()
    for seed in seed_urls:
        for feed_url in discover_feeds(seed, fetch=fetch):
            if feed_url in seen:
                continue
            seen.add(feed_url)
            out.append(
                Source(url=seed, feed_url=feed_url, added=today, tags=["bootstrap"])
            )
    return out


# --- fetching candidates -----------------------------------------------------


def fetch_candidates(
    sources: Iterable[Source],
    since: _dt.datetime | None = None,
    per_feed_limit: int = 20,
    parse_feed: Callable[[str], Any] | None = None,
) -> list[Item]:
    """Pull recent entries from each source's feed into a flat candidate list."""
    if parse_feed is None:  # imported lazily so the module loads without the dep
        import feedparser  # type: ignore

        parse_feed = feedparser.parse

    items: list[Item] = []
    for src in sources:
        if not src.feed_url:
            continue
        try:
            parsed = parse_feed(src.feed_url)
        except Exception:
            continue
        for entry in (getattr(parsed, "entries", None) or [])[:per_feed_limit]:
            published = _entry_datetime(entry)
            if since and published and published < since:
                continue
            items.append(
                Item(
                    title=_get(entry, "title"),
                    url=_get(entry, "link"),
                    summary=_get(entry, "summary"),
                    published=published.isoformat() if published else "",
                    source_url=src.url,
                )
            )
    return items


def extract_article(url: str) -> str:
    """Best-effort readable text for one article URL (used sparingly)."""
    try:
        import trafilatura  # type: ignore
    except Exception:
        return ""
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return ""
    return trafilatura.extract(downloaded) or ""


# --- helpers -----------------------------------------------------------------


def _default_fetch(url: str) -> str:
    import httpx  # type: ignore

    resp = httpx.get(url, follow_redirects=True, timeout=15.0)
    resp.raise_for_status()
    return resp.text


def _entry_datetime(entry: Any) -> _dt.datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if not parsed:
        if isinstance(entry, dict):
            parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return _dt.datetime(*parsed[:6])
    except (TypeError, ValueError):
        return None


def _get(entry: Any, key: str) -> str:
    if isinstance(entry, dict):
        return str(entry.get(key, "") or "")
    return str(getattr(entry, key, "") or "")


def _root(url: str) -> str:
    p = urlparse(url)
    if p.scheme and p.netloc:
        return f"{p.scheme}://{p.netloc}/"
    return url


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
