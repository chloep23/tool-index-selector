"""The deterministic verifier: each tool's checks live in its own module, on contract instances."""

from contract import Task, Tool

from . import key, report, search, task, taskdata

TOOLS = {
    Tool.READ_TASK: taskdata,
    Tool.REPORT_PICKS: report,
    Tool.ANSWER_KEY: key,
    Tool.SEARCH_INDEX: search,
}
# Every select-N task is the same check at a different index size.
TASKS = dict.fromkeys(Task, task.verify_task)


def verify_input(tool, value):
    return TOOLS[Tool(tool)].verify_input(value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)].verify_output(input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](Task(task).value, arguments, output, reference, workspace)
