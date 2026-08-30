# =============================================================================
# paths.py - THE SECURITY GATE FOR THE FILESYSTEM.
#
# This file answers two questions, and every file tool must ask them before
# touching the disk:
#
#     1. "Is this file off limits?"        -> is_blocked_path()
#     2. "Where does this path really go?" -> resolve_work_path()
#
# config.py DRAWS the sandbox boundary (get_work_dir). This file ENFORCES it.
#
# Remember: the LLM can only ASK for a file. It never opens anything itself.
# So this one module is the complete list of files the agent can reach.
# =============================================================================

from fnmatch import fnmatch   # simple wildcard matching: fnmatch("a.log", "*.log") -> True
from pathlib import Path

from config.config import get_work_dir


#what paths we dont want our agent to read
#
# These are wildcard patterns, checked against the whole normalized path.
#   *  matches any characters
#   ?  matches one character
#
#
#   1. MISSING COMMA after ".env.*" below. Python silently joins two adjacent
#      string literals, so ".env.*" ".pem" becomes the single useless pattern
#      ".env.*.pem". The list has 8 entries, not 9, and .pem files are NOT
#      protected at all.
#
#   2. ".key" / ".secret" have no leading "*", so they only match a file named
#      EXACTLY ".key". A real file called "server.key" sails straight through.
#      They need to be "*.key" and "*.secret".
#
# What is ACTUALLY blocked today (measured, not assumed):
#      .env  .key  .secret  .git  .git/**  *.log  *.p12
# What gets through today:
#      secrets.pem   server.key   api.secret
#      .env.local    .env.production   config/.env
BLOCKED_PATH_PATTERNS = [
    ".env",
    ".env.*"  ,    
    ".pem",
    ".key",
    ".secret",
    ".git",
    ".git/**",
    "*.log",
    "*.p12"
]


# -----------------------------------------------------------------------------
# WHAT : Rewrites a path into one single, predictable spelling.
# INPUT: path (str) - a path as the model wrote it, any style.
#                     e.g. "./main.py", "src\\a\\b.py", "main.py"
# OUTPUT: str       - forward slashes, no leading "./"
#                     e.g. "main.py",   "src/a/b.py",   "main.py"
#
# WHY IT EXISTS: the pattern matching below is plain text comparison, so the
# same file must always produce the same string. Without this, "./secrets.log"
# and "secrets.log" are different text, and only one of them would be caught -
# a trivial way to slip past the blocklist.
#
# HOW: Path(path) parses it, .as_posix() re-prints it with forward slashes
# (so Windows backslashes are normalised away), then the "./" prefix is
# trimmed by hand because as_posix() keeps it.
# -----------------------------------------------------------------------------
def normalize_path(path: str) -> str:
    normalized = Path(path).as_posix()#converts path object into a string with forward slashes . 
    if normalized.startswith("./"):
        normalized = normalized[2:] #pick  everything after ./
    return normalized


# -----------------------------------------------------------------------------
# WHAT : Decides whether a path is on the forbidden list.
# INPUT: path (str) - the path the model asked for, e.g. "secrets.pem"
# OUTPUT: bool      - True  = refuse it
#                     False = allowed to continue
#
# HOW: normalize it first, then test it against every pattern.
# any(...) stops at the first match, so one hit is enough to block.
#
# NOTE this checks the NAME ONLY. It has no idea where the file physically is;
# that is resolve_work_path's job. The two checks are separate on purpose:
#   is_blocked_path   -> "is this KIND of file forbidden?"   (.env, keys, logs)
#   resolve_work_path -> "is this LOCATION allowed?"          (inside the sandbox)
# A file can pass one and fail the other, so callers must run BOTH.
#
# LIMITATION: patterns are matched against the full path, so "config/.env"
# is NOT caught by the ".env" pattern. A pattern like "**/.env", or comparing
# Path(path).name instead, would catch nested files too.
# -----------------------------------------------------------------------------
def is_blocked_path(path: str) -> bool:
    normalized = normalize_path(path)
    return any(fnmatch(normalized, pattern) for pattern in BLOCKED_PATH_PATTERNS)


# -----------------------------------------------------------------------------
# WHAT : Turns a path the model asked for into a real, absolute path we are
#        willing to open - or refuses it.
# INPUT: path (str)   - relative to the work dir, e.g. "main.py", "src/app.py"
# OUTPUT: Path        - the absolute location inside the sandbox
#         or raises ValueError if the path points outside it.
#
# ★ THE KEY IDEA: RESOLVE FIRST, COMPARE AFTER.
#
# It is tempting to check this with text:
#       if not str(work_dir / path).startswith(str(work_dir))   # <- WRONG
#
# That is broken, because the STRING "workspace/../../.env" really does start
# with "workspace" - so it passes, and then the operating system cheerfully
# walks up two folders to your real .env.
#
# .resolve() fixes it by asking the OS for the true final location: every ".."
# is collapsed and every symlink followed BEFORE we compare. Measured results:
#
#       "main.py"                -> ...\workspace\main.py        OK
#       "sub/dir/app.py"         -> ...\workspace\sub\dir\app.py OK
#       "../../.env"             -> ValueError                   blocked
#       "C:/Windows/System32/x"  -> ValueError                   blocked
#
# The absolute-path case works because pathlib deliberately lets an absolute
# path replace the base when joined, so (work_dir / "C:/Windows") becomes
# "C:/Windows" - and the check below is what rejects it.
#
# relative_to() raises ValueError when the candidate is NOT underneath
# work_dir, so the try/except IS the boundary test. Its return value is thrown
# away; we only care whether it raised.
# -----------------------------------------------------------------------------
#will resolve the path prpperly so that new files are only created inside working directory
#IMPORTANT -  THIS  FUNCTIONJ EITHER RAISES A PATH object OR returns a ValueError . 
def resolve_work_path(path: str) -> Path:
    # get_work_dir() already returns a resolved absolute path.
    work_dir = get_work_dir()

    # Create the sandbox if this is the first run. exist_ok=True means "do
    # nothing if it already exists" rather than raising.
    work_dir.mkdir(parents=True, exist_ok=True)

    candidate = (work_dir / path).resolve()

    try:
        candidate.relative_to(work_dir)
    except ValueError as e:
        raise ValueError(f"Path escapes working directory")

    return candidate
