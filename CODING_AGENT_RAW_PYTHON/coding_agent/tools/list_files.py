"""Tool: show what files and folders exist in the workspace."""

from pathlib import Path

from coding_agent.security import SecurityError, is_denied, resolve_safe_path
from coding_agent.tools._helpers import truncate

# How deep to recurse. Without a cap, a deeply nested node_modules-style tree
# would produce thousands of lines and flood the model's context.
MAX_DEPTH = 4


def list_files(path: str = ".") -> str:
    """
    Return an indented tree of everything under `path`.

    Default "." means the workspace root - which is how the agent orients
    itself at the start of a task ("what already exists here?").
    """
    try:
        safe_path = resolve_safe_path(path)
    except SecurityError as err:
        return f"DENIED: {err}"

    if not safe_path.exists():
        return f"Error: path not found: {path}"

    if safe_path.is_file():
        size = safe_path.stat().st_size
        return f"{safe_path.name} ({size:,} bytes) - this is a file, not a directory."

    lines: list[str] = []
    _walk(safe_path, depth=0, lines=lines)

    if not lines:
        return f"{path} is empty."

    return truncate(f"{path}\n" + "\n".join(lines))


def _walk(directory: Path, depth: int, lines: list[str]) -> None:
    """
    Recursive helper. Appends one line per entry into `lines`.

    Note it takes `lines` as an argument and mutates it, rather than returning
    a new list at every level - simpler, and avoids rebuilding the list on each
    recursive call.
    """
    if depth >= MAX_DEPTH:
        lines.append("  " * (depth + 1) + "... (max depth reached)")
        return

    try:
        # Sorted so the output is stable between runs: folders first, then
        # files, each alphabetically. Stable output means the model sees the
        # same picture twice if nothing changed.
        entries = sorted(
            directory.iterdir(),
            key=lambda p: (p.is_file(), p.name.lower()),
        )
    except OSError as err:
        lines.append("  " * (depth + 1) + f"[cannot read: {err}]")
        return

    for entry in entries:
        # ★ Hidden, not refused. is_denied() is the non-raising version of the
        #   denylist, so one blocked entry does not abort the whole listing -
        #   it simply does not appear.
        if is_denied(entry):
            continue

        indent = "  " * (depth + 1)

        if entry.is_dir():
            lines.append(f"{indent}{entry.name}/")
            _walk(entry, depth + 1, lines)
        else:
            try:
                size = entry.stat().st_size
                lines.append(f"{indent}{entry.name}  ({size:,} bytes)")
            except OSError:
                lines.append(f"{indent}{entry.name}")
