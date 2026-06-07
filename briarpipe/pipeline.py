"""The curate + cultivate pipeline — briarPipe's core.

One run:

1. Load config, the source base, and STATE.md.
2. Bootstrap the base from seed URLs if it's empty (no tokens).
3. Fetch candidate stories from known feeds (no tokens).
4. Curate (~80% of budget): pick + write the edition, and produce an updated
   STATE.md digest in the same call so continuity costs nothing extra.
5. Cultivate (~20% of budget): grow/prune the source base, validating new feeds.
6. Render, persist (edition + sources.json + STATE.md), deliver, and commit.

Phases are held to their slice of the token budget by :class:`BudgetTracker`.
"""

from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import sources as S
from .budget import BudgetTracker, estimate_tokens
from .config import Config
from .delivery import Edition, get_gateway
from .prompts import (
    CULTIVATE_SYSTEM,
    CURATE_SYSTEM,
    build_cultivate_prompt,
    build_curate_prompt,
    parse_json_response,
)
from .providers import Provider
from .render import edition_path, render_markdown
from .store import Store

SOURCES_PATH = "state/sources.json"
STATE_PATH = "STATE.md"
MAX_SOURCES = 60  # keep the base small and deliberate

# Environment markers that mean "this isn't your personal machine" — a CI runner
# or hosted/cloud environment. GitHub Actions sets both CI and GITHUB_ACTIONS.
# When any of these is present, ``output.save_to`` is skipped: dropping a file in
# a user's home directory only makes sense on that user's own box.
_CLOUD_ENV_MARKERS = (
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "CIRCLECI",
    "BUILDKITE",
    "JENKINS_URL",
    "TF_BUILD",  # Azure Pipelines
    "TRAVIS",
)

WINDOW_DAYS = {"daily": 2, "weekly": 8, "monthly": 32}


@dataclass
class RunResult:
    published: bool
    date: str
    edition_path: str = ""
    story_count: int = 0
    sources_before: int = 0
    sources_after: int = 0
    curation_tokens: int = 0
    cultivation_tokens: int = 0
    delivery_status: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.curation_tokens + self.cultivation_tokens


def run_pipeline(
    config: Config,
    store: Store,
    provider: Provider,
    *,
    now: _dt.datetime | None = None,
    fetch: Callable[[str], str] | None = None,
    parse_feed: Callable[[str], Any] | None = None,
) -> RunResult:
    now = now or _dt.datetime.now()
    today = now.date().isoformat()
    result = RunResult(published=False, date=today)

    # 1. Load state ----------------------------------------------------------
    base = S.sources_from_json(store.read_json(SOURCES_PATH))
    state_md = store.read_text(STATE_PATH) or ""
    result.sources_before = len(base)

    # 2. Bootstrap (first run only) -----------------------------------------
    if not base and config.bootstrap_sources:
        base = S.bootstrap_sources(config.bootstrap_sources, fetch=fetch, today=today)
        result.notes.append(f"bootstrapped {len(base)} source(s) from seeds")

    if not base:
        result.notes.append("no sources available; nothing to curate")
        store.write_json(SOURCES_PATH, S.sources_to_json(base))
        return result

    # 3. Fetch candidates (no tokens) ---------------------------------------
    since = now - _dt.timedelta(days=WINDOW_DAYS.get(config.frequency, 8))
    candidates = S.fetch_candidates(base, since=since, parse_feed=parse_feed)
    result.notes.append(f"{len(candidates)} candidate stories in window")

    # 4. Curate (~80%) -------------------------------------------------------
    curate_budget = BudgetTracker(config.token_budget.curation_budget)
    edition_data, state_digest = _curate(
        config, provider, candidates, state_md, curate_budget
    )
    result.curation_tokens = curate_budget.spent

    edition_data.setdefault("title", config.edition_name)
    edition_data["date"] = today
    result.story_count = sum(
        len(sec.get("stories") or []) for sec in edition_data.get("sections") or []
    )

    # 5. Cultivate (~20%) ----------------------------------------------------
    cultivate_budget = BudgetTracker(config.token_budget.cultivation_budget)
    base = _cultivate(config, provider, base, cultivate_budget, fetch, today)
    result.cultivation_tokens = cultivate_budget.spent
    result.sources_after = len(base)

    # 6. Render, persist, deliver -------------------------------------------
    markdown = render_markdown(edition_data)
    path = store.write_text(edition_path(today), markdown)
    result.edition_path = path

    # Optional: drop a copy into a local directory of the user's choosing — but
    # only on a personal machine, never on a CI/cloud runner.
    if config.output.save_to:
        saved = _save_local_copy(config.output.save_to, today, markdown)
        if saved:
            result.notes.append(f"saved local copy to {saved}")
        else:
            result.notes.append(
                f"output.save_to set ({config.output.save_to}) but skipped — "
                "not running on a local machine"
            )

    store.write_json(SOURCES_PATH, S.sources_to_json(base))
    if state_digest.strip():
        store.write_text(STATE_PATH, _stamp_state(state_digest, today))

    edition = Edition(
        title=edition_data["title"], date=today, markdown=markdown, path=path
    )
    result.delivery_status = _deliver(config, edition)

    # Persistence/commit is the caller's call (see run.py) so the pipeline stays
    # free of any host-specific concerns.
    result.published = True
    return result


# --- phases ------------------------------------------------------------------


def _curate(
    config: Config,
    provider: Provider,
    candidates: list[S.Item],
    state_md: str,
    budget: BudgetTracker,
) -> tuple[dict[str, Any], str]:
    items = _fit_candidates(config, candidates, budget, state_md)
    prompt = build_curate_prompt(config, items, state_md)

    if not budget.can_spend():
        return _fallback_edition(config, items), ""

    completion = provider.complete(
        CURATE_SYSTEM, prompt, max_tokens=budget.output_cap()
    )
    budget.record(completion.usage)

    parsed = parse_json_response(completion.text)
    edition = parsed.get("edition") if isinstance(parsed, dict) else None
    if not isinstance(edition, dict) or not edition.get("sections"):
        return _fallback_edition(config, items, raw=completion.text), ""
    state_digest = str(parsed.get("state_digest", "")) if isinstance(parsed, dict) else ""
    return edition, state_digest


def _cultivate(
    config: Config,
    provider: Provider,
    base: list[S.Source],
    budget: BudgetTracker,
    fetch: Callable[[str], str] | None,
    today: str,
) -> list[S.Source]:
    if not budget.can_spend():
        return base

    prompt = build_cultivate_prompt(config, base)
    completion = provider.complete(
        CULTIVATE_SYSTEM, prompt, max_tokens=budget.output_cap(ceiling=2000)
    )
    budget.record(completion.usage)
    parsed = parse_json_response(completion.text)
    if not isinstance(parsed, dict):
        return base

    # Drop flagged feeds.
    drop = {str(u) for u in (parsed.get("drop") or [])}
    if drop:
        base = [s for s in base if s.feed_url not in drop]

    # Validate and add suggestions (bounded discovery, never open crawling).
    known = {s.feed_url for s in base}
    for url in (parsed.get("add") or [])[:5]:
        for feed_url in S.discover_feeds(str(url), fetch=fetch):
            if feed_url not in known:
                known.add(feed_url)
                base.append(
                    S.Source(url=str(url), feed_url=feed_url, added=today, tags=["cultivated"])
                )

    # Keep the base small: trim lowest-scoring sources if over the cap.
    if len(base) > MAX_SOURCES:
        base.sort(key=lambda s: s.score, reverse=True)
        base = base[:MAX_SOURCES]
    return base


# --- helpers -----------------------------------------------------------------


def running_locally(env: dict[str, str] | None = None) -> bool:
    """True when running on a personal machine rather than CI/cloud.

    ``CI`` is honoured as a truthy flag (GitHub Actions, etc. set ``CI=true``);
    the other markers count by mere presence.
    """
    env = os.environ if env is None else env
    if str(env.get("CI", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return False
    return not any(env.get(marker) for marker in _CLOUD_ENV_MARKERS)


def _save_local_copy(
    save_to: str, date: str, markdown: str, *, env: dict[str, str] | None = None
) -> str | None:
    """Write a copy of the edition into ``save_to`` and return the full path.

    Returns ``None`` (writing nothing) when not running on a local machine, so
    the same committed config is a no-op on CI/cloud hosts.
    """
    if not running_locally(env):
        return None
    dest_dir = Path(save_to).expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{date}.md"
    dest.write_text(markdown, encoding="utf-8")
    return str(dest)


def _fit_candidates(
    config: Config,
    candidates: list[S.Item],
    budget: BudgetTracker,
    state_md: str,
) -> list[S.Item]:
    """Include as many candidates as fit within the curation input budget."""
    # Reserve ~60% of the phase budget for the prompt, the rest for output.
    input_token_budget = int(budget.limit * 0.6)
    base_cost = estimate_tokens(config.interests + config.style + state_md) + 400
    hard_cap = max(config.output.max_stories * 6, 12)

    chosen: list[S.Item] = []
    running = base_cost
    for item in candidates[: hard_cap * 2]:
        cost = estimate_tokens(item.title + item.summary[:400] + item.url) + 8
        if running + cost > input_token_budget and chosen:
            break
        chosen.append(item)
        running += cost
        if len(chosen) >= hard_cap:
            break
    return chosen


def _fallback_edition(
    config: Config, items: list[S.Item], raw: str = ""
) -> dict[str, Any]:
    """A minimal edition when the model is unavailable or returns unusable output."""
    stories = [
        {"headline": it.title, "summary": it.summary[:200], "url": it.url,
         "source": it.source_url}
        for it in items[: config.output.max_stories]
    ]
    intro = "Automated digest (editor unavailable)."
    return {
        "title": config.edition_name,
        "intro": intro,
        "sections": [{"heading": "Headlines", "stories": stories}],
    }


def _stamp_state(digest: str, today: str) -> str:
    return f"<!-- briarPipe continuity memory — updated {today} -->\n\n{digest.strip()}\n"


def _deliver(config: Config, edition: Edition) -> list[str]:
    statuses: list[str] = []
    gateways = ["markdown"]
    if config.delivery.gateway and config.delivery.gateway != "markdown":
        gateways.append(config.delivery.gateway)
    for name in gateways:
        try:
            gw = get_gateway(name, config.delivery.to, config.delivery.options)
            statuses.append(gw.send(edition))
        except Exception as exc:  # delivery failure shouldn't lose the edition
            statuses.append(f"{name}: delivery failed: {exc}")
    return statuses
