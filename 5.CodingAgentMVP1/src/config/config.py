# =============================================================================
# config.py - every setting for the agent, in one place.
#
# This file holds DATA and a couple of tiny lookup helpers. No agent logic, no
# tools, no LLM calls. If you want to know "what is this agent allowed to do
# and where does it work?", this is the only file you need to read.
# =============================================================================

import os                       # read environment variables (os.getenv)
from pathlib import Path        # build file paths that work on Windows AND Mac/Linux

from dotenv import load_dotenv  # reads a .env file into the environment


# Runs ONCE, the moment this file is first imported.
# It finds the nearest .env file (walking UP the folder tree from here) and
# copies every KEY=value line into os.environ.
# After this line, os.getenv("ANYTHING") can see what is in .env.
load_dotenv()


# -----------------------------------------------------------------------------
# WHERE THINGS ARE
# -----------------------------------------------------------------------------

# Work out the project's top folder by walking UP from this file.
#
#   Path(__file__)  -> .../5.CodingAgentMVP1/src/config/config.py   (this file)
#   .resolve()      -> makes it absolute and removes any ".." or symlinks
#   .parent         -> .../src/config          (the folder holding this file)
#   .parent         -> .../src
#   .parent         -> .../5.CodingAgentMVP1   <- PROJECT_ROOT
#
# Three .parent hops because config.py sits three levels deep. Add a folder to
# that path and you must add another .parent here.
#
# WHY ANCHOR TO __file__ AND NOT THE CURRENT DIRECTORY?
# Because __file__ never changes. If we used os.getcwd(), the project root
# would silently become wrong depending on which folder you launched from -
# and for a sandbox path, "silently wrong" is dangerous.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# The "/" here is NOT division. pathlib overloads it to mean "join a path",
# so this reads almost like the path itself. It also inserts the correct
# separator for your OS ("\" on Windows, "/" elsewhere) so you never hardcode one.
PROMPTS_DIR = PROJECT_ROOT / "prompts"

DEFAULT_WORK_DIR = PROJECT_ROOT / "workspace" #the sandbox where all of our coding work will happen


# -----------------------------------------------------------------------------
# IDENTITY
# -----------------------------------------------------------------------------

# Shown in the CLI banner / prompts. Kept here so the name lives in one place.
AGENT_NAME = "AgCamp Coding Agent"


# -----------------------------------------------------------------------------
# SAFETY LIMITS
# -----------------------------------------------------------------------------

# The pattern on both lines below is: os.getenv(NAME, DEFAULT) wrapped in int().
#
#   os.getenv("X", "10")  -> returns the env var if set, otherwise the string "10"
#   int(...)              -> converts it to a number
#
# The int() is REQUIRED, not decoration. Environment variables are ALWAYS
# strings, even when they look like numbers. Without it you would get "10"
# instead of 10, and `calls > MAX_MODEL_CALLS_PER_RUN` would raise TypeError.
# Note the default is written as a STRING "10" for the same reason - so both
# branches hand int() the same type.

# The stop-the-loop cap. An agent that keeps calling the model forever burns
# your API budget with nothing to show for it, so we allow at most 10 model
# calls per user request.
MAX_MODEL_CALLS_PER_RUN = int(os.getenv("MAX_MODEL_CALLS_PER_RUN", "10"))

# The biggest file the agent may read: 1,000,000 bytes (about 1 MB).
# Reading a huge file would blow past the model's context window and make every
# following request slow and expensive - the whole conversation is re-sent each
# turn, so one giant read is a cost you pay over and over.
MAX_READ_BYTES = int(os.getenv("MAX_READ_BYTES", "1000000"))


# -----------------------------------------------------------------------------
# HUMAN IN THE LOOP
# -----------------------------------------------------------------------------

#default value is enabled . 1 or true or yes means true
def hitl_enabled() -> bool:
    # HITL = Human In The Loop: ask the user before doing anything destructive.
    #
    # Reading it right to left:
    #   os.getenv("HTIL_ENABLED", "true")  -> the env var, or "true" if unset
    #   .lower()                           -> "TRUE" and "True" both become "true"
    #   in {"1", "true", "yes"}            -> is it one of these? -> True / False
    #
    # A SET is used rather than a list because `in` on a set is a direct lookup,
    # and it reads clearly as "one of these accepted spellings".
    #
    # Note the default is "true": safety is ON unless you deliberately turn it
    # off. Anything unrecognised ("maybe", "", "off") also gives False - so an
    # unclear value disables approval rather than enabling it. Worth knowing.
    return os.getenv("HTIL_ENABLED", "true").lower() in {"1", "true", "yes"}


# -----------------------------------------------------------------------------
# THE SANDBOX PATH
# -----------------------------------------------------------------------------

def get_work_dir() -> Path:
    # Returns the one folder the agent is allowed to work inside.
    # An env var can point it somewhere else; otherwise the default is used.

    # os.getenv(..., "") gives "" when unset, so .strip() is always safe to call
    # (calling .strip() on None would raise AttributeError).
    # .strip() also means WORK_DIR="  " counts as "not set" rather than as a
    # folder literally named two spaces.
    override = os.getenv("WORK_DIR", "").strip()

    # An empty string is falsy in Python, so this is "if the user set one".
    if override:
        # .expanduser() turns a leading "~" into the real home folder.
        # .resolve()   makes it absolute and collapses any ".." segments.
        #
        # .resolve() is the important one for security: it is what turns
        # "workspace/../../secrets" into its true destination, so a later
        # "is this inside the sandbox?" check compares real paths and cannot be
        # fooled by a path that only LOOKS like it stays put.
        return Path(override).expanduser().resolve() # ~/Developer/workspce => /Users/john/Developer/workspce

    # No override: fall back to <project>/workspace, resolved for the same reason.
    return DEFAULT_WORK_DIR.resolve()
