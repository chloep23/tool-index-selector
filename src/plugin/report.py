"""report_picks: merge this run's picks into its report file."""

from __future__ import annotations

import json
from pathlib import Path

from contract import Pick, PicksOutput, ReportInput, ReportOutput
from plugin.rules import RuleError, load_sources
from plugin.selecting import REPORTS, RUN, run_folder

REPORT = "picks.json"


def report_path(run: str = RUN) -> str:
    return f"{REPORTS}/{run}/{REPORT}"


def report_picks(given: ReportInput, workspace: Path) -> ReportOutput:
    _, requests, _ = load_sources(Path(workspace), given.task.index, given.task.requests)
    order = [item.id for item in requests]
    named = [pick.request for pick in given.picks]
    unknown = [name for name in named if name not in set(order)]
    if unknown:
        raise RuleError(f"the requests file has no request {unknown[0]!r}")
    if len(set(named)) != len(named):
        raise RuleError("a request is answered twice in one call")

    folder = run_folder(Path(workspace))
    path = folder / REPORT
    held = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"picks": {}}
    wanted = {"index": given.task.index, "requests": given.task.requests, "size": given.task.size.value}
    if held.get("task") not in (None, wanted):
        raise RuleError(f"{report_path()} is another task's report: start a new run")
    for pick in given.picks:
        held["picks"][pick.request] = pick.tool
    held["task"] = wanted
    path.write_text(json.dumps(held, indent=1), encoding="utf-8")

    picks = [Pick(request=name, tool=held["picks"][name]) for name in order if name in held["picks"]]
    report = PicksOutput(task=given.task, run=RUN, picks=picks)
    return ReportOutput(path=report_path(), covered=len(picks), complete=len(picks) == len(order), report=report)
