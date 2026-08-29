"""
★ THE REACT LOOP ★

Reason -> Act -> Observe -> Repeat -> Final Answer.

This is the whole agent, and it is deliberately about 60 lines of real logic.
Everything clever lives elsewhere: security.py decides what is allowed, tools/
does the work, schemas.py describes it. This file just runs the cycle.

Mapping the assignment's five words onto the code:

    Reason        message.content         - the model's thinking, printed for the user
    Act           message.tool_calls      - the structured request it emits
    Observe       {"role": "tool", ...}   - what WE append after running the tools
    Repeat        for step in range(...)  - the loop, capped by MAX_STEPS
    Final Answer  no tool_calls -> return - the only normal way out
"""

import json
from functools import lru_cache
from typing import NamedTuple

from pydantic import ValidationError

from coding_agent.client import get_client_and_model
from coding_agent.config import MAX_STEPS, MAX_TOKENS
from coding_agent.prompts import build_system_prompt
from coding_agent.schemas import TOOL_ARG_MODELS, TOOL_MENU
from coding_agent.tools import TOOL_FUNCTIONS

# How much of a tool's output to show the USER on screen. The MODEL always
# receives the full text - this only keeps the terminal readable.
PREVIEW_CHARS = 400


@lru_cache(maxsize=1)
def _client_and_model():
    """
    Build the client once and reuse it.

    weather_app called get_client_and_model() on every turn, which constructs a
    fresh HTTP connection pool each time. lru_cache makes it a one-off.
    """
    client, model, _provider = get_client_and_model()
    return client, model


def _preview(text: str) -> str:
    """Shorten a tool result for on-screen display only."""
    text = text.strip()
    if len(text) <= PREVIEW_CHARS:
        return text
    return text[:PREVIEW_CHARS] + f"\n     ... ({len(text):,} chars total)"

#convert the models reply into a plain dict for the conversation  history .
def _assistant_message(message) -> dict:
    """
    Convert the model's reply into a plain dict for the conversation history.

    ---------------------------------------------------------------------------
    ★ THE BUG WE ARE DELIBERATELY NOT REPEATING.

    weather_app/agent.py writes this line:

        "arguments": json.dumps(call.function.arguments)     # ← WRONG

    call.function.arguments is ALREADY a JSON string. Encoding it again gives:

        before:  {"location": "Tokyo"}
        after:  "{\\"location\\": \\"Tokyo\\"}"

    The tool still runs, because the executor reads the original object. But
    the HISTORY sent back to the model contains escaped gibberish, so on the
    next turn the model sees its own request mangled. For multi-step work -
    exactly what a coding agent does - that quietly degrades everything.

    Pass the string through untouched.
    ---------------------------------------------------------------------------
    """
    return {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,  # already JSON text
                },
            }
            for call in message.tool_calls
        ],
    }


class ToolRun(NamedTuple):
    """One completed tool call, ready to be displayed and recorded."""

    reasoning: str | None   # the model's "why", pulled out of the arguments
    display: str            # e.g. write_file(path='main.py') - for the screen
    observation: str        # the tool's full output - for the model


#Run one tool the model asked for, and return its output as a string.
def _execute_tool(call) -> ToolRun:
    """
    Run one tool the model asked for, and return its output as a string.

    ---------------------------------------------------------------------------
    ★ EVERY PATH RETURNS A STRING. There is exactly one variable and one return
      type, so the other weather_app bug - assigning `result` in one branch and
      reading `tool_result` in another, which is a NameError waiting to happen -
      cannot occur here.

    And every failure is RETURNED, never raised. A raised exception would abort
    the whole run; a returned string becomes the next Observe step, and the
    model gets a chance to correct itself.
    ---------------------------------------------------------------------------
    """
    name = call.function.name

    # 1. Does this tool exist?
    if name not in TOOL_FUNCTIONS:
        available = ", ".join(sorted(TOOL_FUNCTIONS))
        return ToolRun(
            None, name, f"Error: unknown tool '{name}'. Available tools: {available}."
        )

    # 2. Are the arguments valid JSON? The model generates them as text, so
    #    they can be malformed.
    try:
        raw_arguments = json.loads(call.function.arguments)
    except json.JSONDecodeError as err:
        return ToolRun(
            None, name, f"Error: arguments for {name} were not valid JSON: {err}"
        )

    # 3. Do they match the schema? Pydantic catches a missing or wrongly-typed
    #    field BEFORE it can reach the filesystem. This is also what makes the
    #    `reasoning` field mandatory - a tool call without it fails right here.
    try:
        validated = TOOL_ARG_MODELS[name].model_validate(raw_arguments)
    except ValidationError as err:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()
        )
        return ToolRun(
            None, name, f"Error: invalid arguments for {name} -> {problems}"
        )

    arguments = validated.model_dump()

    # ★ Pull `reasoning` OUT before calling the function.
    #   It exists purely to force the model to explain itself; the tools
    #   themselves know nothing about it and keep their clean signatures.
    reasoning = arguments.pop("reasoning", None)

    # A short one-line form of the call, for the screen. Long values (a whole
    # file's contents) are shortened so the trace stays readable.
    display = f"{name}({', '.join(f'{k}={_short(v)!r}' for k, v in arguments.items())})"

    # 4. Run it. ** spreads the dict into keyword arguments:
    #    read_file(path="main.py").
    try:
        observation = TOOL_FUNCTIONS[name](**arguments)
    except Exception as err:  # noqa: BLE001 - a crashing tool must not kill the run
        observation = f"Error: the {name} tool crashed: {type(err).__name__}: {err}"

    return ToolRun(reasoning, display, observation)


def _short(value, limit: int = 60) -> str:
    """Shorten one argument value for the on-screen call trace."""
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"... (+{len(text) - limit} chars)"


def run_agent(user_query: str, history: list[dict] | None = None) -> str:
    """
    Run the full Reason-Act-Observe loop for ONE user request.

    `history` is previous {"role": "user"/"assistant"} turns, so follow-up
    questions work. We READ it but never modify it - the caller owns its own
    list and appends to it itself.

    (weather_app did the opposite: run_agent_turns() appended to the caller's
    list as a side effect, which is why app.py had a commented-out line warning
    you not to append again. Returning a value and letting the caller decide is
    easier to follow.)
    """
    client, model = _client_and_model()

    # `working` is this request's scratchpad. It grows with every tool call and
    # is thrown away at the end - only the final answer goes into `history`.
    working: list[dict] = [
        {"role": "system", "content": build_system_prompt()},
        *(history or []),
        {"role": "user", "content": user_query},
    ]

    for step in range(1, MAX_STEPS + 1):
        print(f"\n  [step {step}/{MAX_STEPS}]")

        # ═══ the model thinks and decides ═══════════════════════════════════
        response = client.chat.completions.create(
            model=model,
            messages=working,
            tools=TOOL_MENU,       # ★ without this, tool calling is impossible
            max_tokens=MAX_TOKENS,
        )
        message = response.choices[0].message

        # ═══ FINAL ANSWER ══════════════════════════════════════════════════
        # No tool calls means the model is done. This is the only normal exit.
        # We return WITHOUT printing here - the caller prints the answer, and
        # printing it in both places would show it twice.
        if not message.tool_calls:
            return message.content or "(the model returned an empty answer)"

        # ═══ REASON (the free-text half) ═══════════════════════════════════
        # Narration the model wrote alongside its tool calls. Usually None with
        # gpt-4o-mini - the reliable reasoning comes from the required
        # `reasoning` argument on each tool, printed below.
        #
        # Labelled "thinking" rather than "reason" so the two are never
        # confused in the trace when both happen to appear.
        if message.content:
            print(f"  thinking: {message.content.strip()}")

        # ═══ ACT ═══════════════════════════════════════════════════════════
        # Record the model's OWN request first. The API rejects a "tool"
        # message unless the assistant message that asked for it comes
        # immediately before - skip this and the next call fails with a 400.
        working.append(_assistant_message(message))

        # The inner loop handles BREADTH: several tools requested in one turn.
        # The outer loop handles DEPTH: several turns in a row.
        for call in message.tool_calls:
            run = _execute_tool(call)

            # The model's "why", now guaranteed to exist because it is a
            # required argument on every tool. This is the visible Reason step.
            if run.reasoning:
                print(f"  reason: {run.reasoning}")

            print(f"  -> {run.display}")
            print(f"  <- {_preview(run.observation)}")

            # ═══ OBSERVE ═══════════════════════════════════════════════════
            # tool_call_id pairs this answer with its request, which is what
            # keeps things straight when several tools ran at once.
            working.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": run.observation,
                }
            )

        # ═══ REPEAT ════════════════════════════════════════════════════════
        # Loop back. The model now sees the results and decides what is next.

    # ═══ the safety net ════════════════════════════════════════════════════
    # Reached only if MAX_STEPS ran out without a final answer. Without this
    # cap, a confused model loops forever and burns the API budget.
    return (
        f"Stopped after {MAX_STEPS} steps without finishing. "
        f"The work done so far is still in the workspace - "
        f"try asking for a smaller piece of the task."
    )
