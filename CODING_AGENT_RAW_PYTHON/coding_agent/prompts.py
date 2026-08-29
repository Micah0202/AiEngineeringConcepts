"""
The prompt factory: turns template files on disk into finished strings.

This is the ONLY module that imports jinja2 or knows that a file called
"system.jinja" exists. Everything downstream just calls build_system_prompt().
Rename a template, or switch template engines entirely, and only this file
changes.
"""

from jinja2 import Environment, FileSystemLoader, select_autoescape

from coding_agent.config import TEMPLATES_DIR
from coding_agent.schemas import tool_catalog

# Built ONCE, at import. The Environment caches compiled templates, so the
# template is parsed a single time and reused for every render afterwards.
# Creating a new Environment per render would recompile every time.
_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    # Removes the newline after a {% %} tag, so the {% for %} loop does not
    # leave blank lines scattered through the prompt.
    trim_blocks=True,
    # Strips whitespace before a {% %} tag, so template logic can be indented
    # for readability without that indentation reaching the output.
    lstrip_blocks=True,
    # Extension-based HTML escaping. It only turns on for .html/.htm/.xml, so
    # it is OFF for our .jinja files - which is what we want. If it were on,
    # every apostrophe and quote in the prompt would become &#39; and the model
    # would have to read entity codes instead of English.
    autoescape=select_autoescape(),
)


def _render(name: str, **context) -> str:
    """
    Load a template and fill in its blanks.

    Note ** used in both directions in two lines: **context PACKS the loose
    keyword arguments into a dict on the way in, and **context UNPACKS that
    dict back into keyword arguments on the way out. Because it collects
    everything, this function never needs to know what any template wants.
    """
    return _env.get_template(name).render(**context)


def build_system_prompt(*, extra_guidance: str = "") -> str:
    """
    The instructions the MODEL reads. This is the agent's behaviour.

    The lone `*` makes extra_guidance keyword-only, so a call site must say
    build_system_prompt(extra_guidance="...") and cannot pass a bare string
    whose meaning is impossible to guess when reading the code.

    tool_catalog() is called fresh on every render, so the tool list inside the
    prompt is always generated from the same TOOL_MENU that the API receives.
    Add a seventh tool and this prompt updates itself - no edit needed here.
    """
    return _render(
        "system.jinja",
        tools=tool_catalog(),
        extra_guidance=extra_guidance,
    )


def build_greeting() -> str:
    """
    The welcome text shown to the HUMAN when the CLI starts.

    This never goes to the model. It is named build_greeting rather than
    build_greeting_prompt precisely so nobody mistakes it for a prompt.
    """
    return _render("greeting.jinja")
