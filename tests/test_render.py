from briarpipe.render import edition_path, render_markdown


def test_edition_path():
    assert edition_path("2026-06-04") == "editions/2026-06-04.md"


def test_render_markdown_structure():
    edition = {
        "title": "The Daily Briar",
        "date": "2026-06-04",
        "intro": "Good morning.",
        "sections": [
            {
                "heading": "Headlines",
                "stories": [
                    {
                        "headline": "Rockets land",
                        "summary": "A booster came home.",
                        "url": "https://example.com/a",
                        "source": "Booster Weekly",
                    }
                ],
            }
        ],
    }
    md = render_markdown(edition)
    assert md.startswith("# The Daily Briar")
    assert "*2026-06-04*" in md
    assert "Good morning." in md
    assert "## Headlines" in md
    assert "### [Rockets land](https://example.com/a)" in md
    assert "— *Booster Weekly*" in md
    assert md.endswith("\n")


def test_render_story_without_url_has_plain_heading():
    md = render_markdown(
        {"title": "T", "sections": [{"heading": "H", "stories": [{"headline": "No link"}]}]}
    )
    assert "### No link" in md
    assert "](" not in md  # no broken link


def test_render_skips_empty_sections():
    md = render_markdown({"title": "T", "sections": [{"heading": "", "stories": []}]})
    assert md.strip() == "# T"
