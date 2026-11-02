"""Bounded, reproducible quote/word selection from stored stream passages; no model API."""

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass

from twitch_games.matching import normalize_answer

GENERATOR_VERSION = "weighted-quotes-v1"
WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
STOP_WORDS = set(
    """
a an the and or but if as at by for from in into of on to with without
i me my mine we us our you your he him his she her it its they them their
this that these those there here what who why when where how which
is am are was were be been being do does did have has had can cannot could
will would should not no yes so just really very like actually literally
um uh erm okay ok yeah gonna wanna know think believe want going getting
said says say thing things something anything everything nothing
""".split()
)


@dataclass(frozen=True)
class Passage:
    text: str
    segment_ids: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    complete_quote: str
    prompt: str
    canonical_answer: str
    blank_start: int
    blank_end: int
    digest: str
    segment_ids: tuple[str, ...]
    weight: float


def choose_quotes(
    passages: list[Passage], used_answers: set[str] | None = None, limit: int = 20
) -> list[Candidate]:
    """Rank at most 200 input passages; original quote/span is never rewritten."""
    if not 1 <= limit <= 50:
        raise ValueError("Candidate queue limit must be between 1 and 50")
    used = {normalize_answer(word) for word in used_answers or set()}
    usable: list[tuple[Passage, list[re.Match]]] = []
    seen: set[str] = set()
    for passage in passages[-200:]:
        text = passage.text
        if (
            not passage.segment_ids
            or not 1 <= len(text) <= 4000
            or text in seen
            or "____" in text
            or any(ord(char) < 32 and char not in "\n\t" for char in text)
        ):
            continue
        words = list(WORD.finditer(text))
        if not 8 <= len(words) <= 40:
            continue
        counts = Counter(normalize_answer(word.group()) for word in words)
        if max(counts.values()) / len(words) > 0.4:
            continue
        seen.add(text)
        usable.append((passage, words))
    frequency = Counter(
        word for _, words in usable for word in {normalize_answer(match.group()) for match in words}
    )
    candidates: list[Candidate] = []
    for passage, words in usable:
        eligible = []
        counts = Counter(normalize_answer(word.group()) for word in words)
        for match in words:
            normalized = normalize_answer(match.group())
            if (
                normalized in STOP_WORDS
                or normalized in used
                or counts[normalized] != 1
                or not 5 <= len(normalized) <= 24
            ):
                continue
            # Rare/local content words get weight, but length is capped to avoid garbage preference.
            weight = math.log1p(len(usable) / (1 + frequency[normalized]))
            weight += min(len(normalized), 10) * 0.03
            eligible.append((weight, match))
        if not eligible:
            continue
        weight, match = max(eligible, key=lambda pair: (pair[0], -pair[1].start()))
        text = passage.text
        candidates.append(
            Candidate(
                complete_quote=text,
                prompt=text[: match.start()] + "____" + text[match.end() :],
                canonical_answer=match.group(),
                blank_start=match.start(),
                blank_end=match.end(),
                digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                segment_ids=passage.segment_ids,
                weight=weight,
            )
        )
    candidates.sort(
        key=lambda candidate: (-candidate.weight, candidate.digest, candidate.blank_start)
    )
    selected: list[Candidate] = []
    selected_answers: set[str] = set()
    for candidate in candidates:
        normalized = normalize_answer(candidate.canonical_answer)
        if normalized not in selected_answers:
            selected.append(candidate)
            selected_answers.add(normalized)
        if len(selected) == limit:
            break
    return selected
