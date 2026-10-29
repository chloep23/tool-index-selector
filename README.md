# Tool Index Selector

A `nanoagent.plugin/v0001` plugin that measures how well an agent picks the right tool from a
compact index, and how that degrades as the index grows. Four tasks ask the same ten requests
against indexes of 5, 10, 20 and 50 tools. No network: everything is read from files in the
workspace.

The index entries are **invented mock tools**, not this plugin's real tools. They exist to be
chosen between.

## Tools

| Name | Kind | Does | Code |
|---|---|---|---|
| `read_task` | tool | Reads both files in one call: the index at this task's size and every request | `src/plugin/selecting.py` |
| `report_picks` | tool | Merges the picks it is given into this run's report and returns the merged report | `src/plugin/report.py` |
| `answer_key` | tool | The labelled tool for every request | `src/plugin/selecting.py` |
| `search_index` | tool | Ranks index entries by how many of a query's words they share | `src/plugin/selecting.py` |
| `select-5` | task | Pick from the 5-tool index: runner `agent`, reference `answer_key` | `verifier/task.py` |
| `select-10` | task | The same requests against 10 tools | `verifier/task.py` |
| `select-20` | task | The same requests against 20 tools | `verifier/task.py` |
| `select-50` | task | The same requests against 50 tools | `verifier/task.py` |

`search_index` is honest about what it does and is not how the task is solved. Sharing words
with a request is not doing the job: at size 50 its top entry is the wrong tool for **7 of the
10 requests**, so an agent that follows it scores 0.3.

## The rules

1. **The indexes are nested.** The 5-tool index is contained in the 10, which is in the 20,
   which is in the 50. Every request's correct tool is in the 5-tool index, so **the right
   answer is the same at every size** and larger indexes only add distractors. That is what
   makes accuracy comparable across sizes.
2. **Each request has exactly one correct tool.** Requests are written so the correct entry's
   one-liner covers them and no other entry's does, even in the 50-tool index.
3. **Larger indexes add hard distractors** on purpose: near-duplicate names (`send_email`
   against `send_email_draft`), one-liners a single qualifier apart (`convert_currency` against
   `convert_units`), and entries sharing a request's words while doing something else
   (`currency_format` writes a number as currency text and converts nothing).
4. **A pick is correct only if it exactly matches the label and is in that task's index.** A
   name from a larger index is wrong in a smaller task, and fails its own check rather than
   being counted as a wrong guess.
5. **The index format is fixed:** `name: description`, one per line, the description at most
   100 characters.

An entry's `tier` in `index.json` is the smallest index it belongs to, so the nesting is
structural rather than a convention. The labels live in `labels.json`, read only by
`answer_key`, so no tool the agent can call will ever return one.

## The verdict

`verify_task` decides a `select-N` submission on 13 constraints, in order. A failure among the
first 10 scores 0; past them the score is **the share of requests picked correctly**.

| # | Constraint | Holds when |
|---|---|---|
| 1 | `answer-key` | The answer key is for this task's files |
| 2 | `sources` | The index, the requests and the labels are well formed |
| 3 | `answer-key-right` | The answer key's picks are the labelled tools |
| 4 | `task-size` | The task was run at its own index size |
| 5 | `this-run` | The report names a run of this workspace |
| 6 | `read-task` | read_task read this task's files, at this size, in this run |
| 7 | `report-saved` | report_picks saved this run's report for this task |
| 8 | `submitted-task` | The submitted report is for this task |
| 9 | `submitted-shape` | The submitted report is well formed |
| 10 | `submitted-as-saved` | The submitted report equals the saved report |
| 11 | `all-requests` | Every request is answered exactly once |
| 12 | `picks-in-index` | Every pick is a tool in this task's index |
| 13 | `picks-exact` | Every pick is the request's labelled tool |

`sources` is where the comparability is enforced rather than assumed: the indexes must nest,
names must be unique, descriptions must fit the line limit, and **every label must be in the
5-tool index**. A label outside it would mean the right answer changed with size, and the four
scores would no longer mean the same thing.

The verifier never runs a model. It reads the three files itself in `verifier/rules.py`, which
shares no code with the plugin.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions, tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable NAMEs this plugin needs, never values
├── src/plugin/      # the MCP server: __main__.py, its IMPLEMENTATIONS, and the plugin's own modules
├── tests/           # the suite, with the invented index, requests and labels under fixtures/
├── ui/              # how the page draws the outputs: renderers.js and renderers.css
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier package
```

`contract.py` is the one place a value's shape is declared. Its `Output` classes are the JSON
Schemas the server offers and the agent sees, and every input and output is built into its class
on the way in and out. A tool that fails raises; NanoAgent sees an MCP error.

Every tool in `tests/fixtures/index.json` is invented, and the data is built so each rule above
has a request that turns on it: a request whose answer is the last line of the smallest index,
near-duplicate names for the answers, and keyword traps that beat the answer on shared words.
`tests/test_data.py` asserts the invariants rather than trusting them.

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

Publishing checks every plugin rule: push the plugin to a public GitHub repository
and submit its URL on RUSH Lab.
