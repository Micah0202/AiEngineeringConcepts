"""Tool: change part of an existing file by exact string replacement."""

from coding_agent.security import SecurityError, resolve_safe_path


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """
    Replace exactly one occurrence of `old_string` with `new_string`.

    ---------------------------------------------------------------------------
    WHY EXACT-STRING REPLACEMENT INSTEAD OF "REWRITE THE WHOLE FILE"?

    Four reasons, and they all matter:

      CHEAPER  The model sends only the fragment that changes. Rewriting a
               300-line file to fix one typo costs 300 lines of output tokens.

      SAFER    If old_string is not in the file we return an error. A whole-file
               rewrite would silently produce something subtly wrong instead.

      FORCES A READ  The model cannot produce an exact old_string without
               having read the file first. Blind edits become structurally
               impossible - it is not a rule we have to enforce, it simply
               cannot happen.

      CATCHES AMBIGUITY  If old_string appears twice we refuse rather than
               guess. Guessing means editing the wrong line and being confident
               about it, which is the worst kind of bug.

    This is how Claude Code's own Edit tool behaves, for exactly these reasons.
    ---------------------------------------------------------------------------
    """
    try:
        safe_path = resolve_safe_path(path)
    except SecurityError as err:
        return f"DENIED: {err}"

    if not safe_path.exists():
        return f"Error: file not found: {path}. Use write_file to create it."

    if safe_path.is_dir():
        return f"Error: {path} is a directory, not a file."

    try:
        text = safe_path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        return f"Error reading {path}: {err}"

    if old_string == new_string:
        return "Error: old_string and new_string are identical - nothing to do."

    occurrences = text.count(old_string)

    if occurrences == 0:
        return (
            f"Error: old_string was not found in {path}.\n"
            f"Read the file again and copy the exact text, including "
            f"indentation and line breaks."
        )

    if occurrences > 1:
        return (
            f"Error: old_string appears {occurrences} times in {path}. "
            f"It must match exactly once.\n"
            f"Include more surrounding lines to make it unique."
        )

    # Exactly one match. count=1 is belt-and-braces; we already know it is unique.
    updated = text.replace(old_string, new_string, 1)

    try:
        safe_path.write_text(updated, encoding="utf-8")
    except OSError as err:
        return f"Error writing {path}: {err}"

    return f"Edited {path}: replaced 1 occurrence."
