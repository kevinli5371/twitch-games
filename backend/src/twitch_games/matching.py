"""Deterministic server-side matching. Never autocorrect the stored submission."""

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz.distance import DamerauLevenshtein

MATCHER_VERSION = "bounded-damerau-v1"


def normalize_answer(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.replace("’", "'").replace("‘", "'")
    value = re.sub(r"\s+", " ", value).strip()
    # Strip decorative quotation/sentence punctuation, not meaningful +, -, # or apostrophes.
    return value.strip(' .,!?:;"“”')


@dataclass(frozen=True)
class MatchResult:
    correct: bool
    reason: str
    distance: int | None = None


def match_answer(submitted: str, canonical: str, aliases: tuple[str, ...] = ()) -> MatchResult:
    answer = normalize_answer(submitted)
    target = normalize_answer(canonical)
    if not answer or not target:
        return MatchResult(False, "empty")
    if answer == target:
        return MatchResult(True, "exact", 0)
    accepted = {normalize_answer(alias) for alias in aliases} - {""}
    if answer in accepted:
        return MatchResult(True, "alias", 0)
    # Semantic equivalence is explicit through aliases. Fuzzy multiword guesses are not accepted.
    if not answer.isalpha() or not target.isalpha():
        return MatchResult(False, "no_match")
    # Tiny edit distances can completely change short words (cat/car, win/won).
    if min(len(answer), len(target)) <= 4:
        return MatchResult(False, "short_word_requires_exact")
    cutoff = 1 if len(target) < 10 else 2
    distance = DamerauLevenshtein.distance(answer, target, score_cutoff=cutoff)
    if distance <= cutoff and distance / max(len(answer), len(target)) <= 0.2:
        return MatchResult(True, "spelling", distance)
    return MatchResult(False, "no_match")
