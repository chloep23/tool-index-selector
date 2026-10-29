"""report_picks: the call and the merged report it returns."""

from .checks import result, run_folder, sources_problem
from .rules import load


def verify_input(value):
    problem = sources_problem(value.task)
    if problem:
        return result(False, problem)
    named = [pick.request for pick in value.picks]
    if len(set(named)) != len(named):
        return result(False, "a request is answered twice in one call")
    for pick in value.picks:
        if not isinstance(pick.tool, str) or not pick.tool.strip():
            return result(False, f"{pick.request}: a pick is a tool's name, not {pick.tool!r}")
    return result(True, "input is valid", picks=len(named))


def verify_output(input_value, output_value, workspace):
    _, requests, _, _, problem = load(workspace, input_value.task.index, input_value.task.requests)
    if problem:
        return result(False, problem)
    order = [request for request, _ in requests]
    report = output_value.report
    if output_value.path != f"{run_folder(report.run)}/picks.json":
        return result(False, f"the report path reads {output_value.path!r}, not this run's")
    if output_value.covered != len(report.picks):
        return result(False, f"covered reads {output_value.covered}, but the report holds {len(report.picks)} picks")
    if output_value.complete != (len(report.picks) == len(order)):
        return result(False, f"complete reads {output_value.complete}, which is not whether every request is answered")
    listed = [pick.request for pick in report.picks]
    if listed != [request for request in order if request in set(listed)]:
        return result(False, "the merged report's picks are not in the requests file's order")
    for pick in input_value.picks:
        if not any(held.request == pick.request and held.tool == pick.tool for held in report.picks):
            return result(False, f"{pick.request} is not in the merged report")
    return result(True, "the merged report holds this call", covered=output_value.covered)
