from jinja2 import Environment, FileSystemLoader, select_autoescape

from weather_agent.schemas import tool_catalog
from weather_agent.config import PROMPTS_DIR

#jinja environment object 
_env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=select_autoescape(),
)

# =========================================================================
# FUNCTION 1: The worker.
# It takes a template file name + some values, and gives back finished text.
# It is "generic" - it does not care WHICH template or WHICH values.
# =========================================================================
def render_template(name: str, **context) -> str:
    # `name`      -> the file to open, e.g. "system.jinja"
    # `**context` -> COLLECTS all the extra named values into one dict.
    #
    #    If someone calls:  render_template("system.jinja", tools=[...], extra_guidance="")
    #    then inside here:  name    == "system.jinja"
    #                       context == {"tools": [...], "extra_guidance": ""}

    # Step 1: _env.get_template(name) -> finds and opens the file.
    # Step 2: .render(**context)      -> SPREADS the dict back out as named
    #                                    values and fills in the blanks
    #                                    ({{tool.name}}, {% if %}, etc.)
    # Note: ** is used twice here, in opposite ways.
    #   In the line above (**context) it PACKS values into a dict.
    #   In the line below (**context) it UNPACKS the dict back into values.
    return _env.get_template(name).render(**context)
    # returns a plain string, e.g. "You are a helpful weather assistant..."


# =========================================================================
# FUNCTION 2: Builds the prompt for the LLM (the AI model).
# This is the text the model reads to know how it should behave.
# =========================================================================
def build_system_prompt(
    # The lone `*` means: everything after this MUST be passed by name.
    #   build_system_prompt(extra_guidance="speak French")  -> OK
    #   build_system_prompt("speak French")                 -> TypeError
    # This stops confusing calls where you cannot tell what the value means.
    *,
    # Optional extra rules. Default is "" (empty), so normally nothing is added.
    extra_guidance: str = "",
) -> str:
    return render_template(
        # Which file to use. Only THIS file knows the template's real name.
        "system.jinja",

        # tool_catalog() gives -> [{"name": "lookup_weather", "description": "..."}]
        # The template loops over this to print the list of tools.
        # We call it fresh every time, so if you add a new tool,
        # the prompt updates by itself. No edit needed here.
        tools=tool_catalog(),

        # Passed to the {% if extra_guidance %} block in the template.
        # Empty string = the block is skipped completely.
        extra_guidance=extra_guidance,
    )
    # Result: ~1125 characters of finished text, sent to the model
    # by agent.py as {"role": "system", "content": <this text>}


# =========================================================================
# FUNCTION 3: Builds the welcome text for the USER (not for the model).
# It is shown in the Streamlit sidebar under "About this project".
# =========================================================================
def build_greeting_prompt() -> str:
    # No extra values are passed, because greeting.jinja has no blanks to fill.
    # It is plain text, so this just reads the file and returns it.
    return render_template("greeting.jinja")
    # returns: "Hi! I'm a small agent that can help you with live weather data..."