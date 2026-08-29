"""Tool: read the contents of a file inside the workspace."""

from coding_agent.config import MAX_FILE_READ_CHARS
from coding_agent.security import SecurityError, resolve_safe_path
from coding_agent.tools._helpers import truncate


def read_file(path: str) -> str:
    """
    Return the contents of a file, with line numbers.

    Every tool follows the same three-part shape:
      1. Ask security.py to validate the path   <- ALWAYS first
      2. Do the work
      3. Return a STRING (this becomes the model's "Observe" step)

    Errors are RETURNED, never raised. A raised exception would kill the whole
    agent run; a returned string lets the model read "file not found" and try
    something else. That is the difference between a brittle agent and a
    recoverable one.
    """
    try:
        # ★ STEP 1 - the gate. Nothing below runs if this raises.
        safe_path = resolve_safe_path(path)
    except SecurityError as err:
        return f"DENIED: {err}"

    if not safe_path.exists():
        return f"Error: file not found: {path}"

    if safe_path.is_dir():
        return f"Error: {path} is a directory. Use list_files to see what is inside it."

    try:
        # errors="replace" means a stray binary byte becomes a placeholder
        # character instead of raising UnicodeDecodeError and killing the run.
        text = safe_path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        return f"Error reading {path}: {err}"

    if not text:
        return f"(file {path} is empty)"

    # Cap the raw read before formatting, so a huge file cannot cost us the
    # time and memory of numbering a million lines.
    text = text[:MAX_FILE_READ_CHARS]

    # Line numbers are worth the extra characters: they let the model refer to
    # exact locations, and they make edit_file's job easier to reason about.
    numbered = "\n".join(
        f"{i:>4} | {line}" for i, line in enumerate(text.splitlines(), start=1)
    )

    return truncate(numbered)
