from briarpipe.budget import BudgetTracker, estimate_tokens
from briarpipe.providers import Usage


def test_estimate_tokens_roughly_chars_over_four():
    assert estimate_tokens("a" * 40) == 10
    assert estimate_tokens("") == 1  # never zero


def test_tracker_records_and_reports_remaining():
    t = BudgetTracker(limit=1000)
    assert t.remaining == 1000
    assert t.can_spend()
    t.record(Usage(input_tokens=300, output_tokens=200))
    assert t.spent == 500
    assert t.remaining == 500


def test_tracker_remaining_never_negative():
    t = BudgetTracker(limit=100)
    t.record(Usage(input_tokens=500, output_tokens=0))
    assert t.remaining == 0
    assert not t.can_spend()


def test_output_cap_respects_ceiling_and_reserve():
    t = BudgetTracker(limit=100_000)
    # 60% reserved for input by default -> 40% available, capped at ceiling
    assert t.output_cap(ceiling=8000) == 8000
    small = BudgetTracker(limit=1000)
    assert small.output_cap(ceiling=8000) == 600
    assert small.output_cap(ceiling=8000) >= 1
