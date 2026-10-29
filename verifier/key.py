"""answer_key: the labelled tool for every request, recomputed."""

from .checks import result, verify_sources_input
from .rules import load

verify_input = verify_sources_input


def verify_output(input_value, output_value, workspace):
    _, requests, labels, source, problem = load(workspace, input_value.index, input_value.requests)
    if problem:
        return result(False, problem)
    if output_value.source_sha256 != source:
        return result(False, "source_sha256 is not the hash of the index and the requests")
    wanted = [(request, labels[request]) for request, _ in requests]
    given = [(pick.request, pick.tool) for pick in output_value.picks]
    if given != wanted:
        return result(False, "the answer key's picks are not the labelled tools, in the requests' order")
    return result(True, "the answer key is the labels", picks=len(wanted))
