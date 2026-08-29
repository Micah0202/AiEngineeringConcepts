"""
What the MODEL sees.

The model has never seen our Python functions. It only ever sees the JSON in
this file. That makes these descriptions part of the product, not documentation
- a vague description is the number one reason an agent fails to call a tool,
or calls the wrong one.

We generate the JSON from pydantic models rather than hand-writing it, so ONE
definition does two jobs:

    ReadFileArgs  --model_json_schema()-->  what we send the model
                  --model_validate()---->  checking what the model sends back

Hand-written schemas drift away from the code that uses them. Generated ones
cannot.
"""

from pydantic import BaseModel, Field

# =============================================================================
# ARGUMENT MODELS
#
# The Field(...) descriptions end up inside the JSON schema, so the model reads
# every one of them. Write them for the model, not for a human reviewer.
# `...` as the first argument means the field is REQUIRED.
# =============================================================================


class ToolArgs(BaseModel):
    """
    Base class every tool's arguments inherit from.

    ---------------------------------------------------------------------------
    ★ THIS IS HOW WE FORCE THE "REASON" STEP OF ReAct.

    The problem: gpt-4o-mini almost never writes text alongside a tool call.
    message.content comes back as None, so the model's thinking is invisible -
    and "Reason -> Act" collapses into just "Act". Telling it to explain itself
    in the system prompt does not reliably work; we tried, and it ignored it.

    The fix: make the reasoning part of the tool's ARGUMENTS. The model cannot
    call a tool without filling in every required field, so it now has to state
    why - not because we asked nicely, but because the request is structurally
    invalid otherwise.

    agent.py strips this field out before calling the actual Python function,
    so the tools themselves never see it and keep their clean signatures.

    The general lesson: when you need a model to do something reliably, prefer
    a structure that makes not doing it impossible over an instruction that
    asks it to comply.
    ---------------------------------------------------------------------------
    """

    reasoning: str = Field(
        ...,
        description=(
            "REQUIRED. One short sentence, in plain English, explaining what "
            "you have learned so far and why you are calling this tool now. "
            "Example: 'The workspace is empty, so I will create main.py first.'"
        ),
    )


class ReadFileArgs(ToolArgs):
    path: str = Field(
        ...,
        description=(
            "Path to the file, relative to the workspace root. "
            "Example: 'main.py' or 'src/utils.py'."
        ),
    )


class WriteFileArgs(ToolArgs):
    path: str = Field(
        ...,
        description=(
            "Path to the file, relative to the workspace root. "
            "Parent folders are created automatically."
        ),
    )
    content: str = Field(
        ...,
        description="The COMPLETE contents of the file. Not a fragment or a diff.",
    )


class EditFileArgs(ToolArgs):
    path: str = Field(..., description="Path to the existing file to change.")
    old_string: str = Field(
        ...,
        description=(
            "The exact text to find, copied character for character from the "
            "file including indentation. It must appear EXACTLY ONCE in the "
            "file. If it appears more than once, include more surrounding "
            "lines to make it unique."
        ),
    )
    new_string: str = Field(..., description="The text to replace it with.")


class DeleteFileArgs(ToolArgs):
    path: str = Field(..., description="Path to the file to delete.")


class ListFilesArgs(ToolArgs):
    # A default makes this optional in the generated schema, so the model can
    # call list_files with no arguments at all.
    path: str = Field(
        default=".",
        description="Folder to list. Defaults to '.', the workspace root.",
    )


class RunCommandArgs(ToolArgs):
    command: str = Field(
        ...,
        description=(
            "ONE single command to run, for example 'python main.py'. "
            "There is NO SHELL, so you cannot use pipes (|), redirects (> <), "
            "chaining (&& ; &), or backticks - commands containing them are "
            "rejected. Shell builtins such as ls, dir, cd and echo do not "
            "exist either; use the list_files tool to browse instead. "
            "To run two commands, call this tool twice."
        ),
    )


# =============================================================================
# BUILDING THE SCHEMAS THE MODEL RECEIVES
# =============================================================================


def _tool_schema(name: str, description: str, args_model: type[BaseModel]) -> dict:
    """
    Wrap one tool in the shape the OpenAI API expects.

    The {"type": "function", "function": {...}} nesting is the API's format,
    which leaves room for other tool types in future.
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            # ★ The schema is GENERATED from the pydantic model above, so the
            #   parameter names the model is told about are guaranteed to match
            #   the ones our validation expects.
            "parameters": args_model.model_json_schema(),
        },
    }


# ★ TOOL_MENU - passed to the API as tools=TOOL_MENU.
#   This is what actually gives the model the ability to request a tool.
#   Without it, tool calling is impossible no matter what the prompt says.
TOOL_MENU = [
    _tool_schema(
        "list_files",
        "List the files and folders in the workspace as a tree. Call this "
        "FIRST when starting a task, to see what already exists.",
        ListFilesArgs,
    ),
    _tool_schema(
        "read_file",
        "Read a file and return its contents with line numbers. You must read "
        "a file before editing it.",
        ReadFileArgs,
    ),
    _tool_schema(
        "write_file",
        "Create a new file, or completely replace an existing one. Use this to "
        "write new code. Overwriting a file that already exists requires the "
        "user's approval, so prefer edit_file for small changes.",
        WriteFileArgs,
    ),
    _tool_schema(
        "edit_file",
        "Change part of an existing file by replacing an exact piece of text. "
        "Cheaper and safer than rewriting the whole file. Read the file first "
        "so you can copy the text exactly.",
        EditFileArgs,
    ),
    _tool_schema(
        "delete_file",
        "Delete a single file. Always requires the user's approval. Cannot "
        "delete folders.",
        DeleteFileArgs,
    ),
    _tool_schema(
        "run_command",
        "Run one terminal command inside the workspace, for example "
        "'python main.py'. Use this to run and test the code you have written.",
        RunCommandArgs,
    ),
]


# ★ TOOL_ARG_MODELS - used by agent.py to VALIDATE the arguments the model
#   sends before we act on them. The model generates JSON as text, so it can
#   send the wrong shape; pydantic catches that before it reaches the disk.
TOOL_ARG_MODELS: dict[str, type[BaseModel]] = {
    "list_files": ListFilesArgs,
    "read_file": ReadFileArgs,
    "write_file": WriteFileArgs,
    "edit_file": EditFileArgs,
    "delete_file": DeleteFileArgs,
    "run_command": RunCommandArgs,
}


def tool_catalog() -> list[dict[str, str]]:
    """
    A stripped-down view of TOOL_MENU: just names and descriptions.

    The system prompt template loops over this to print a readable tool list.
    It does NOT need the parameter schemas - the model already receives those
    through the tools= API field, and repeating them in English would waste
    tokens and risk the two versions disagreeing.

    One source of truth (TOOL_MENU), two consumers.
    """
    return [
        {
            "name": schema["function"]["name"],
            "description": schema["function"]["description"],
        }
        for schema in TOOL_MENU
    ]
