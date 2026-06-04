import datetime as dt
import time

from briarpipe import sources as S


def test_parse_feed_links_finds_advertised_feeds():
    html = """
    <html><head>
      <link rel="alternate" type="application/rss+xml" href="/feed.xml">
      <link rel="alternate" type="application/atom+xml" href="https://x.example/atom">
      <link rel="stylesheet" href="/style.css">
    </head></html>
    """
    feeds = S.parse_feed_links(html, "https://x.example/blog")
    assert "https://x.example/feed.xml" in feeds
    assert "https://x.example/atom" in feeds
    assert all("style.css" not in f for f in feeds)


def test_looks_like_feed():
    assert S.looks_like_feed("<?xml version='1.0'?><rss version='2.0'>")
    assert S.looks_like_feed("  <feed xmlns='http://www.w3.org/2005/Atom'>")
    assert not S.looks_like_feed("<!doctype html><html><body>hi</body></html>")


def test_discover_feeds_uses_advertised_link():
    pages = {
        "https://blog.example/": (
            '<html><head><link rel="alternate" '
            'type="application/rss+xml" href="/rss"></head></html>'
        ),
    }
    feeds = S.discover_feeds("https://blog.example/", fetch=lambda u: pages[u])
    assert feeds == ["https://blog.example/rss"]


def test_discover_feeds_probes_common_paths():
    def fetch(url):
        if url == "https://plain.example/":
            return "<html><body>no feed link here</body></html>"
        if url == "https://plain.example/feed":
            return "<rss version='2.0'><channel></channel></rss>"
        raise RuntimeError("404")

    feeds = S.discover_feeds("https://plain.example/", fetch=fetch)
    assert feeds == ["https://plain.example/feed"]


def test_discover_feeds_returns_seed_if_already_a_feed():
    feed_body = "<?xml version='1.0'?><feed></feed>"
    feeds = S.discover_feeds("https://x.example/atom.xml", fetch=lambda u: feed_body)
    assert feeds == ["https://x.example/atom.xml"]


def test_bootstrap_sources_dedupes_and_tags():
    def fetch(url):
        return '<link rel="alternate" type="application/rss+xml" href="https://shared/feed">'

    srcs = S.bootstrap_sources(
        ["https://a.example", "https://b.example"], fetch=fetch, today="2026-06-04"
    )
    # both seeds advertise the same feed; it should appear once
    assert len(srcs) == 1
    assert srcs[0].feed_url == "https://shared/feed"
    assert srcs[0].added == "2026-06-04"
    assert "bootstrap" in srcs[0].tags


def test_sources_json_round_trip():
    src = S.Source(url="https://a", feed_url="https://a/feed", title="A", score=2.0)
    data = S.sources_to_json([src])
    back = S.sources_from_json(data)
    assert back[0].feed_url == "https://a/feed"
    assert back[0].score == 2.0


def test_sources_from_json_ignores_unknown_keys():
    data = {"sources": [{"url": "u", "feed_url": "f", "mystery": 1}]}
    back = S.sources_from_json(data)
    assert back[0].url == "u"


def _entry(title, link, when):
    return {
        "title": title,
        "link": link,
        "summary": "s",
        "published_parsed": when.timetuple(),
    }


def test_fetch_candidates_filters_by_since():
    old = dt.datetime(2020, 1, 1)
    new = dt.datetime(2026, 6, 1)
    feed = type("F", (), {"entries": [_entry("old", "u1", old), _entry("new", "u2", new)]})()

    items = S.fetch_candidates(
        [S.Source(url="s", feed_url="https://s/feed")],
        since=dt.datetime(2026, 1, 1),
        parse_feed=lambda url: feed,
    )
    titles = [i.title for i in items]
    assert titles == ["new"]
    assert items[0].source_url == "s"
