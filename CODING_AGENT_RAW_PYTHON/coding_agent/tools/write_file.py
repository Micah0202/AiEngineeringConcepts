"""Tool: create a new file, or overwrite an existing one."""

from coding_agent import approvals
from coding_agent.security import SecurityError, resolve_safe_path


def write_file(path: str, content: str) -> str:
    """
    Write `content` to `path`, creating parent folders as needed.

    APPROVAL RULE: creating a new file is free; OVERWRITING an existing one
    asks the human first.

    Why the asymmetry? Creating a file cannot destroy anything - at worst you
    get clutter. Overwriting silently discards work the user may care about.
    Prompting on every create would make the agent unusable (a Todo app needs
    several files); prompting only on overwrite keeps the friction where the
    actual risk is.
    """
    try:
        safe_path = resolve_safe_path(path)
    except SecurityError as err:
        return f"DENIED: {err}"

    if safe_path.is_dir():
        return f"Error: {path} is a directory, not a file."

    is_overwrite = safe_path.exists()

    if is_overwrite:
        # Note we import the MODULE (`from coding_agent import approvals`) and
        # call approvals.request_approval(...), rather than importing the
        # function by name. That keeps the lookup dynamic, so tests can swap
        # the behaviour without the tools having already bound the old one.
        old_size = safe_path.stat().st_size
        approved = approvals.request_approval(
            action="Overwrite an existing file",
            detail=f"{path}  ({old_size:,} bytes will be replaced)",
        )
        if not approved:
            # Returned as a normal observation so the model can adapt.
            return f"DENIED by user: overwrite of {path} was not approved."

    try:
        # The parent folders may not exist yet (e.g. "src/utils/helpers.py").
        # parents=True creates the whole chain; exist_ok=True makes it a no-op
        # if it is already there.
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding="utf-8")
    except OSError as err:
        return f"Error writing {path}: {err}"

    line_count = len(content.splitlines())
    verb = "Overwrote" if is_overwrite else "Created"
    return f"{verb} {path} ({line_count} lines, {len(content):,} characters)."
