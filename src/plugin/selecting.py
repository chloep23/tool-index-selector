"""The tools: read_task, answer_key (the reference) and search_index (which answers a narrower
question than the task asks)."""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

from contract import KeyOutput, Pick, Ranked, SearchInput, SearchOutput, SelectInput, TaskDataOutput
from plugin.rules import RuleError, index_at, load_labels, load_sources

# One token per plugin process: every file a run writes lands under reports/<RUN>/.
RUN = secrets.token_hex(8)
REPORTS = "reports"
MARKER = "run.json"
RECEIPT = "task.json"
WORD = re.compile(r"[a-z0-9]+")


def run_folder(workspace: Path, run: str = RUN) -> Path:
    folder = Path(workspace) / REPORTS / run
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / MARKER
    if not marker.is_file():
        marker.write_text(json.dumps({"run": run}), encoding="utf-8")
    return folder


def read_task(given: SelectInput, workspace: Path) -> TaskDataOutput:
    """This task's index and its requests, in one call. The labels are never read here."""
    catalogue, requests, source = load_sources(Path(workspace), given.index, given.requests)
    receipt = {"run": RUN, "index": given.index, "requests": given.requests, "size": given.size.value, "sha256": source}
    (run_folder(Path(workspace)) / RECEIPT).write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    return TaskDataOutput(
        run=RUN,
        size=given.size,
        entries=index_at(catalogue, given.size),
        requests=requests,
        source_sha256=source,
    )


def answer_key(given: SelectInput, workspace: Path) -> KeyOutput:
    """The labelled tool for every request. The task's reference: the agent never sees it."""
    catalogue, requests, source = load_sources(Path(workspace), given.index, given.requests)
    labels = load_labels(Path(workspace), given.requests, requests, catalogue)
    return KeyOutput(source_sha256=source, picks=[Pick(request=item.id, tool=labels[item.id]) for item in requests])


def words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def search_index(given: SearchInput, workspace: Path) -> SearchOutput:
    """Every entry of this size sharing a word with the query, most shared words first.

    Literal word overlap and nothing else: it knows no more about what a request means than the
    words it happens to use, which is why the entry it puts first is often not the one that does
    the job.
    """
    if not given.query.strip():
        raise RuleError("a query holds at least one word")
    from plugin.rules import read_index_data, read_text

    text = read_text(Path(workspace), given.index)
    try:
        catalogue = read_index_data(json.loads(text))
    except json.JSONDecodeError as error:
        raise RuleError(f"{given.index} is not JSON: {error}") from error
    asked = words(given.query)
    ranked = []
    for position, entry in enumerate(index_at(catalogue, given.size)):
        overlap = len(asked & (words(entry.name) | words(entry.description)))
        if overlap:
            ranked.append((-overlap, position, entry.name))
    return SearchOutput(ranked=[Ranked(name=name, overlap=-score) for score, _, name in sorted(ranked)])
