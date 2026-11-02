"""PR #1 planning utilities, retained independently of the running quote game.

The runtime does not call this planner or its immutable-answer helper. Its actual
quote-game rules are documented in backend/README.md and implemented in game_service.
Pure planning is not a running game service or a persistence substitute.

Callers supply the drawn round modes/counts and explicit eligibility. This avoids
silently choosing count distribution, cooldown counting or selection policies.
The eventual repository must lock/revalidate all selected rows in one transaction.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class Mode(StrEnum):
    QUOTE = "quote_completion"
    NICHE = "niche"
    HIVE = "hive_mind"


@dataclass(frozen=True)
class RoundPlan:
    mode: Mode
    question_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.mode, Mode):
            raise ValueError("mode must be a Mode")
        if type(self.question_count) is not int or not 3 <= self.question_count <= 5:
            raise ValueError("Each round must contain 3–5 questions")


@dataclass(frozen=True)
class BankQuestion:
    id: str
    channel_id: str
    mode: Mode
    approved: bool
    source_eligible: bool
    off_cooldown: bool
    reserved: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Question ID must be nonblank text")
        if not isinstance(self.channel_id, str) or not self.channel_id.strip():
            raise ValueError("Channel ID must be nonblank text")
        if not isinstance(self.mode, Mode):
            raise ValueError("mode must be a Mode")
        if any(
            type(value) is not bool
            for value in (self.approved, self.source_eligible, self.off_cooldown, self.reserved)
        ):
            raise ValueError("Eligibility flags must be booleans")


@dataclass(frozen=True)
class PlannedRound:
    mode: Mode
    question_ids: tuple[str, ...]


class InsufficientSupply(ValueError):
    def __init__(self, mode: Mode, required: int, available: int):
        self.mode, self.required, self.available = mode, required, available
        super().__init__(f"{mode}: requires {required}; only {available} eligible")


def eligible_random_modes(previous: Mode | None) -> tuple[Mode, ...]:
    """The RNG/weight distribution remains a caller-owned, unresolved policy."""
    return tuple(mode for mode in Mode if mode != previous)


def plan_reservation(
    channel_id: str,
    rounds: Sequence[RoundPlan],
    bank: Sequence[BankQuestion],
    *,
    randomized: bool,
    allow_exact_repeats: bool | None = None,
) -> tuple[PlannedRound, ...]:
    """Return all reservations or fail without mutating any input.

    Input bank order is an explicit selection order supplied by the caller.
    Exact orders with repeats need an explicit caller-supplied product policy.
    No policy is selected when that input is absent. Random plans never repeat.
    """
    if not isinstance(channel_id, str) or not channel_id.strip() or not rounds:
        raise ValueError("A channel and at least one round are required")
    if type(randomized) is not bool:
        raise ValueError("randomized must be a boolean")
    if allow_exact_repeats is not None and type(allow_exact_repeats) is not bool:
        raise ValueError("allow_exact_repeats must be an explicit boolean policy")
    if len({q.id for q in bank}) != len(bank):
        raise ValueError("Duplicate bank question IDs")
    if randomized and any(a.mode == b.mode for a, b in zip(rounds, rounds[1:], strict=False)):
        raise ValueError("Random rotation cannot repeat consecutive modes")
    if (
        not randomized
        and any(a.mode == b.mode for a, b in zip(rounds, rounds[1:], strict=False))
        and allow_exact_repeats is not True
    ):
        raise ValueError("Exact-order repetition requires an explicitly approved policy")
    pool = {
        mode: [
            q.id
            for q in bank
            if q.channel_id == channel_id
            and q.mode == mode
            and q.approved
            and q.source_eligible
            and q.off_cooldown
            and not q.reserved
        ]
        for mode in Mode
    }
    for mode in Mode:
        required = sum(r.question_count for r in rounds if r.mode == mode)
        if required > len(pool[mode]):
            raise InsufficientSupply(mode, required, len(pool[mode]))
    result = []
    for item in rounds:
        selected = tuple(pool[item.mode][: item.question_count])
        del pool[item.mode][: item.question_count]
        result.append(PlannedRound(item.mode, selected))
    return tuple(result)


@dataclass(frozen=True)
class Submission:
    question_id: str
    viewer_id: str
    answer: str


def accept_final_answer(existing: Submission | None, incoming: Submission) -> Submission:
    """Preserve an accepted answer on retry; reject any attempted revision.

    Persistence must enforce the same rule under concurrency. Identity, question
    openness and deadline authorization happen before calling this function.
    """
    if not incoming.answer.strip():
        raise ValueError("Answer cannot be blank")
    if existing is None:
        return incoming
    if existing == incoming:
        return existing
    raise ValueError("Submission already accepted; revisions are not allowed")
