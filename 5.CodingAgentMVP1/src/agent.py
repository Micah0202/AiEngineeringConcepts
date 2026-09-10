#will  call the human in the loop  middleware here 
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langgraph.checkpoint.memory import InMemorySaver

from config.config import MAX_MODEL_CALLS_PER_RUN, hitl_enabled
from middlewares import AuditMiddleware, ProtectionMiddleware, HITLMiddleware
from models import build_chat_model
from memory import make_checkpointer
from tools import ALL_TOOLS
from prompts import build_system_prompt
from schemas import TurnSummary


# =============================================================================
# INPUT : enable_hitl (bool) - keyword only, and REQUIRED (it has no default).
# OUTPUT: a plain Python list of middleware OBJECTS, ready to hand to
#         create_agent(middleware=...). Three items normally, four with HITL.
# =============================================================================
def build_middleware(
        # A bare * means EVERY argument after it must be passed BY NAME.
        #   build_middleware(enable_hitl=True)   OK
        #   build_middleware(True)               TypeError
        # It stops a bare True appearing at a call site with no clue what it means.
        *,
        enable_hitl:bool          # no default value -> the caller MUST supply it
)-> list :                        # -> list is the return type hint
    """
    Harness layers , outermost first.

    1. model-call cap
    2. Audit log
    3. payload guarding
    4. HITL on write/edit/run
    """
    # WHAT THAT DOCSTRING MEANS:
    #
    # "Layers" because middleware WRAP each other like onion skins rather than
    # running one after another. "Outermost first" is LangChain's rule: the
    # FIRST item in this list becomes the OUTERMOST wrapper, so it sees the
    # request first and the result last.
    #
    #     ModelCallLimit  ┐  outermost - counts the call before anything else
    #       Audit         │  logs whatever finally happened
    #         Protection  │  can refuse the payload
    #           HITL      │  innermost - asks the human right before the tool
    #             [ the actual tool runs here ]
    #
    # Order is a real decision, not cosmetic. Audit sits OUTSIDE Protection, so
    # a refusal by Protection still gets logged. Flip them and blocked calls
    # would vanish from your audit trail.

    # `layers: list = [...]` - the ": list" is just an annotation on a local
    # variable. Note each entry is CONSTRUCTED with (), so these are objects,
    # not classes.
    layers: list = [
        ModelCallLimitMiddleware(
            # The stop-the-loop cap from config.py. Without it a confused model
            # can loop forever and burn your API budget.
            run_limit=MAX_MODEL_CALLS_PER_RUN,
            exit_behavior="end" #what to  do  when the limits are exceeded
            # "end" = stop cleanly and return what we have, rather than raising.
        ),
        AuditMiddleware(),        # your class - writes a JSON line per tool call
        ProtectionMiddleware()    # your class - can refuse a tool call outright
    ]

    #if hitl is enabled
    # .append() adds to the END of the list, which makes HITL the INNERMOST
    # layer - the last gate before the tool actually runs. That is the right
    # place for it: the human is asked about the final, fully-checked call.
    if enable_hitl:
        layers.append(HITLMiddleware())

    return layers


# =============================================================================
# INPUT : all three are keyword only, and all three are OPTIONAL.
#   checkpointer    - where conversation state is saved. None -> make one.
#   enable_hitl     - True / False / None. None means "ask config".
#   extra_guidance  - extra text injected into the system prompt.
# OUTPUT: a fully assembled agent object, ready for .invoke(). Nothing has run
#         yet - this only builds it.
# =============================================================================
def build_agent(
    *,
    # "InMemorySaver | None" means "either an InMemorySaver or None".
    # "= None" makes it optional.
    checkpointer: InMemorySaver | None = None,
    # THREE possible values, which is the point of allowing None:
    #   True  -> force HITL on
    #   False -> force HITL off
    #   None  -> do not decide here; let config.py decide
    enable_hitl: bool | None = None,
    extra_guidance: str = "",
):
    # build_chat_model() returns a 3-tuple (client, model, provider) - here it
    # is unpacked into two names, and the leading underscore on _provider is the
    # convention for "I am not going to use this".
    model, _provider = build_chat_model()

    # A ternary: VALUE_IF_TRUE if CONDITION else VALUE_IF_FALSE.
    # Reads as: "if the caller did not say, ask config; otherwise obey them."
    # Note it tests `is None`, NOT `if not enable_hitl` - because False is a
    # deliberate "off" and must not be treated the same as "unspecified".
    use_hitl = hitl_enabled() if enable_hitl is None else enable_hitl

    return create_agent(
        model=model,                        # the LLM to talk to
        tools=ALL_TOOLS,                    # what the model is allowed to request
        # The system prompt is rendered NOW, once, and baked into the agent.
        system_prompt=build_system_prompt(extra_guidance=extra_guidance),
        # Our onion of layers from the function above.
        middleware=build_middleware(enable_hitl=use_hitl),
        # Forces every final answer into the TurnSummary shape (summary,
        # files_touched, status) instead of free text.
        response_format=ProviderStrategy(TurnSummary),
        # `a or b` returns a if it is truthy, otherwise b - the standard Python
        # idiom for "use what I was given, else make a default".
        # A checkpointer is REQUIRED for HITL: an interrupt has to save state
        # somewhere in order to be resumable.
        checkpointer=checkpointer or make_checkpointer(),
        name="Coding Agent",                # label used in traces and logs
    )
    