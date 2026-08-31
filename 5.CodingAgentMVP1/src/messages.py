# =============================================================================
# messages.py - small helpers for READING the conversation list.
#
# An agent's conversation is a list of message objects that grows every turn:
#
#     [SystemMessage, HumanMessage, AIMessage(tool_calls), ToolMessage, AIMessage]
#
# The agent loop needs to keep asking questions about that list - "what was the
# final answer?", "what did the last tool say?", "print this so I can debug it".
# Rather than scatter that fiddly digging through the loop, it all lives here.
#
# Nothing in this file talks to the model or touches the disk. These are pure
# lookups: a list goes in, a string comes out.
# =============================================================================

from typing import Any
from langchain.messages import AIMessage, ToolMessage, SystemMessage, HumanMessage


# -----------------------------------------------------------------------------
# WHAT  : Wraps plain text in the dict shape the chat API expects for a user turn.
# INPUT : text (str)            - what the human typed, e.g. "Create hello.py"
# OUTPUT: dict[str, str]        - {"role": "user", "content": "Create hello.py"}
#
# NOTE this returns an OpenAI-style DICT, while everything else in this file
# works with LangChain message OBJECTS (HumanMessage, AIMessage, ...).
# LangChain accepts both, so it works - but mixing the two styles in one list
# makes the list harder to reason about. HumanMessage(content=text) would be
# the consistent choice.
# -----------------------------------------------------------------------------
def user_input(text: str) -> dict[str, str]:
    """OpenAI style dict for user input"""
    return { "role" : "user", "content": text}


# -----------------------------------------------------------------------------
# WHAT  : Finds the model's most recent REAL answer - the final text meant for
#         the human, skipping any turn where the model only asked for a tool.
# INPUT : messages (list) - the whole conversation so far
# OUTPUT: str            - the answer text, or "" if there is no answer yet
#
# WHY THE SKIPPING MATTERS:
# When the model requests a tool, it sends an AIMessage with tool_calls and
# usually EMPTY content. Taking "the last AIMessage" blindly would hand the
# user a blank string. This walks backwards past those until it finds one that
# actually says something.
#
# Measured on a real conversation
#   [system, human, ai(tool_call), tool, ai("Done - I created hello.py")]:
#       -> 'Done - I created hello.py for you.'
#   same list cut short at the tool result (no final answer yet):
#       -> ''            <- the tool-call AIMessage was correctly skipped
#   empty list:
#       -> ''
#
# THE TWO CONTENT SHAPES:
#   str  - the normal case. Returned as-is.
#   list - some providers return "content blocks" like
#            [{"type": "text", "text": "part one"}, {"type": "image", ...}]
#          Only the text blocks are kept and joined with newlines:
#            -> 'part one\npart two'
#
# reversed() walks newest-first, so the FIRST match found is the most recent.
# -----------------------------------------------------------------------------
#IMPORTANT - WANT TO  RETURN THE PLAIN TEXT STRING OF THE LAST AI MESSAGE THAT IS NOT A TALL  CALL 
def last_ai_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        # Not from the model at all (human / system / tool) - keep looking.
        #if current message is not  an AI MESSAGE
        if not isinstance(message, AIMessage):
            continue
        # From the model, but it was only asking for a tool - keep looking.
        # getattr(..., None) is used because not every message object is
        # guaranteed to have the attribute; this avoids an AttributeError.
        #IF tool_calls attribute is none then continue
        if getattr(message, "tool_calls", None):
            continue
        content = message.content

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            #crate a new list parts
            parts = [
                #extracting all  the text inside content 
                block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
            ]
            return "\n".join(part for part in parts if part)
    # Searched the whole list and found nothing the model actually said.
    return ""


# -----------------------------------------------------------------------------
# WHAT  : Finds the output of the most recently executed tool.
# INPUT : messages (list) - the whole conversation so far
# OUTPUT: str            - the tool's result text, or "" if no tool has run
#
# WHY IT EXISTS: sometimes the model runs a tool and then stops without writing
# a closing sentence, so last_ai_text() returns "". Falling back to the last
# tool result means the user still sees something useful instead of a blank
# screen. Measured: 'Created hello.py (1 line).'
#
# The isinstance check on the way out is defensive - ToolMessage content is
# normally a str, but str(content) guarantees this function always returns a
# string, so the caller never has to type-check the result.
# -----------------------------------------------------------------------------
def last_tool_text(messages: list[Any]) -> str:
    """"
    Returns the content of the most recent tool result - useful when the model skips a chat reply.
    """
    for message in reversed(messages):
        if isinstance(message, ToolMessage):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""


# -----------------------------------------------------------------------------
# WHAT  : Turns ONE message into a single readable line for logs / trace output.
# INPUT : message - any LangChain message object
# OUTPUT: str     - "<role><extra>: <content on one line>"
#
# Measured output for a full conversation:
#     system (system): You are a coding agent.
#     human (human): Create hello.py
#     ai tools=[write_file]:
#     tool tool_call_id=call_1: Created hello.py (1 line).
#     ai: Done - I created hello.py for you.
#
# HOW THE ROLE IS DERIVED:
#     type(message).__name__   ->  "AIMessage"
#     .replace("Message", "")  ->  "AI"
#     .lower()                 ->  "ai"
# Reading the class name means a new message type is labelled automatically,
# with no lookup table to keep in sync.
#
# The `extra` field adds whatever is most useful per type: which tools were
# requested, which request a result belongs to, or just a role marker.
#
# The \n -> space replacement keeps every message on ONE line, so a multi-line
# file write does not wreck the shape of the trace.
# -----------------------------------------------------------------------------
def describe_message(message) -> str:
    """Useful for logging and debugging"""
    role = type(message).__name__.replace("Message", "").lower()
    content = message.content
    preview = content if isinstance(content, str) else str(content)
    preview = preview.replace("\n", " ")
    extra = ""

    if isinstance(message, AIMessage) and message.tool_calls:
        # tool_calls are dicts here, so .get("name", "?") is used rather than
        # attribute access - "?" if a malformed call has no name.
        #fetch the name of  the tool  being called 
        names = ", ".join(call.get("name", "?") for call in message.tool_calls)
        extra = f" tools=[{names}]"

    #if message is a reply from tool     
    if isinstance(message, ToolMessage):
        # Shows WHICH request this result answers - the pairing that matters
        # when several tools ran in the same turn.
        extra = f" tool_call_id={message.tool_call_id}"
    if isinstance(message, SystemMessage):
        extra = " (system)"
    if isinstance(message, HumanMessage):
        extra = " (human)"
    return f"{role}{extra}: {preview}"
