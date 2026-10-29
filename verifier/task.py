"""The select-N verdict: 13 constraints, in order, on the answer key, the run the submission
names, the receipt read_task left, the saved and submitted report, and the picks themselves.

The verdict is valid only when every one holds. A failure among the first 10 -- the sources and
the report's integrity -- scores 0; otherwise the score is the share of the requests picked
correctly, which is what makes the four sizes comparable: the right answer is the same at every
size, so a lower score at 50 is the index's distractors and nothing else.
"""

from pathlib import Path

from .checks import RECEIPT, REPORT, constraint, read_json, result, run_folder, run_problem, summary
from .rules import index_at, load

TEXT = {
    "answer-key": "The answer key is for this task's files",
    "sources": "The index, the requests and the labels are well formed",
    "answer-key-right": "The answer key's picks are the labelled tools",
    "task-size": "The task was run at its own index size",
    "this-run": "The report names a run of this workspace",
    "read-task": "read_task read this task's files, at this size, in this run",
    "report-saved": "report_picks saved this run's report for this task",
    "submitted-task": "The submitted report is for this task",
    "submitted-shape": "The submitted report is well formed",
    "submitted-as-saved": "The submitted report equals the saved report",
    "all-requests": "Every request is answered exactly once",
    "picks-in-index": "Every pick is a tool in this task's index",
    "picks-exact": "Every pick is the request's labelled tool",
}
ORDER = tuple(TEXT)
GATES = ORDER[:10]
ANSWER_CHECKS = ORDER[10:]
MOST_NAMED = 3
SUBMIT = "Submit the report the last report_picks call returned, as it is."
# task id -> the index size it is run at
SIZES = {"select-5": 5, "select-10": 10, "select-20": 20, "select-50": 50}


def named(names):
    shown = ", ".join(str(name) for name in names[:MOST_NAMED])
    return shown + (f" and {len(names) - MOST_NAMED} more" if len(names) > MOST_NAMED else "")


def also(words, names):
    return f" Also {words}: {named(names[1:])}." if len(names) > 1 else ""


def saved_report(workspace, run):
    """(the run's saved report, None) or (None, what is wrong with it)."""
    where = f"{run_folder(run)}/{REPORT}"
    found, problem = read_json(Path(workspace) / where)
    if problem == "missing":
        return None, f"no report at {where}: report_picks never saved this task's picks"
    if problem:
        return None, f"{where} is not a report: {problem}"
    if not isinstance(found, dict) or not isinstance(found.get("picks"), dict) or not isinstance(found.get("task"), dict):
        return None, f"{where} was altered after report_picks: it must hold task and picks"
    for request, tool in found["picks"].items():
        if not isinstance(request, str) or not isinstance(tool, str):
            return None, f"{where} was altered after report_picks: every pick is a request and a tool name"
    return found, None


def shape_problem(ids, picked):
    """Why the submitted report cannot be judged, or None."""
    listed = [request for request, _ in picked]
    unknown = [request for request in listed if request not in ids]
    if unknown:
        return f"{unknown[0]!r} is not a request in this task"
    repeated = [request for request in listed if listed.count(request) > 1]
    if repeated:
        return f"{repeated[0]} is answered twice"
    for request, tool in picked:
        if not isinstance(tool, str) or not tool.strip():
            return f"{request}: a pick is a tool's name, not {tool!r}"
    return None


def verify_task(task, arguments, output, reference, workspace):
    """The verdict on a submitted select-N report (see the module's docstring)."""
    checks = {}

    def put(identifier, ok, expected_value=None, actual=None, message=""):
        checks[identifier] = constraint(identifier, TEXT[identifier], ok, expected_value, actual, message)

    def skip(identifier, *needs):
        blocking = [need for need in needs if checks[need]["ok"] is not True]
        checks[identifier] = constraint(identifier, TEXT[identifier], None, message=f"Not checked: {' and '.join(blocking)} did not hold.")

    def hold(*identifiers):
        return all(checks[identifier]["ok"] is True for identifier in identifiers)

    # 1-4: the sources, the answer key and the size this task is run at.
    entries, requests, labels, source, problem = load(workspace, arguments.index, arguments.requests)
    if reference is None:
        put("answer-key", False, None, None, f"No answer key: answer_key never read {arguments.requests}.")
    elif problem is None and reference.source_sha256 != source:
        put("answer-key", False, source[:16], reference.source_sha256[:16], "The answer key read other files than this task names.")
    else:
        put("answer-key", True)
    put("sources", problem is None, None, None, problem or "")
    ids, wanted = [], []
    if hold("answer-key", "sources"):
        ids = [request for request, _ in requests]
        wanted = [(request, labels[request]) for request in ids]
        given = [(pick.request, pick.tool) for pick in reference.picks]
        put("answer-key-right", given == wanted, None, None, "The answer key's picks are not the labelled tools.")
    else:
        skip("answer-key-right", "answer-key", "sources")
    size = SIZES[task]
    put(
        "task-size",
        arguments.size.value == size,
        size,
        arguments.size.value,
        f"{task} is the {size}-entry index, but the task was run at {arguments.size.value}.",
    )

    # 5-6: the run, and the receipt read_task left in it.
    run = output.run
    problem = run_problem(workspace, run)
    put("this-run", problem is None, None, run, problem or "")
    if hold("this-run", "sources", "task-size"):
        where = f"{run_folder(run)}/{RECEIPT}"
        found, trouble = read_json(Path(workspace) / where)
        wanted_receipt = {"index": arguments.index, "requests": arguments.requests, "size": arguments.size.value}
        if trouble == "missing":
            message = f"read_task was never called in run {run} (no {where}): read the files before picking."
        elif trouble:
            message = f"{where} is not a receipt: {trouble}."
        elif not isinstance(found, dict) or found.get("run") != run:
            message = f"{where} was altered after read_task: it does not name run {run}."
        elif {key: found.get(key) for key in wanted_receipt} != wanted_receipt:
            message = f"read_task read {found.get('index')!r} and {found.get('requests')!r} at size {found.get('size')}, not this task's."
        else:
            message = ""
        put("read-task", not message, None, None, message)
    else:
        skip("read-task", "this-run", "sources", "task-size")

    # 7-10: the saved and the submitted report.
    saved = None
    if hold("this-run"):
        saved, problem = saved_report(workspace, run)
        wanted_task = {"index": arguments.index, "requests": arguments.requests, "size": arguments.size.value}
        if saved is not None and saved["task"] != wanted_task:
            saved, problem = None, f"the saved report is for another task: {saved['task']}"
        put("report-saved", saved is not None, None, None, problem or "")
    else:
        skip("report-saved", "this-run")
    given_task = {"index": output.task.index, "requests": output.task.requests, "size": output.task.size.value}
    wanted_task = {"index": arguments.index, "requests": arguments.requests, "size": arguments.size.value}
    put("submitted-task", given_task == wanted_task, wanted_task, given_task, f"The submitted report names {given_task}, not this task's. {SUBMIT}")
    picked = [(pick.request, pick.tool) for pick in output.picks]
    if hold("sources", "submitted-task"):
        problem = shape_problem(ids, picked)
        put("submitted-shape", problem is None, None, None, f"The submitted report is malformed: {problem}" if problem else "")
    else:
        skip("submitted-shape", "sources", "submitted-task")
    if saved is not None and hold("submitted-shape"):
        held = saved["picks"]
        difference = ""
        for request, tool in picked:
            if request not in held:
                difference = f"it adds {request}, which the saved report does not hold"
            elif held[request] != tool:
                difference = f"{request} reads {tool!r} in the submission but {held[request]!r} in the saved report"
            if difference:
                break
        if not difference and len(held) != len(picked):
            difference = "it leaves out a pick the saved report holds"
        put("submitted-as-saved", not difference, len(held), len(picked), f"The submitted report is not the saved report {run_folder(run)}/{REPORT}: {difference}. {SUBMIT}")
    else:
        skip("submitted-as-saved", "report-saved", "submitted-shape")

    # 11-13: the picks themselves.
    right = None
    if hold("answer-key-right", "submitted-shape", "task-size"):
        by_request = dict(picked)
        missing = [request for request in ids if request not in by_request]
        put(
            "all-requests",
            not missing,
            len(ids),
            len(by_request),
            f"{len(missing)} of the {len(ids)} requests {'is' if len(missing) == 1 else 'are'} not answered ({named(missing)}).",
        )
        in_index = set(index_at(entries, size))
        outside = [request for request in ids if request in by_request and by_request[request] not in in_index]
        if outside:
            first = outside[0]
            put(
                "picks-in-index",
                False,
                None,
                {request: by_request[request] for request in outside},
                f"{first} is answered {by_request[first]!r}, which is not one of the {size} tools in this task's index.{also('outside the index', outside)}",
            )
        else:
            put("picks-in-index", True)
        wrong = [
            request
            for request, tool in wanted
            if request in by_request and by_request[request] in in_index and by_request[request] != tool
        ]
        if wrong:
            first = wrong[0]
            put(
                "picks-exact",
                False,
                {request: labels[request] for request in wrong},
                {request: by_request[request] for request in wrong},
                f"{first} is answered {by_request[first]!r}, but the tool for it is {labels[first]!r}.{also('wrong', wrong)}",
            )
        else:
            put("picks-exact", True)
        right = sum(1 for request, tool in wanted if by_request.get(request) == tool)
    else:
        for identifier in ANSWER_CHECKS:
            skip(identifier, "answer-key-right", "submitted-shape", "task-size")

    constraints = [checks[identifier] for identifier in ORDER]
    valid = all(entry["ok"] is True for entry in constraints)
    if any(checks[identifier]["ok"] is not True for identifier in GATES) or right is None or not ids:
        score = 0.0
    else:
        score = right / len(ids)
    details = {"constraints": constraints, "size": size, "requests": len(ids) or None}
    if right is not None:
        details["right"] = right
    if valid:
        return result(True, f"All {len(constraints)} checks hold: {right} of {len(ids)} requests picked from the {size}-tool index.", score=1.0, **details)
    return result(False, summary(constraints), score=min(score, 0.99), **details)
