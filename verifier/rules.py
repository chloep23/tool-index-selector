"""The index, the requests and the labels, read again from the files.

This is the verifier's own reading: it shares no code with the plugin, so a tool and the check
of that tool cannot be wrong in the same way. It also enforces what makes the four tasks
comparable -- the indexes nest, names are unique, descriptions are short, and every label is in
the smallest index, so the right answer never changes with size.
"""

import hashlib
import json
from pathlib import Path

TIERS = (5, 10, 20, 50)
MOST_DESCRIPTION = 100
NAME = set("abcdefghijklmnopqrstuvwxyz0123456789_")


def parse_index(data):
    """(the entries as (name, description, tier) triples, None) or (None, what is wrong)."""
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list) or not data["entries"]:
        return None, "an index holds an entries list with at least one entry"
    names, made = set(), []
    for item in data["entries"]:
        if not isinstance(item, dict):
            return None, "every entry is an object"
        name, description, tier = item.get("name"), item.get("description"), item.get("tier")
        if not isinstance(name, str) or not name or set(name) - NAME:
            return None, f"every entry's name is lower-case letters, digits and underscores, not {name!r}"
        if name in names:
            return None, f"entry {name!r} is listed twice"
        if not isinstance(description, str) or not description.strip():
            return None, f"{name}: every entry has a description"
        if len(description) > MOST_DESCRIPTION:
            return None, f"{name}: a description runs to at most {MOST_DESCRIPTION} characters, not {len(description)}"
        if tier not in TIERS:
            return None, f"{name}: tier is one of {list(TIERS)}, not {tier!r}"
        names.add(name)
        made.append((name, description, tier))
    for size in TIERS:
        held = sum(1 for _, _, tier in made if tier <= size)
        if held != size:
            return None, f"the index at size {size} holds {held} entries, not {size}"
    return made, None


def parse_requests(data):
    if not isinstance(data, dict) or not isinstance(data.get("requests"), list) or not data["requests"]:
        return None, "a requests file holds a requests list with at least one request"
    seen, made = set(), []
    for item in data["requests"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            return None, "every request has an id"
        if item["id"] in seen:
            return None, f"request {item['id']!r} is listed twice"
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            return None, f"{item['id']}: every request has text"
        seen.add(item["id"])
        made.append((item["id"], item["text"]))
    return made, None


def parse_labels(data, requests, entries):
    if not isinstance(data, dict) or not isinstance(data.get("labels"), dict):
        return None, "a labels file holds a labels object"
    labels = data["labels"]
    smallest = {name for name, _, tier in entries if tier <= TIERS[0]}
    made = {}
    for request, _ in requests:
        tool = labels.get(request)
        if not isinstance(tool, str):
            return None, f"{request}: every request has a labelled tool"
        if tool not in smallest:
            return None, f"{request}: {tool!r} is not in the {TIERS[0]}-entry index, so the answer would change with size"
        made[request] = tool
    extra = [key for key in labels if key not in {request for request, _ in requests}]
    if extra:
        return None, f"labels names {extra[0]!r}, which is not a request"
    return made, None


def index_at(entries, size):
    """The names of the index at ``size``, in the file's order."""
    return [name for name, _, tier in entries if tier <= size]


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sources_sha256(index_text, requests_text):
    return sha256_text(f"{sha256_text(index_text)}:{sha256_text(requests_text)}")


def read_text(workspace, name):
    if not isinstance(name, str) or not name:
        return None, f"{name!r} is not a file name"
    relative = Path(name)
    root = Path(workspace).resolve()
    path = (root / relative).resolve()
    if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root) or path == root:
        return None, f"{name!r} must name a file inside the workspace"
    if not path.is_file():
        return None, f"no file at {name}"
    if path.stat().st_size > 4_000_000:
        return None, f"{name} is too large to read"
    return path.read_text(encoding="utf-8"), None


def labels_name(requests_name):
    return (Path(requests_name).parent / "labels.json").as_posix()


def load(workspace, index_name, requests_name):
    """(entries, requests, labels, source hash, None) or (None, None, None, None, what is wrong)."""
    index_text, problem = read_text(workspace, index_name)
    if problem:
        return None, None, None, None, problem
    requests_text, problem = read_text(workspace, requests_name)
    if problem:
        return None, None, None, None, problem
    labels_text, problem = read_text(workspace, labels_name(requests_name))
    if problem:
        return None, None, None, None, problem
    try:
        index_data, requests_data, labels_data = json.loads(index_text), json.loads(requests_text), json.loads(labels_text)
    except (ValueError, RecursionError) as error:
        return None, None, None, None, f"a source file is not JSON: {error}"
    entries, problem = parse_index(index_data)
    if problem:
        return None, None, None, None, f"{index_name}: {problem}"
    requests, problem = parse_requests(requests_data)
    if problem:
        return None, None, None, None, f"{requests_name}: {problem}"
    labels, problem = parse_labels(labels_data, requests, entries)
    if problem:
        return None, None, None, None, f"{labels_name(requests_name)}: {problem}"
    return entries, requests, labels, sources_sha256(index_text, requests_text), None
