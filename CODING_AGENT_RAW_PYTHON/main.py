"""
The command line interface for the coding agent.

Run it interactively:

    cd CODING_AGENT_RAW_PYTHON
    uv run python main.py

Or give it a single task and let it exit when done:

    uv run python main.py "Create a fizzbuzz script and run it"

This file is deliberately thin. It handles TALKING TO THE HUMAN - reading
input, printing output, remembering the conversation. All the thinking happens
in coding_agent/agent.py.
"""

import sys

from coding_agent import build_greeting, run_agent
from coding_agent.client import get_client_and_model
from coding_agent.config import MAX_STEPS
from coding_agent.security import JAIL

QUIT_WORDS = ("quit", "exit", "q", "bye")

# Characters that are INVISIBLE but are not whitespace as far as Python is
# concerned, so str.strip() leaves them behind:
#   ﻿  byte order mark - PowerShell and many editors prepend one
#   ​  zero width space      ‌  zero width non-joiner
#   ‍  zero width joiner     ⁠  word joiner
#
# Without this, piping an "empty" line into the agent produces a query of
# "﻿", which is truthy - so `if not query` passes and the agent runs a
# whole task on an invisible character. That is a wasted API call at best, and
# a surprise edit to your files at worst. It happened during testing.
INVISIBLE_CHARS = "﻿​‌‍⁠"


def clean_input(raw: str) -> str:
    """Strip whitespace AND invisible characters, so 'blank' really is blank."""
    return raw.strip().strip(INVISIBLE_CHARS).strip()


def print_banner() -> None:
    """Show what this is, which model is running, and where the sandbox is."""
    print()
    print("=" * 72)
    print(build_greeting().strip())
    print("=" * 72)

    # Report the provider up front. If no API key is set, get_client_and_model
    # raises RuntimeError - catching it here means the user gets one clear line
    # telling them what to fix, instead of a traceback.
    try:
        _client, model, provider = get_client_and_model()
        print(f"  provider  : {provider.name} ({model})")
    except RuntimeError as err:
        print(f"  provider  : NOT CONFIGURED - {err}")

    # Printing the sandbox path matters: the user should be able to see at a
    # glance exactly which folder the agent is able to touch.
    print(f"  workspace : {JAIL}")
    print(f"  max steps : {MAX_STEPS} per request")
    print("=" * 72)


def handle(query: str, history: list[dict]) -> None:
    """
    Run one user request and record the result.

    The try/except is what stops a network blip, an expired API key, or a bug
    in a tool from ending the whole session. The user sees the error and can
    simply ask again.
    """
    print()
    print("-" * 72)
    print(f"TASK: {query}")
    print("-" * 72)

    try:
        answer = run_agent(query, history)
    except KeyboardInterrupt:
        # Ctrl+C during a long run means "stop this task", not "quit".
        print("\n\n  (interrupted - the task was stopped)")
        return
    except Exception as err:  # noqa: BLE001 - one bad request must not end the session
        print(f"\n  ERROR: {type(err).__name__}: {err}")
        return

    print()
    print("-" * 72)
    print("ANSWER:")
    print(answer)
    print("-" * 72)

    # ★ The CALLER owns the history. run_agent() reads it but never touches it,
    #   so the appends happen here where you can see them - no hidden mutation.
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": answer})


def main() -> None:
    print_banner()

    # Conversation memory for this session. Passing it to run_agent is what
    # makes follow-ups like "now add a delete function" work - the model can
    # see what was asked and answered before.
    history: list[dict] = []

    # ---- one-shot mode -----------------------------------------------------
    # Anything after the script name is treated as a single task. Handy for
    # scripted runs and for testing without typing.
    if len(sys.argv) > 1:
        task = clean_input(" ".join(sys.argv[1:]))
        if task:
            handle(task, history)
        return

    # ---- interactive mode --------------------------------------------------
    while True:
        try:
            query = clean_input(input("\nYou: "))
        except (EOFError, KeyboardInterrupt):
            # Ctrl+C or Ctrl+D at the prompt means quit. Handling it here gives
            # a tidy goodbye instead of a KeyboardInterrupt traceback.
            print("\nGoodbye.")
            return

        if not query:
            continue  # they just pressed Enter - re-prompt without an API call

        if query.lower() in QUIT_WORDS:
            print("Goodbye.")
            return

        handle(query, history)


# Only runs when this file is executed directly, never when imported.
if __name__ == "__main__":
    main()
