"""Tool: delete a file from the workspace."""

from coding_agent import approvals
from coding_agent.security import SecurityError, resolve_safe_path


def delete_file(path: str) -> str:
    """
    Delete one file. ALWAYS asks the human first - no exceptions.

    Why always, when write_file only asks on overwrite? Because deletion has no
    harmless case. Creating a file you did not want leaves clutter; deleting a
    file you did want loses work. Confirming is cheap, so we always confirm.

    DIRECTORIES ARE NOT SUPPORTED, on purpose. A recursive directory delete is
    the single most destructive operation a coding agent can perform, and one
    wrong path would take the whole workspace with it. If the agent genuinely
    needs to remove a folder, that goes through run_command, where the command
    classifier gets its own look at it.
    """
    try:
        safe_path = resolve_safe_path(path)
    except SecurityError as err:
        return f"DENIED: {err}"

    if not safe_path.exists():
        return f"Error: file not found: {path}"

    if safe_path.is_dir():
        return (
            f"Error: {path} is a directory. delete_file only removes single "
            f"files, never folders."
        )

    size = safe_path.stat().st_size
    approved = approvals.request_approval(
        action="DELETE a file",
        detail=f"{path}  ({size:,} bytes - this cannot be undone)",
    )
    if not approved:
        return f"DENIED by user: deletion of {path} was not approved."

    try:
        safe_path.unlink()
    except OSError as err:
        return f"Error deleting {path}: {err}"

    return f"Deleted {path}."
