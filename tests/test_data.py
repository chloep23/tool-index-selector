"""The committed data, held to what makes the four tasks comparable: the indexes nest, names are
unique, descriptions are short, and every request's answer is in the smallest index."""

from __future__ import annotations

import itertools
import json

import pytest
from helpers import FIXTURES, LABELS

import verifier.rules as checked

INDEX = json.loads((FIXTURES / "index.json").read_text())["entries"]
REQUESTS = json.loads((FIXTURES / "requests.json").read_text())["requests"]
ANSWERS = json.loads((FIXTURES / LABELS).read_text())["labels"]
TIERS = (5, 10, 20, 50)


@pytest.mark.parametrize("size", TIERS)
def test_the_index_at_each_size_holds_exactly_that_many_entries(size: int) -> None:
    assert len([entry for entry in INDEX if entry["tier"] <= size]) == size


@pytest.mark.parametrize(("smaller", "larger"), list(itertools.pairwise(TIERS)))
def test_each_index_is_contained_in_the_next(smaller: int, larger: int) -> None:
    inner = [entry["name"] for entry in INDEX if entry["tier"] <= smaller]
    outer = [entry["name"] for entry in INDEX if entry["tier"] <= larger]
    assert outer[: len(inner)] == inner, "the smaller index is the larger one's opening entries, in order"


def test_every_name_is_unique_and_well_formed() -> None:
    names = [entry["name"] for entry in INDEX]
    assert len(set(names)) == len(names)
    assert all(set(name) <= checked.NAME for name in names)


def test_every_description_fits_the_line_limit() -> None:
    longest = max(INDEX, key=lambda entry: len(entry["description"]))
    assert len(longest["description"]) <= 100, f"{longest['name']} runs to {len(longest['description'])}"


def test_every_request_is_labelled_with_a_tool_in_the_smallest_index() -> None:
    smallest = {entry["name"] for entry in INDEX if entry["tier"] <= TIERS[0]}
    assert {item["id"] for item in REQUESTS} == set(ANSWERS)
    assert set(ANSWERS.values()) <= smallest, "an answer outside the 5-entry index would change with size"


def test_the_answer_is_the_same_at_every_size() -> None:
    """The point of the nesting: only the distractors change."""
    for size in TIERS:
        names = {entry["name"] for entry in INDEX if entry["tier"] <= size}
        assert set(ANSWERS.values()) <= names


def test_one_request_is_answered_by_the_last_entry_of_the_smallest_index() -> None:
    """A boundary: the right answer is not found by stopping at the first plausible line."""
    last = [entry["name"] for entry in INDEX if entry["tier"] <= 5][-1]
    assert last in set(ANSWERS.values()), f"no request is answered by {last}"


def test_every_answer_gains_a_same_family_distractor_once_the_index_grows() -> None:
    """Rule 3, first kind: each answer has an entry whose name opens with the same word and which
    does something else, so the name alone never settles a request."""
    names = {entry["name"] for entry in INDEX}
    for answer in set(ANSWERS.values()):
        family = answer.split("_")[0]
        assert any(name != answer and name.split("_")[0] == family for name in names), f"{answer} has no neighbour"


def test_some_answers_gain_a_strict_prefix_near_duplicate() -> None:
    """Rule 3 again: send_email against send_email_draft, the hardest pair to tell apart."""
    names = {entry["name"] for entry in INDEX}
    twinned = [a for a in set(ANSWERS.values()) if any(n != a and n.startswith(a + "_") for n in names)]
    assert len(twinned) >= 2, f"only {twinned} have a name that extends them"


def test_the_fifty_index_adds_entries_that_share_request_words_and_do_something_else() -> None:
    """Rule 3, third kind: the keyword traps. search_index ranks by shared words alone, and at
    size 50 it puts the wrong entry first for most requests, which is what makes it a trap."""
    import re

    word = re.compile(r"[a-z0-9]+")
    traps = 0
    for item in REQUESTS:
        asked = set(word.findall(item["text"].lower()))
        answer = ANSWERS[item["id"]]
        best = max(
            (entry for entry in INDEX if entry["name"] != answer),
            key=lambda e: len(asked & set(word.findall((e["name"] + " " + e["description"]).lower()))),
        )
        overlap = len(asked & set(word.findall((best["name"] + " " + best["description"]).lower())))
        answer_entry = next(e for e in INDEX if e["name"] == answer)
        own = len(asked & set(word.findall((answer_entry["name"] + " " + answer_entry["description"]).lower())))
        if overlap >= own:
            traps += 1
    assert traps >= 5, f"only {traps} requests have a distractor matching as many words as the answer"
