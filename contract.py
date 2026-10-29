"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    READ_TASK = "read_task"
    REPORT_PICKS = "report_picks"
    ANSWER_KEY = "answer_key"
    SEARCH_INDEX = "search_index"


class Task(Enum):
    SELECT_5 = "select-5"
    SELECT_10 = "select-10"
    SELECT_20 = "select-20"
    SELECT_50 = "select-50"


class Size(Enum):
    FIVE = 5
    TEN = 10
    TWENTY = 20
    FIFTY = 50


INDEX = "The index file, relative to the workspace, e.g. index.json"
REQUESTS = "The requests file, relative to the workspace, e.g. requests.json"
SIZE = "How many entries this task's index holds: 5, 10, 20 or 50. The smaller indexes are contained in the larger ones"
TOOL_NAME = "A tool's name, exactly as the index writes it"
REQUEST_ID = "The request's id, exactly as the requests file writes it"
RUN = "The run that read this task's files, as read_task returns it: copy it unchanged"
SOURCE_HASH = "sha256 over the index and requests files the picks were made from"


@dataclass
class Entry(Output):
    name: Annotated[str, TOOL_NAME]
    description: Annotated[str, "What the tool does, in one line of at most 100 characters"]


@dataclass
class Request(Output):
    id: Annotated[str, REQUEST_ID]
    text: Annotated[str, "What the user asked for, in their own words"]


@dataclass
class Pick(Output):
    request: Annotated[str, REQUEST_ID]
    tool: Annotated[str, "The one tool in this task's index that handles the request, by name"]


@dataclass
class SelectInput(Output):
    index: Annotated[str, INDEX]
    requests: Annotated[str, REQUESTS]
    size: Annotated[Size, SIZE]


@dataclass
class TaskDataOutput(Output):
    run: Annotated[str, RUN]
    size: Annotated[Size, SIZE]
    entries: Annotated[list[Entry], "This task's index, in the order the file lists it"]
    requests: Annotated[list[Request], "Every request to answer, in the file's order"]
    source_sha256: Annotated[str, SOURCE_HASH]


@dataclass
class ReportInput(Output):
    task: Annotated[SelectInput, "The task input, exactly as given"]
    picks: Annotated[list[Pick], "The picks this call reports; an earlier pick for the same request is replaced"]


@dataclass
class PicksOutput(Output):
    task: Annotated[SelectInput, "The task input, exactly as given"]
    run: Annotated[str, RUN]
    picks: Annotated[list[Pick], "One pick per request, in the requests file's order"]


@dataclass
class ReportOutput(Output):
    path: Annotated[str, "The report file, relative to the workspace: reports/<run>/picks.json"]
    covered: Annotated[int, "How many of the requests the merged report answers so far"]
    complete: Annotated[bool, "Whether every request is answered: then submit the report"]
    report: Annotated[PicksOutput, "The merged report so far"]


@dataclass
class KeyOutput(Output):
    source_sha256: Annotated[str, SOURCE_HASH]
    picks: Annotated[list[Pick], "Every request's labelled tool, in the requests file's order"]


@dataclass
class SearchInput(Output):
    index: Annotated[str, INDEX]
    size: Annotated[Size, SIZE]
    query: Annotated[str, "Words to look for in the index"]


@dataclass
class Ranked(Output):
    name: Annotated[str, TOOL_NAME]
    overlap: Annotated[int, "How many of the query's words appear in the entry's name or description"]


@dataclass
class SearchOutput(Output):
    ranked: Annotated[
        list[Ranked],
        "The entries sharing at least one word with the query, most shared words first, then by index order",
    ]


TOOLS = {
    Tool.READ_TASK: (SelectInput, TaskDataOutput),
    Tool.REPORT_PICKS: (ReportInput, ReportOutput),
    Tool.ANSWER_KEY: (SelectInput, KeyOutput),
    Tool.SEARCH_INDEX: (SearchInput, SearchOutput),
}
TASKS = {
    Task.SELECT_5: (SelectInput, PicksOutput),
    Task.SELECT_10: (SelectInput, PicksOutput),
    Task.SELECT_20: (SelectInput, PicksOutput),
    Task.SELECT_50: (SelectInput, PicksOutput),
}
