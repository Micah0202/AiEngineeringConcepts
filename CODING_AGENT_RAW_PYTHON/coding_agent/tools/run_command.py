"""
Tool: run a terminal command inside the workspace.

This is the most dangerous tool in the project, so it is the most guarded.
Three gates, in this order:

    1. classify_command()   - is this even allowed?
    2. request_approval()   - if risky, does the human say yes?
    3. subprocess.run()     - execute, with shell=False, inside the jail

Nothing reaches gate 3 without clearing gates 1 and 2.
"""

import os
import shlex
import subprocess

from coding_agent import approvals, config
from coding_agent.security import JAIL, Risk, classify_command
from coding_agent.tools._helpers import truncate


def _child_env() -> dict[str, str]:
    """
    Build the environment the command will run with.

    ---------------------------------------------------------------------------
    ★ WHY THIS EXISTS: git can tunnel straight out of the path jail.

    workspace/ lives inside a git repository (this course repo). Git does not
    care about our sandbox - it walks UP from its working directory looking for
    a .git folder, finds the repo's one, and happily reports on files far
    outside the workspace:

        $ git status --short
        M ../coding_agent/tools/__init__.py     <- outside the jail!

    From there `git log -p` or `git show` would let the agent read the contents
    of files that resolve_safe_path() would have refused outright. The path jail
    guards OUR file tools; it cannot guard what another program chooses to open.

    GIT_CEILING_DIRECTORIES tells git "do not chdir above these paths" while
    searching for a repository. Pointing it at the workspace's parent means git
    stops at the workspace boundary - the same boundary the path jail uses.

    THE GENERAL LESSON: a sandbox is only as strong as the programs you let
    through it. Every allowed program is a potential tunnel, and each one has
    to be considered on its own terms.
    ---------------------------------------------------------------------------
    """
    env = os.environ.copy()

    # os.pathsep is ";" on Windows and ":" on POSIX. Using it rather than a
    # hardcoded separator keeps this correct on both.
    env["GIT_CEILING_DIRECTORIES"] = str(JAIL.parent)

    return env


def _build_argv(command: str) -> list[str]:
    """
    Turn the command string into an argv LIST for subprocess.

    posix=False keeps Windows backslashes intact - in POSIX mode shlex treats
    "\\" as an escape character and would turn C:\\temp\\x into C:tempx.

    The trade-off is that posix=False leaves quotes attached to the token, so
    'python "my file.py"' comes back as ['python', '"my file.py"']. We strip a
    matched pair of outer quotes ourselves, otherwise subprocess would look for
    a file whose name literally contains quote characters.
    """
    tokens = shlex.split(command, posix=False)

    cleaned = []
    for token in tokens:
        if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
            token = token[1:-1]
        cleaned.append(token)

    return cleaned


def run_command(command: str) -> str:
    """
    Execute one terminal command and return its exit code, stdout and stderr.

    The return value is a plain string because it becomes the model's "Observe"
    step. Even a failure (non-zero exit, missing program, timeout) is returned
    as text rather than raised - a failing command is INFORMATION the agent
    needs, not a reason to abort the run.
    """
    # -------------------------------------------------------------------------
    # GATE 1 - classify.
    # -------------------------------------------------------------------------
    risk, reason = classify_command(command)

    if risk is Risk.BLOCKED:
        # The human is not even offered the choice. Note we explain WHY: the
        # model reads this and can pick a different approach.
        return f"BLOCKED: {reason}"

    # -------------------------------------------------------------------------
    # GATE 2 - human approval, only for the middle tier.
    # -------------------------------------------------------------------------
    if risk is Risk.NEEDS_APPROVAL:
        approved = approvals.request_approval(
            action="Run a potentially destructive command",
            detail=f"{command}\n           Why flagged: {reason}",
        )
        if not approved:
            return f"DENIED by user: the command '{command}' was not approved."

    # -------------------------------------------------------------------------
    # GATE 3 - execute.
    # -------------------------------------------------------------------------
    argv = _build_argv(command)
    if not argv:
        return "Error: empty command."

    try:
        result = subprocess.run(
            argv,
            # ★ shell=False IS THE MOST IMPORTANT ARGUMENT ON THIS CALL.
            #
            # With shell=True the OS shell re-parses the string, and every
            # quoting trick becomes an escape route - the classifier above
            # would be checking one thing while the shell ran another.
            #
            # With shell=False there is no shell involved at all: argv[0] is
            # the program, the rest are literal arguments handed straight to
            # it. "rm -rf /" cannot expand, chain, or redirect, because nothing
            # is left to interpret those characters.
            shell=False,
            # ★ Run INSIDE the sandbox. A bare `python main.py` therefore means
            #   workspace/main.py, and relative paths in generated code resolve
            #   the way the model expects.
            cwd=JAIL,
            # ★ Stops git walking up out of the sandbox - see _child_env().
            env=_child_env(),
            capture_output=True,
            # Read as text, replacing any byte we cannot decode rather than
            # raising - console output on Windows is not always UTF-8.
            encoding="utf-8",
            errors="replace",
            # ★ Read from config.* (not a module-level import) so the timeout
            #   stays adjustable at runtime.
            timeout=config.COMMAND_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        # run() kills the child process before raising, so nothing is left
        # running in the background.
        return (
            f"Error: command timed out after {config.COMMAND_TIMEOUT} seconds "
            f"and was killed: {command}\n"
            f"If the program waits for user input, it cannot be run here."
        )
    except FileNotFoundError:
        return (
            f"Error: program '{argv[0]}' was not found.\n"
            f"Note there is no shell here, so shell builtins and aliases "
            f"(ls, dir, cd, echo) do not exist. Use the list_files tool to "
            f"browse the workspace."
        )
    except OSError as err:
        return f"Error running '{command}': {err}"

    # -------------------------------------------------------------------------
    # Format the observation.
    #
    # We always report the exit code, and we label empty streams explicitly.
    # "(empty)" tells the model the command genuinely produced no output;
    # showing nothing at all would leave it guessing whether output was lost.
    # -------------------------------------------------------------------------
    stdout = result.stdout.strip() or "(empty)"
    stderr = result.stderr.strip() or "(empty)"

    report = (
        f"$ {command}\n"
        f"exit code: {result.returncode}\n"
        f"\n--- stdout ---\n{stdout}\n"
        f"\n--- stderr ---\n{stderr}"
    )

    return truncate(report)
