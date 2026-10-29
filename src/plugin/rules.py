"""Reading the index, the requests and the labels, and the one rule that decides a pick.

The index is nested: an entry's ``tier`` is the smallest index it belongs to, so the index at
size N is every entry whose tier is N or less, in the file's order. Every request's labelled
tool is in the 5-entry index, so the right answer is the same at every size and a larger index
only adds distractors. A pick is right when it equals the label and is in the task's index.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from contract import Entry, Request, Size

TIERS = (5, 10, 20, 50)
MOST_DESCRIPTION = 100
NAME = "abcdefghijklmnopqrstuvwxyz0123456789_"


class RuleError(ValueError):
    """An index, requests or labels file that does not follow the format."""


@dataclass(frozen=True)
class Catalogue:
    entries: list[Entry]  # every entry, in the file's order
    tiers: list[int]  # each entry's tier, in the same order


def read_index_data(data) -> Catalogue:
    """The ``Catalogue`` a parsed index file states, or raise ``RuleError``."""
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list) or not data["entries"]:
        raise RuleError("an index holds an entries list with at least one entry")
    names, entries, tiers = set(), [], []
    for item in data["entries"]:
        if not isinstance(item, dict):
            raise RuleError("every entry is an object")
        name, description, tier = item.get("name"), item.get("description"), item.get("tier")
        if not isinstance(name, str) or not name or set(name) - set(NAME):
            raise RuleError(f"every entry's name is lower-case letters, digits and underscores, not {name!r}")
        if name in names:
            raise RuleError(f"entry {name!r} is listed twice")
        if not isinstance(description, str) or not description.strip():
            raise RuleError(f"{name}: every entry has a description")
        if len(description) > MOST_DESCRIPTION:
            raise RuleError(f"{name}: a description runs to at most {MOST_DESCRIPTION} characters, not {len(description)}")
        if tier not in TIERS:
            raise RuleError(f"{name}: tier is one of {list(TIERS)}, not {tier!r}")
        names.add(name)
        entries.append(Entry(name=name, description=description))
        tiers.append(tier)
    for size in TIERS:
        if sum(1 for value in tiers if value <= size) != size:
            raise RuleError(f"the index at size {size} holds {sum(1 for v in tiers if v <= size)} entries, not {size}")
    return Catalogue(entries=entries, tiers=tiers)


def read_requests_data(data) -> list[Request]:
    """Every request a parsed requests file holds, in its order, or raise ``RuleError``."""
    if not isinstance(data, dict) or not isinstance(data.get("requests"), list) or not data["requests"]:
        raise RuleError("a requests file holds a requests list with at least one request")
    seen, made = set(), []
    for item in data["requests"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            raise RuleError("every request has an id")
        if item["id"] in seen:
            raise RuleError(f"request {item['id']!r} is listed twice")
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            raise RuleError(f"{item['id']}: every request has text")
        seen.add(item["id"])
        made.append(Request(id=item["id"], text=item["text"]))
    return made


def read_labels_data(data, requests: list[Request], catalogue: Catalogue) -> dict[str, str]:
    """Each request's labelled tool. Every label is in the 5-entry index, which is what makes the
    answer the same at every size."""
    if not isinstance(data, dict) or not isinstance(data.get("labels"), dict):
        raise RuleError("a labels file holds a labels object")
    labels = data["labels"]
    smallest = {entry.name for entry, tier in zip(catalogue.entries, catalogue.tiers, strict=True) if tier <= TIERS[0]}
    for request in requests:
        tool = labels.get(request.id)
        if not isinstance(tool, str):
            raise RuleError(f"{request.id}: every request has a labelled tool")
        if tool not in smallest:
            raise RuleError(f"{request.id}: {tool!r} is not in the {TIERS[0]}-entry index, so the answer would change with size")
    extra = [key for key in labels if key not in {request.id for request in requests}]
    if extra:
        raise RuleError(f"labels names {extra[0]!r}, which is not a request")
    return {request.id: labels[request.id] for request in requests}


def index_at(catalogue: Catalogue, size: Size) -> list[Entry]:
    """The index at ``size``: every entry of that tier or smaller, in the file's order."""
    return [entry for entry, tier in zip(catalogue.entries, catalogue.tiers, strict=True) if tier <= size.value]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sources_sha256(index_text: str, requests_text: str) -> str:
    return sha256_text(f"{sha256_text(index_text)}:{sha256_text(requests_text)}")


def inside(workspace: Path, name: str) -> Path:
    relative = Path(name)
    root = Path(workspace).resolve()
    path = (root / relative).resolve()
    if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root) or path == root:
        raise RuleError(f"{name!r} must name a file inside the workspace")
    return path


def read_text(workspace: Path, name: str) -> str:
    path = inside(workspace, name)
    if not path.is_file():
        raise RuleError(f"no file at {name}")
    return path.read_text(encoding="utf-8")


def labels_name(requests_name: str) -> str:
    """Where the labels live: beside the requests, named labels.json. No tool but answer_key reads
    them, so a pick can never be copied out of the data the agent is given."""
    return (Path(requests_name).parent / "labels.json").as_posix()


def load_sources(workspace: Path, index_name: str, requests_name: str) -> tuple[Catalogue, list[Request], str]:
    index_text = read_text(workspace, index_name)
    requests_text = read_text(workspace, requests_name)
    try:
        catalogue = read_index_data(json.loads(index_text))
        requests = read_requests_data(json.loads(requests_text))
    except json.JSONDecodeError as error:
        raise RuleError(f"not JSON: {error}") from error
    return catalogue, requests, sources_sha256(index_text, requests_text)


def load_labels(workspace: Path, requests_name: str, requests: list[Request], catalogue: Catalogue) -> dict[str, str]:
    text = read_text(workspace, labels_name(requests_name))
    try:
        return read_labels_data(json.loads(text), requests, catalogue)
    except json.JSONDecodeError as error:
        raise RuleError(f"{labels_name(requests_name)} is not JSON: {error}") from error
