#!/usr/bin/env python3
"""briarPipe entrypoint — host-agnostic.

Run it however your host likes (cron, Docker, a laptop, GitHub Actions):

    python run.py                  # publish if an edition is due
    python run.py --force          # publish regardless of schedule
    python run.py --config my.yaml # use a specific config
    python run.py --store git      # commit results back

Bring your own provider: point ``provider.base_url`` at any OpenAI-compatible
endpoint and set your key in ``LLM_API_KEY`` (or whatever ``provider.api_key_env``
names). Secrets (the key, SMTP_*) come from the environment — locally as env vars
(or a ``.env``), in CI as Actions secrets. The single ``config.yaml`` is safe to
commit as long as those sensitive values stay out of it; the environment always
wins. The store defaults to the local filesystem; pass ``--store git`` (or set
BRIARPIPE_STORE=git) on a host that should commit results back.
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

    config_path = _resolve_config_path(args.config)
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    # Environment / Actions secrets win; the config's `secrets:` block only fills
    # gaps. Log names (never values) so it's clear where a key came from.
    applied = config.apply_secrets_to_env()
    if applied:
        print(f"using {len(applied)} secret(s) from config.yaml: {', '.join(sorted(applied))}")

    store_name = args.store or os.environ.get("BRIARPIPE_STORE", "local")
    store = get_store(store_name, root=args.root)
    now = _dt.datetime.now()

    last = (store.read_text(LAST_EDITION_PATH) or "").strip()
    if not args.force and not is_due(config.frequency, last, now):
        print(f"not due (frequency={config.frequency}, last={last or 'never'}); skipping")
        return 0

    prov = config.provider
    try:
        provider = get_provider(
            prov.name,
            prov.model,
            base_url=prov.base_url,
            api_key=os.environ.get(prov.api_key_env),
        )
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


def _resolve_config_path(path: str) -> str:
    """Use the given config path, falling back to config.yml for old setups.

    The default is ``config.yaml``; if that's absent but a legacy ``config.yml``
    sits next to it, use that instead so existing checkouts keep working.
    """
    if path == "config.yaml" and not os.path.exists(path) and os.path.exists("config.yml"):
        return "config.yml"
    return path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="briarPipe — be your own newsboy")
    p.add_argument("--config", default="config.yaml", help="path to config.yaml")
    p.add_argument("--root", default=".", help="working directory / repo root")
    p.add_argument("--store", default=None, choices=["local", "git"], help="state store")
    p.add_argument("--force", action="store_true", help="publish even if not due")
    return p.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
