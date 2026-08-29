"""
Small shared bits used by more than one tool. Not a tool itself - the leading
underscore marks it as internal to the tools package.
"""

from coding_agent.config import MAX_TOOL_OUTPUT_CHARS


def truncate(text: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """
    Cut oversized tool output down to size before it goes back to the model.

    Why this matters: every tool result is appended to the conversation and
    re-sent on EVERY subsequent turn. One 500KB file read would blow the
    context window and make every following request expensive.

    The marker is important. Silently truncating would leave the model
    believing it had seen the whole thing; telling it the real size lets it
    narrow its next read instead.
    """
    if len(text) <= limit:
        return text

    return (
        text[:limit]
        + f"\n\n... [truncated: showing {limit:,} of {len(text):,} characters]"
    )
