import datetime as dt
import json

from briarpipe.config import Config
from briarpipe.pipeline import run_pipeline
from briarpipe.providers import Completion, Usage
from briarpipe.store import LocalStore
from briarpipe.prompts import CURATE_SYSTEM


class FakeProvider:
    """Returns canned JSON depending on which phase is calling."""

    name = "fake"

    def __init__(self):
        self.calls = []

    def complete(self, system, prompt, max_tokens):
        self.calls.append((system, max_tokens))
        if system == CURATE_SYSTEM:
            payload = {
                "edition": {
                    "title": "Test Paper",
                    "intro": "Hello.",
                    "sections": [
                        {
                            "heading": "Headlines",
                            "stories": [
                                {
                                    "headline": "Big news",
                                    "summary": "It happened.",
                                    "url": "https://feed.example/story",
                                    "source": "Example",
                                }
                            ],
                        }
                    ],
                },
                "state_digest": "Covered: big news (2026-06-04).",
            }
        else:  # cultivate
            payload = {"add": ["https://new.example"], "drop": []}
        return Completion(text=json.dumps(payload), usage=Usage(100, 50))


def _config():
    return Config(
        interests="testing",
        frequency="weekly",
        edition_name="Test Paper",
        bootstrap_sources=["https://blog.example"],
    )


def _fetch(url):
    # Every site advertises one feed; cultivation's new source also resolves.
    return (
        '<link rel="alternate" type="application/rss+xml" '
        'href="https://feed.example/rss">'
    )


def _parse_feed(url):
    entry = {
        "title": "Big news",
        "link": "https://feed.example/story",
        "summary": "Something happened today.",
        "published_parsed": dt.datetime(2026, 6, 3).timetuple(),
    }
    return type("Feed", (), {"entries": [entry]})()


def test_full_run_publishes_edition_and_updates_state(tmp_path):
    store = LocalStore(tmp_path)
    provider = FakeProvider()
    result = run_pipeline(
        _config(),
        store,
        provider,
        now=dt.datetime(2026, 6, 4, 9, 0),
        fetch=_fetch,
        parse_feed=_parse_feed,
    )

    assert result.published is True
    assert result.story_count == 1
    assert result.curation_tokens == 150
    assert result.cultivation_tokens == 150

    # Edition written
    edition_md = (tmp_path / "editions" / "2026-06-04.md").read_text()
    assert "Big news" in edition_md
    assert edition_md.startswith("# Test Paper")

    # STATE.md written with the digest
    state = (tmp_path / "STATE.md").read_text()
    assert "Covered: big news" in state
    assert "continuity memory" in state

    # Source base persisted; bootstrap + cultivated source present
    base = json.loads((tmp_path / "state" / "sources.json").read_text())
    feeds = {s["feed_url"] for s in base["sources"]}
    assert "https://feed.example/rss" in feeds
    assert result.sources_after >= result.sources_before

    # Delivery ran (markdown baseline at least)
    assert any("edition written" in s for s in result.delivery_status)


def test_run_with_no_sources_does_not_publish(tmp_path):
    cfg = Config(interests="x", bootstrap_sources=[])
    result = run_pipeline(
        cfg, LocalStore(tmp_path), FakeProvider(), now=dt.datetime(2026, 6, 4)
    )
    assert result.published is False
    assert "nothing to curate" in " ".join(result.notes)


def test_fallback_edition_when_model_returns_garbage(tmp_path):
    class BadProvider(FakeProvider):
        def complete(self, system, prompt, max_tokens):
            self.calls.append((system, max_tokens))
            return Completion(text="not json at all", usage=Usage(10, 10))

    result = run_pipeline(
        _config(),
        LocalStore(tmp_path),
        BadProvider(),
        now=dt.datetime(2026, 6, 4),
        fetch=_fetch,
        parse_feed=_parse_feed,
    )
    assert result.published is True
    md = (tmp_path / "editions" / "2026-06-04.md").read_text()
    assert "editor unavailable" in md


# Markers that mean "not a local machine" — GitHub Actions sets both CI and
# GITHUB_ACTIONS, so a local run must have all of these unset.
_CI_VARS = (
    "CI", "GITHUB_ACTIONS", "GITLAB_CI", "CIRCLECI",
    "BUILDKITE", "JENKINS_URL", "TF_BUILD", "TRAVIS",
)


def test_saves_local_copy_when_configured_and_running_locally(tmp_path, monkeypatch):
    for var in _CI_VARS:
        monkeypatch.delenv(var, raising=False)
    save_dir = tmp_path / "Documents" / "news"
    cfg = _config()
    cfg.delivery.save_to = str(save_dir)

    result = run_pipeline(
        cfg,
        LocalStore(tmp_path),
        FakeProvider(),
        now=dt.datetime(2026, 6, 4, 9, 0),
        fetch=_fetch,
        parse_feed=_parse_feed,
    )

    saved = save_dir / "2026-06-04.md"
    assert saved.exists()
    assert "Big news" in saved.read_text()
    assert any("saved local copy" in n for n in result.notes)


def test_skips_local_copy_under_ci(tmp_path, monkeypatch):
    monkeypatch.setenv("CI", "true")
    save_dir = tmp_path / "Documents" / "news"
    cfg = _config()
    cfg.delivery.save_to = str(save_dir)

    result = run_pipeline(
        cfg,
        LocalStore(tmp_path),
        FakeProvider(),
        now=dt.datetime(2026, 6, 4, 9, 0),
        fetch=_fetch,
        parse_feed=_parse_feed,
    )

    assert not (save_dir / "2026-06-04.md").exists()
    assert any("save_to" in n and "skipped" in n for n in result.notes)


def test_no_local_copy_when_save_to_unset(tmp_path, monkeypatch):
    for var in _CI_VARS:
        monkeypatch.delenv(var, raising=False)
    result = run_pipeline(
        _config(),
        LocalStore(tmp_path),
        FakeProvider(),
        now=dt.datetime(2026, 6, 4, 9, 0),
        fetch=_fetch,
        parse_feed=_parse_feed,
    )
    assert not any("local copy" in n for n in result.notes)
