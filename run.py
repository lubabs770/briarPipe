#!/usr/bin/env python3
"""briarPipe entrypoint — host-agnostic.

Run it however your host likes (GitHub Actions, cron, Docker, a laptop):

    python run.py                 # publish if an edition is due
    python run.py --force         # publish regardless of schedule
    python run.py --config my.yml # use a specific config
    python run.py --store git     # commit results back (CI)

Secrets (e.g. ANTHROPIC_API_KEY, SMTP_*) come from the environment, never config.
The store defaults to the local filesystem; pass ``--store git`` (or set
BRIARPIPE_STORE=git) on a host that should commit editions back.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys

from briarpipe.config import ConfigError, load_config
from briarpipe.pipeline import RunResult, run_pipeline
from briarpipe.providers import get_provider
from briarpipe.schedule import is_due
from briarpipe.store import get_store

LAST_EDITION_PATH = "state/last_edition.txt"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    store_name = args.store or os.environ.get("BRIARPIPE_STORE", "local")
    store = get_store(store_name, root=args.root)
    now = _dt.datetime.now()

    last = (store.read_text(LAST_EDITION_PATH) or "").strip()
    if not args.force and not is_due(config.frequency, last, now):
        print(f"not due (frequency={config.frequency}, last={last or 'never'}); skipping")
        return 0

    try:
        provider = get_provider(config.provider.name, config.provider.model)
    except ValueError as exc:
        print(f"provider error: {exc}", file=sys.stderr)
        return 2

    result = run_pipeline(config, store, provider, now=now)
    _report(result)

    if result.published:
        store.write_text(LAST_EDITION_PATH, result.date + "\n")
        store.persist(f"briarPipe: edition {result.date}")
    return 0


def _report(result: RunResult) -> None:
    for note in result.notes:
        print(f"· {note}")
    if not result.published:
        print("no edition published")
        return
    print(
        f"published {result.date}: {result.story_count} stories, "
        f"{result.total_tokens} tokens "
        f"(curate {result.curation_tokens} / cultivate {result.cultivation_tokens}), "
        f"sources {result.sources_before}→{result.sources_after}"
    )
    for status in result.delivery_status:
        print(f"  delivery: {status}")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="briarPipe — be your own newsboy")
    p.add_argument("--config", default="config.yml", help="path to config.yml")
    p.add_argument("--root", default=".", help="working directory / repo root")
    p.add_argument("--store", default=None, choices=["local", "git"], help="state store")
    p.add_argument("--force", action="store_true", help="publish even if not due")
    return p.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
