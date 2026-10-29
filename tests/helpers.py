"""Staging a workspace and running the prescribed path, as the host runs a select-N task."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from slimconfig import build_output, plain_output

import verifier
from contract import KeyOutput, PicksOutput, ReportInput, SelectInput
from plugin import answer_key, read_task, report_picks

FIXTURES = Path(__file__).resolve().parent / "fixtures"
INDEX = "index.json"
REQUESTS = "requests.json"
LABELS = "labels.json"
SIZES = (5, 10, 20, 50)
# The labels, which are the right answer at every size. Read from the committed file so the
# tests and the data cannot drift apart; the shape is asserted in test_data.py.
ANSWERS = json.loads((FIXTURES / LABELS).read_text())["labels"]
IDS = [item["id"] for item in json.loads((FIXTURES / REQUESTS).read_text())["requests"]]


def stage(workspace: Path, *names: str) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy(FIXTURES / name, workspace / name)


class Run:
    """One task's workspace: the staged files, the tools, and the verdict on what was submitted."""

    def __init__(self, workspace: Path, size: int = 5, index: str = INDEX, requests: str = REQUESTS) -> None:
        self.workspace = workspace
        self.size = size
        self.task_id = f"select-{size}"
        self.task = {"index": index, "requests": requests, "size": size}
        stage(workspace, index, requests, LABELS)
        self.given = build_output(self.task, SelectInput)
        self.submitted: dict | None = None
        self.run = ""
        # The host pins the reference before the agent runs.
        self.key: KeyOutput = build_output(plain_output(answer_key(self.given, workspace)), KeyOutput)

    def read(self):
        found = read_task(self.given, self.workspace)
        self.run = found.run
        return found

    def report(self, picks: list[dict]) -> dict:
        given = build_output({"task": self.task, "picks": picks}, ReportInput)
        self.submitted = plain_output(report_picks(given, self.workspace).report)
        return self.submitted

    def answer(self) -> list[dict]:
        """The answer key, in the shape report_picks takes."""
        return [{"request": pick.request, "tool": pick.tool} for pick in self.key.picks]

    def gold(self) -> dict:
        """The prescribed path, answered right: read the task, then one report call."""
        self.read()
        return self.report(self.answer())

    def verdict(self, report: dict | None = None, reference: KeyOutput | None = ...) -> dict:
        found = report if report is not None else self.submitted
        return verifier.verify_task(
            self.task_id,
            self.given,
            build_output(found, PicksOutput),
            self.key if reference is ... else reference,
            str(self.workspace),
        )


def failed(verdict: dict) -> list[str]:
    return [entry["id"] for entry in verdict["details"]["constraints"] if entry["ok"] is False]


def unchecked(verdict: dict) -> list[str]:
    return [entry["id"] for entry in verdict["details"]["constraints"] if entry["ok"] is None]
