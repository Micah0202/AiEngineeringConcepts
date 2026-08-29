"""
LAYER 3 - HUMAN IN THE LOOP.

Deliberately tiny, and deliberately pessimistic.

Two design decisions worth understanding:

1. THE DEFAULT IS NO.
   Pressing Enter denies. Typing anything other than "y" denies. The dangerous
   path must be the one that takes deliberate effort.

2. A DENIAL IS AN OBSERVATION, NOT A CRASH.
   The tools that call this return a string like "DENIED by user: ..." back to
   the model as a normal tool result. The model then SEES the refusal and can
   adapt ("understood, I will not delete that - here is another approach").
   Raising an exception would kill the whole run and teach the model nothing.
"""

import sys

# Set to True only by tests, so an automated run never blocks on input().
# Production code never touches this.
AUTO_DENY_FOR_TESTS = False


def request_approval(action: str, detail: str) -> bool:
    """
    Ask the human to approve one dangerous action.

    Returns True only if they explicitly type 'y'.
    """
    if AUTO_DENY_FOR_TESTS:
        return False

    print()
    print("  " + "=" * 62)
    print("  APPROVAL REQUIRED")
    print("  " + "-" * 62)
    print(f"  Action : {action}")
    print(f"  Detail : {detail}")
    print("  " + "=" * 62)

    try:
        choice = input("  Allow this? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        # No terminal attached, or the user hit Ctrl+C at the prompt.
        # Both mean "we could not get consent", so we refuse.
        print("\n  -> DENIED (no input available)")
        return False

    approved = choice == "y"
    print(f"  -> {'APPROVED' if approved else 'DENIED'}")
    sys.stdout.flush()
    return approved
