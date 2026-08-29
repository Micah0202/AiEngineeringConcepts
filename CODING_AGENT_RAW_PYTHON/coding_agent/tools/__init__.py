"""
★ THE TOOL REGISTRY ★

This is the same idea as TOOL_FUNCTIONS in weather_app: a dictionary mapping
the NAME the model sends us (a plain string) to the actual Python function.

    model says:  {"name": "read_file", "arguments": '{"path": "main.py"}'}
    we do:       TOOL_FUNCTIONS["read_file"](path="main.py")

Why a dict instead of a chain of if/elif? Because adding a tool then means
adding one file plus one line here - and agent.py never changes. agent.py has
no idea which tools exist; it just looks names up in this table.

All six tools are registered below.
"""

from typing import Callable

from coding_agent.tools.delete_file import delete_file
from coding_agent.tools.edit_file import edit_file
from coding_agent.tools.list_files import list_files
from coding_agent.tools.read_file import read_file
from coding_agent.tools.run_command import run_command
from coding_agent.tools.write_file import write_file

# Every tool has the same contract: takes keyword arguments, returns a string.
# That returned string is what becomes the model's "Observe" step.
TOOL_FUNCTIONS: dict[str, Callable[..., str]] = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "delete_file": delete_file,
    "list_files": list_files,
    "run_command": run_command,
}

__all__ = ["TOOL_FUNCTIONS"]
