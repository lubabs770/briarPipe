"""Frequency due-check.

Scheduling is config-driven, not host-driven: a host invokes ``run.py`` on some
regular tick (e.g. daily cron) and briarPipe decides whether an edition is actually
due based on ``config.frequency`` and when it last published. This keeps the same
``run.py`` working identically on GitHub Actions, a VPS cron, or a laptop.
"""

from __future__ import annotations

import datetime as _dt

MIN_DAYS = {"daily": 1, "weekly": 7, "monthly": 28}


def is_due(frequency: str, last_published: str | None, now: _dt.datetime) -> bool:
    """Return True if a new edition should be published now.

    ``last_published`` is the ISO date (YYYY-MM-DD) of the previous edition, or
    None/"" if none has been published yet (always due).
    """
    if not last_published:
        return True
    try:
        last = _dt.date.fromisoformat(last_published.strip())
    except ValueError:
        return True  # unreadable bookkeeping -> don't get stuck, just publish
    elapsed = (now.date() - last).days
    return elapsed >= MIN_DAYS.get(frequency, 7)
