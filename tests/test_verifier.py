"""The select-N verdict: a gold run at every size holds every constraint, and each one fails on
its own case with its own message; plus the per-call checks.

The cases are the five a verifier has to decide -- correct, wrong, missing, malformed, and the
boundaries where a plausible pick is the wrong one.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from helpers import ANSWERS, IDS, SIZES, Run, failed
from slimconfig import build_output, plain_output

import verifier
from contract import KeyOutput, ReportInput, SearchInput, TaskDataOutput
from plugin import search_index
from verifier.task import TEXT

CONSTRAINTS = len(TEXT)


# ----- Correct -----


@pytest.mark.parametrize("size", SIZES)
def test_a_gold_run_holds_every_constraint(tmp_path: Path, size: int) -> None:
    run = Run(tmp_path, size=size)
    run.gold()
    found = run.verdict()
    assert found["valid"], found["message"]
    assert found["score"] == 1.0 and found["message"].startswith(f"All {CONSTRAINTS} checks hold")
    assert [entry["ok"] for entry in found["details"]["constraints"]] == [True] * CONSTRAINTS
    assert found["details"]["size"] == size
    assert len(json.dumps(found)) < 8000, "the verdict lands in the chat's context: keep it small"


@pytest.mark.parametrize("size", SIZES)
def test_the_right_answer_is_the_same_at_every_size(tmp_path: Path, size: int) -> None:
    """The nesting is the point: only the distractors change."""
    report = Run(tmp_path, size=size).gold()
    assert {pick["request"]: pick["tool"] for pick in report["picks"]} == ANSWERS


# ----- Wrong -----


def test_a_wrong_pick_fails_picks_exact_and_costs_one_request(tmp_path: Path) -> None:
    run = Run(tmp_path, size=10)
    run.read()
    picks = run.answer()
    picks[0] = {**picks[0], "tool": "send_email_draft"}
    run.report(picks)
    found = run.verdict()
    assert failed(found) == ["picks-exact"]
    assert "r01 is answered 'send_email_draft', but the tool for it is 'send_email'" in found["message"]
    assert found["score"] == pytest.approx(9 / 10)


def test_trusting_the_keyword_search_scores_badly(tmp_path: Path) -> None:
    """search_index ranks by shared words alone. Taking its top entry for every request is a
    plausible strategy and a losing one."""
    run = Run(tmp_path, size=50)
    run.read()
    picks = []
    for request_id, text in [(item["id"], item["text"]) for item in json.loads((Path(run.workspace) / "requests.json").read_text())["requests"]]:
        ranked = search_index(build_output({"index": "index.json", "size": 50, "query": text}, SearchInput), run.workspace).ranked
        picks.append({"request": request_id, "tool": ranked[0].name})
    run.report(picks)
    found = run.verdict()
    assert "picks-exact" in failed(found)
    assert found["score"] <= 0.5, f"the keyword ranking scored {found['score']}"


def test_a_submission_that_is_not_the_saved_report_fails_submitted_as_saved(tmp_path: Path) -> None:
    run = Run(tmp_path)
    report = run.gold()
    changed = copy.deepcopy(report)
    changed["picks"][0]["tool"] = "create_event"
    found = run.verdict(changed)
    assert failed(found)[0] == "submitted-as-saved" and found["score"] == 0.0


def test_an_answer_key_that_is_not_the_labels_fails_answer_key_right(tmp_path: Path) -> None:
    run = Run(tmp_path)
    report = run.gold()
    key = plain_output(run.key)
    key["picks"][0] = {**key["picks"][0], "tool": "translate_text"}
    found = run.verdict(report, reference=build_output(key, KeyOutput))
    assert failed(found)[0] == "answer-key-right" and found["score"] == 0.0


def test_running_a_task_at_another_size_fails_task_size(tmp_path: Path) -> None:
    """select-5 run against the 50-entry index: the sizes must agree or nothing is comparable."""
    run = Run(tmp_path, size=50)
    run.task_id = "select-5"
    run.gold()
    found = run.verdict()
    assert failed(found) == ["task-size"] and found["score"] == 0.0
    assert "select-5 is the 5-entry index, but the task was run at 50" in found["message"]


# ----- Missing -----


def test_no_answer_key_fails_first_and_scores_zero(tmp_path: Path) -> None:
    run = Run(tmp_path)
    report = run.gold()
    found = run.verdict(report, reference=None)
    assert failed(found)[0] == "answer-key" and found["score"] == 0.0 and "answer_key never read" in found["message"]


def test_picks_without_reading_the_task_fail_read_task(tmp_path: Path) -> None:
    run = Run(tmp_path)
    run.gold()
    (tmp_path / "reports" / run.run / "task.json").unlink()
    found = run.verdict()
    assert failed(found)[0] == "read-task" and found["score"] == 0.0
    assert "was never called in run" in found["message"]
    assert found["details"]["right"] == 10, "the picks are still judged, and still right"


def test_an_unanswered_request_fails_all_requests(tmp_path: Path) -> None:
    run = Run(tmp_path)
    run.read()
    run.report(run.answer()[:-1])
    found = run.verdict()
    assert failed(found) == ["all-requests"]
    assert f"1 of the {len(IDS)} requests is not answered ({IDS[-1]})" in found["message"]
    assert found["score"] == pytest.approx(9 / 10)


def test_no_saved_report_fails_report_saved(tmp_path: Path) -> None:
    run = Run(tmp_path)
    report = run.gold()
    (tmp_path / "reports" / run.run / "picks.json").unlink()
    found = run.verdict(report)
    assert failed(found)[0] == "report-saved" and found["score"] == 0.0


def test_a_missing_source_file_fails_sources(tmp_path: Path) -> None:
    run = Run(tmp_path)
    report = run.gold()
    (tmp_path / "labels.json").unlink()
    found = run.verdict(report)
    assert "sources" in failed(found) and "No file at labels.json" in found["message"]


# ----- Malformed -----


def test_an_unknown_request_id_fails_submitted_shape(tmp_path: Path) -> None:
    run = Run(tmp_path)
    report = run.gold()
    broken = copy.deepcopy(report)
    broken["picks"][0]["request"] = "r99"
    found = run.verdict(broken)
    assert failed(found) == ["submitted-shape"] and found["score"] == 0.0
    assert "'r99' is not a request in this task" in found["message"]


def test_a_request_answered_twice_fails_submitted_shape(tmp_path: Path) -> None:
    run = Run(tmp_path)
    report = run.gold()
    twice = copy.deepcopy(report)
    twice["picks"].append(dict(twice["picks"][0]))
    found = run.verdict(twice)
    assert failed(found) == ["submitted-shape"] and "r01 is answered twice" in found["message"]


def test_an_empty_pick_fails_submitted_shape(tmp_path: Path) -> None:
    run = Run(tmp_path)
    report = run.gold()
    broken = copy.deepcopy(report)
    broken["picks"][0]["tool"] = "   "
    found = run.verdict(broken)
    assert failed(found) == ["submitted-shape"] and "a pick is a tool's name" in found["message"]


@pytest.mark.parametrize(("token", "words"), [("../..", "is not a run token"), ("", "is not a run token"), ("0" * 16, "has no run")])
def test_a_run_that_is_not_this_workspace_s_fails_this_run(tmp_path: Path, token: str, words: str) -> None:
    run = Run(tmp_path)
    report = run.gold()
    found = run.verdict({**report, "run": token})
    assert failed(found)[0] == "this-run" and words in found["message"] and found["score"] == 0.0


@pytest.mark.parametrize(
    ("change", "words"),
    [
        ({"entries": []}, "at least one entry"),
        ({"entries": [{"name": "a", "description": "x", "tier": 5}]}, "holds 1 entries, not 5"),
        ({"entries": [{"name": "Send_Email", "description": "x", "tier": 5}]}, "lower-case letters"),
    ],
)
def test_an_index_that_breaks_the_format_fails_sources(tmp_path: Path, change: dict, words: str) -> None:
    run = Run(tmp_path)
    report = run.gold()
    path = tmp_path / "index.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), **change}))
    found = run.verdict(report)
    assert "sources" in failed(found) and words in found["message"]


def test_a_description_over_the_line_limit_fails_sources(tmp_path: Path) -> None:
    run = Run(tmp_path)
    report = run.gold()
    path = tmp_path / "index.json"
    data = json.loads(path.read_text())
    data["entries"][0]["description"] = "x" * 101
    path.write_text(json.dumps(data))
    found = run.verdict(report)
    assert "sources" in failed(found) and "at most 100 characters, not 101" in found["message"]


def test_a_label_outside_the_smallest_index_fails_sources(tmp_path: Path) -> None:
    """The invariant that makes the sizes comparable, enforced rather than assumed."""
    run = Run(tmp_path)
    report = run.gold()
    path = tmp_path / "labels.json"
    data = json.loads(path.read_text())
    data["labels"]["r01"] = "send_email_draft"
    path.write_text(json.dumps(data))
    found = run.verdict(report)
    assert "sources" in failed(found) and "is not in the 5-entry index" in found["message"]


def test_an_edited_report_file_always_gives_a_verdict(tmp_path: Path) -> None:
    """600 mutations of the saved report: one field, at any depth, replaced by an odd JSON value
    or dropped. Every one is a verdict; none is an exception."""
    import random

    run = Run(tmp_path)
    report = run.gold()
    path = tmp_path / "reports" / run.run / "picks.json"
    good = json.loads(path.read_text())
    odd = [None, 0, -1, 1e308, "", "x", [], {}, [1], {"a": 1}, True, "../..", "r01", "send_email"]
    randomly = random.Random(7)
    for _ in range(600):
        broken = json.loads(json.dumps(good))
        target = randomly.choice(["task", "picks", "pick", "drop"])
        if target == "pick" and broken["picks"]:
            key = randomly.choice(list(broken["picks"]))
            broken["picks"][key] = randomly.choice(odd)
        elif target == "drop":
            broken.pop(randomly.choice(list(broken)), None)
        else:
            broken[target] = randomly.choice(odd)
        path.write_text(json.dumps(broken))
        found = run.verdict(report)
        assert isinstance(found["valid"], bool) and 0.0 <= found["score"] <= 1.0, broken


# ----- Boundary -----


def test_a_near_duplicate_distractor_is_wrong(tmp_path: Path) -> None:
    """send_email_draft saves without sending; the request says straight away."""
    run = Run(tmp_path, size=10)
    run.read()
    picks = [{**pick, "tool": "send_email_draft"} if pick["request"] == "r01" else pick for pick in run.answer()]
    run.report(picks)
    found = run.verdict()
    assert failed(found) == ["picks-exact"] and "send_email_draft" in found["message"]


def test_a_keyword_trap_distractor_is_wrong(tmp_path: Path) -> None:
    """currency_format writes a number as currency text; it converts nothing."""
    run = Run(tmp_path, size=50)
    run.read()
    picks = [{**pick, "tool": "currency_format"} if pick["request"] == "r05" else pick for pick in run.answer()]
    run.report(picks)
    found = run.verdict()
    assert failed(found) == ["picks-exact"]
    assert "r05 is answered 'currency_format', but the tool for it is 'convert_currency'" in found["message"]


def test_a_tool_from_the_fifty_index_is_outside_a_select_5_task(tmp_path: Path) -> None:
    """Rule 4: a name from a larger index is wrong in a smaller task, and fails its own check."""
    run = Run(tmp_path, size=5)
    run.read()
    picks = [{**pick, "tool": "translate_document"} if pick["request"] == "r09" else pick for pick in run.answer()]
    run.report(picks)
    found = run.verdict()
    assert failed(found) == ["picks-in-index"], failed(found)
    assert "r09 is answered 'translate_document', which is not one of the 5 tools in this task's index" in found["message"]
    assert found["score"] == pytest.approx(9 / 10)


def test_the_correct_tool_can_be_the_last_entry_of_the_index(tmp_path: Path) -> None:
    """translate_text is the fifth and final line of the 5-entry index."""
    run = Run(tmp_path, size=5)
    data = run.read()
    assert data.entries[-1].name == "translate_text"
    assert ANSWERS["r09"] == "translate_text" and ANSWERS["r10"] == "translate_text"
    run.report(run.answer())
    assert run.verdict()["valid"]


@pytest.mark.parametrize("size", SIZES)
def test_the_index_grows_but_the_requests_do_not(tmp_path: Path, size: int) -> None:
    run = Run(tmp_path, size=size)
    data = run.read()
    assert len(data.entries) == size and len(data.requests) == len(IDS)
    assert [entry.name for entry in data.entries][:5] == ["send_email", "create_event", "convert_currency", "resize_image", "translate_text"]


# ----- The per-call checks -----


def test_every_tool_has_both_checks_on_its_module(tmp_path: Path) -> None:
    """NanoAgent calls verify_input and verify_output on every tool call, so every Tool must
    resolve to a module exposing both."""
    from contract import Tool

    assert set(verifier.TOOLS) == set(Tool)
    for tool in Tool:
        module = verifier.TOOLS[tool]
        for name in ("verify_input", "verify_output"):
            assert callable(module.__dict__.get(name)), f"{tool.value}: {module.__name__} has no {name}"


def test_verify_input_answers_for_every_tool(tmp_path: Path) -> None:
    run = Run(tmp_path)
    from contract import Tool

    valid = {
        Tool.READ_TASK: run.given,
        Tool.ANSWER_KEY: run.given,
        Tool.REPORT_PICKS: build_output({"task": run.task, "picks": []}, ReportInput),
        Tool.SEARCH_INDEX: build_output({"index": "index.json", "size": 5, "query": "send an email"}, SearchInput),
    }
    for tool, value in valid.items():
        found = verifier.verify_input(tool.value, value)
        assert found["valid"] is True, (tool.value, found["message"])


def test_verify_output_recomputes_the_index_at_the_size_asked_for(tmp_path: Path) -> None:
    run = Run(tmp_path, size=20)
    data = plain_output(run.read())
    assert verifier.verify_output("read_task", run.given, build_output(data, TaskDataOutput), str(tmp_path))["valid"]
    changed = copy.deepcopy(data)
    changed["entries"] = changed["entries"][:-1]
    found = verifier.verify_output("read_task", run.given, build_output(changed, TaskDataOutput), str(tmp_path))
    assert not found["valid"] and "not the file's entries of that tier" in found["message"]


def test_the_search_distractor_is_checked_against_word_overlap_not_the_answer(tmp_path: Path) -> None:
    """search_index is honest about what it does; its check holds it to that and nothing more."""
    Run(tmp_path, size=50)  # stages the files
    given = build_output({"index": "index.json", "size": 50, "query": "convert 240 euros into yen"}, SearchInput)
    found = search_index(given, tmp_path)
    assert verifier.verify_output("search_index", given, found, str(tmp_path))["valid"]
    assert found.ranked[0].name != ANSWERS["r05"] or found.ranked[0].overlap >= 1


# ----- The verdict's own shape -----


def test_every_verdict_entry_has_the_same_keys_and_says_why(tmp_path: Path) -> None:
    run = Run(tmp_path)
    report = run.gold()
    broken = copy.deepcopy(report)
    broken["picks"][0]["tool"] = "create_event"
    for found in (run.verdict(report), run.verdict(broken), run.verdict({**report, "run": "0" * 16})):
        entries = found["details"]["constraints"]
        order = [entry["id"] for entry in entries]
        assert order == list(TEXT)
        for position, entry in enumerate(entries):
            assert set(entry) == {"id", "constraint", "ok", "expected", "actual", "message"}
            assert (entry["message"] == "") == (entry["ok"] is True)
            if entry["ok"] is None:
                blocking = entry["message"].removeprefix("Not checked: ").removesuffix(" did not hold.").split(" and ")
                assert all(name in order[:position] for name in blocking), entry
        wrong = [entry for entry in entries if entry["ok"] is False]
        if wrong:
            more = f" (+{len(wrong) - 1} more)" if len(wrong) > 1 else ""
            assert found["message"] == f"{wrong[0]['id']}: {wrong[0]['message'].removesuffix('.')}{more}"


def test_the_readme_lists_every_constraint_as_the_verifier_names_it() -> None:
    import re

    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\d+) \| `([a-z-]+)` \| ([^|]+) \|", readme, re.MULTILINE)
    assert [(int(n), name, text.strip()) for n, name, text in rows] == [(n, *e) for n, e in enumerate(TEXT.items(), 1)]
