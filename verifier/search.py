"""search_index: checked against the word overlap it claims, not against the task's answer."""

import json
import re

from .checks import result
from .rules import index_at, parse_index, read_text

WORD = re.compile(r"[a-z0-9]+")


def words(text):
    return set(WORD.findall(text.lower()))


def verify_input(value):
    if not isinstance(value.index, str) or not value.index.strip():
        return result(False, "the index is named by its path in the workspace")
    if not isinstance(value.query, str) or not value.query.strip():
        return result(False, "a query holds at least one word")
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    text, problem = read_text(workspace, input_value.index)
    if problem:
        return result(False, problem)
    try:
        entries, problem = parse_index(json.loads(text))
    except (ValueError, RecursionError) as error:
        return result(False, f"{input_value.index} is not JSON: {error}")
    if problem:
        return result(False, f"{input_value.index}: {problem}")
    asked = words(input_value.query)
    kept = set(index_at(entries, input_value.size.value))
    wanted = []
    for position, (name, description, _) in enumerate(entries):
        if name not in kept:
            continue
        overlap = len(asked & (words(name) | words(description)))
        if overlap:
            wanted.append((-overlap, position, name))
    ranked = [(name, -score) for score, _, name in sorted(wanted)]
    if [(item.name, item.overlap) for item in output_value.ranked] != ranked:
        return result(False, "the ranking is not the entries' word overlap with the query, most first")
    return result(True, "the ranking is the query's word overlap", ranked=len(ranked))
