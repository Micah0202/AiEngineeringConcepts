"""
The public front door of the package.

Everything else - the tools, the security layer, the prompts - is internal
plumbing. A caller only needs these two.
"""

from coding_agent.agent import run_agent
from coding_agent.prompts import build_greeting

__all__ = ["run_agent", "build_greeting"]
