"""State store seam.

Everything briarPipe needs to persist between runs — the source base, editions,
``STATE.md`` — goes through a small store interface. The default
:class:`LocalStore` is just the filesystem (the host persists however it likes);
:class:`GitStore` adds a commit-back step for hosts like GitHub Actions. Swapping
to object storage or a database later means writing one more store, nothing else.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class Store(Protocol):  # pragma: no cover - interface
    def read_text(self, rel_path: str) -> str | None: ...
    def write_text(self, rel_path: str, content: str) -> str: ...
    def read_json(self, rel_path: str) -> Any | None: ...
    def write_json(self, rel_path: str, data: Any) -> str: ...
    def persist(self, message: str) -> None: ...


class LocalStore:
    """Filesystem store rooted at the repo/working directory."""

    name = "local"

    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()

    def _path(self, rel_path: str) -> Path:
        return self.root / rel_path

    def read_text(self, rel_path: str) -> str | None:
        p = self._path(rel_path)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def write_text(self, rel_path: str, content: str) -> str:
        p = self._path(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return str(p)

    def read_json(self, rel_path: str) -> Any | None:
        text = self.read_text(rel_path)
        if text is None:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def write_json(self, rel_path: str, data: Any) -> str:
        return self.write_text(rel_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def persist(self, message: str) -> None:
        # Filesystem writes are already durable; nothing to commit.
        return None


class GitStore(LocalStore):
    """LocalStore that commits (and optionally pushes) results back to a repo."""

    name = "git"

    def __init__(self, root: str | Path = ".", push: bool = True) -> None:
        super().__init__(root)
        self.push = push

    def persist(self, message: str) -> None:
        import subprocess

        def git(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git", *args], cwd=self.root, capture_output=True, text=True
            )

        git("add", "-A")
        status = git("status", "--porcelain")
        if not status.stdout.strip():
            return  # nothing changed
        # Identify as the bot when running in CI; harmless locally.
        git("config", "user.name", "briarPipe")
        git("config", "user.email", "briarpipe@users.noreply.github.com")
        git("commit", "-m", message)
        if self.push:
            git("push")


def get_store(name: str, root: str | Path = ".") -> Store:
    key = (name or "local").lower()
    if key == "git":
        return GitStore(root)
    if key == "local":
        return LocalStore(root)
    raise ValueError(f"unknown store {name!r}; available: ['local', 'git']")
