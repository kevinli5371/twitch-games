import pytest

from twitch_games.matching import match_answer, normalize_answer
from twitch_games.quote_engine import Passage, choose_quotes


@pytest.mark.parametrize(
    "answer,canonical,correct,reason",
    [
        (" SPOON! ", "spoon", True, "exact"),
        ("ＳＰＯＯＮ", "spoon", True, "exact"),
        ("spoonn", "spoon", True, "spelling"),
        ("sopon", "spoon", True, "spelling"),
        ("bananna", "banana", True, "spelling"),
        ("car", "cat", False, "short_word_requires_exact"),
        ("won", "win", False, "short_word_requires_exact"),
        ("automobile", "car", False, "short_word_requires_exact"),
        ("a spoon", "spoon", False, "no_match"),
        ("c", "C++", False, "no_match"),
        ("", "spoon", False, "empty"),
        ("spade", "spoon", False, "no_match"),
    ],
)
def test_conservative_matching(answer, canonical, correct, reason):
    result = match_answer(answer, canonical)
    assert result.correct is correct
    assert result.reason == reason


def test_aliases_are_explicit_and_input_is_not_mutated():
    raw = "  AUTOMOBILE! "
    assert match_answer(raw, "car", ("automobile",)).correct
    assert raw == "  AUTOMOBILE! "
    assert not match_answer("automobile", "car").correct
    assert normalize_answer("don't") == "don't"
    assert normalize_answer("C++") == "c++"


def test_quote_is_exactly_one_original_span_and_repeatable():
    passage = Passage("I cannot believe we won with a spoon.", ("segment-1",))
    candidates = choose_quotes([passage])
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.canonical_answer == "spoon"
    assert candidate.prompt == "I cannot believe we won with a ____."
    assert candidate.complete_quote[candidate.blank_start : candidate.blank_end] == "spoon"
    assert candidates == choose_quotes([passage])


def test_quote_reuse_filler_garbage_and_duplicates_are_filtered():
    good = Passage("I cannot believe we won with a spoon.", ("1",))
    noisy = Passage("banana banana banana banana banana banana banana banana", ("2",))
    short = Passage("We won with spoon.", ("3",))
    filler = Passage("I think that we are just going to do that.", ("4",))
    assert len(choose_quotes([good, good, noisy, short, filler])) == 1
    assert choose_quotes([good], used_answers={"SPOON"}) == []
    assert choose_quotes([Passage(good.text, ())]) == []


def test_repeated_answers_cannot_remain_visible_elsewhere_in_the_prompt():
    quote = "We used a spoon and the spoon won us the game."
    assert choose_quotes([Passage(quote, ("1",))]) == []
    quote = "We used a spoon and the spoon won us the tournament."
    candidate = choose_quotes([Passage(quote, ("1",))])[0]
    assert candidate.canonical_answer == "tournament"
    assert candidate.prompt.count("____") == 1
    assert candidate.complete_quote == quote


def test_unicode_offsets_preserve_original_text_and_source_ids():
    text = "The café team somehow won this round using bananas."
    candidate = choose_quotes([Passage(text, ("source-a", "source-b"))])[0]
    assert candidate.segment_ids == ("source-a", "source-b")
    assert text[candidate.blank_start : candidate.blank_end] == candidate.canonical_answer
    assert candidate.prompt.replace("____", candidate.canonical_answer) == text
