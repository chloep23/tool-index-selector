"""read_task: the index at this task's size and the requests, both recomputed from the files."""

from .checks import result, verify_sources_input
from .rules import index_at, load

verify_input = verify_sources_input


def verify_output(input_value, output_value, workspace):
    entries, requests, _, source, problem = load(workspace, input_value.index, input_value.requests)
    if problem:
        return result(False, problem)
    if output_value.source_sha256 != source:
        return result(False, "source_sha256 is not the hash of the index and the requests")
    if output_value.size != input_value.size:
        return result(False, f"size reads {output_value.size.value}, not the {input_value.size.value} asked for")
    wanted = index_at(entries, input_value.size.value)
    if [entry.name for entry in output_value.entries] != wanted:
        return result(False, f"the index at size {input_value.size.value} is not the file's entries of that tier, in its order")
    described = {name: description for name, description, _ in entries}
    for entry in output_value.entries:
        if entry.description != described[entry.name]:
            return result(False, f"{entry.name}: the description is not the file's")
    if [(item.id, item.text) for item in output_value.requests] != requests:
        return result(False, "the requests are not the file's, in its order")
    return result(True, "the index and the requests are the files'", entries=len(wanted), requests=len(requests))
