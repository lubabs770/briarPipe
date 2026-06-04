"""Token budgeting primitives.

The whole point of briarPipe is *bounded* spend: a run never quietly blows through
your tokens. Each phase gets a tracker; the pipeline trims its inputs to fit and
stops calling the model once a phase's slice is exhausted.
"""

from __future__ import annotations

from dataclasses import dataclass

from .providers import Usage


def estimate_tokens(text: str) -> int:
    """Rough char-based token estimate (~4 chars/token). Good enough for trimming."""
    return max(1, len(text) // 4)


@dataclass
class BudgetTracker:
    """Tracks spend against a hard limit for one phase of the run."""

    limit: int
    spent: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.spent)

    def can_spend(self) -> bool:
        return self.remaining > 0

    def record(self, usage: Usage) -> None:
        self.spent += usage.total

    def output_cap(self, ceiling: int = 8000, reserve_for_input: float = 0.4) -> int:
        """How many output tokens to allow on the next call.

        Leaves a slice of what's left for the prompt itself and never exceeds
        ``ceiling``. Always returns at least 1 so a call can still be attempted
        when the budget is nearly gone.
        """
        allowance = int(self.remaining * (1 - reserve_for_input))
        return max(1, min(ceiling, allowance))
