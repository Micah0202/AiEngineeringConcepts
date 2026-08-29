"""
Answers ONE question for the whole app: which LLM am I talking to, and how do I
connect to it?

This is the same pattern as weather_app/weather_agent/client.py. Keeping the
provider details in one file means agent.py never has to know about API keys,
.env files, or base URLs - and swapping OpenAI for Groq is a one-file change.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from coding_agent.config import MODEL

# Reads the .env file into os.environ.
# With no arguments, python-dotenv walks UP the folder tree from this file
# until it finds a .env - so the repo-root .env is picked up automatically,
# whichever directory you launch the agent from.
load_dotenv()


@dataclass(frozen=True)
class Provider:
    """
    One LLM provider described as pure DATA.

    frozen=True makes it immutable: `provider.model = "gpt-4"` raises instead of
    silently changing shared config underneath you.
    """

    name: str
    env_var: str          # which environment variable holds the API key
    base_url: str | None  # None = real OpenAI; a URL = an OpenAI-compatible server
    model: str


# The catalogue. ORDER MATTERS - this is a priority list, and the first
# provider whose key is actually present wins.
#
# Groq is listed but commented out; uncomment it and set GROQ_API_KEY to switch
# with zero other code changes. That works because Groq speaks the same
# protocol, so only `base_url` differs.
PROVIDERS = [
    Provider(
        name="OpenAI",
        env_var="OPENAI_API_KEY",
        base_url=None,
        model=MODEL,
    ),
    # Provider(
    #     name="Groq",
    #     env_var="GROQ_API_KEY",
    #     base_url="https://api.groq.com/openai/v1",
    #     model="llama-3.3-70b-versatile",
    # ),
]


def select_provider() -> Provider:
    """
    Return the first provider whose API key is actually set in the environment.

    Raising here - rather than letting the request fail later with a confusing
    401 - means a missing key is reported at startup with a message that says
    exactly what to do about it.
    """
    for provider in PROVIDERS:
        if os.getenv(provider.env_var):
            return provider

    expected = ", ".join(p.env_var for p in PROVIDERS)
    raise RuntimeError(
        f"No API key found. Add one of these to your .env file: {expected}"
    )


def get_client_and_model() -> tuple[OpenAI, str, Provider]:
    """
    Build a connected client.

    Returns a 3-tuple: (client, model_name, provider).
    The third item is there so the CLI can print "Provider: OpenAI (gpt-4o-mini)".

    The if/else below is the entire provider-swap mechanism: passing base_url
    points the OpenAI SDK at a different server while every call site keeps
    using the identical client.chat.completions.create(...) interface.
    """
    provider = select_provider()
    api_key = os.getenv(provider.env_var)

    if provider.base_url is None:
        client = OpenAI(api_key=api_key)
    else:
        client = OpenAI(api_key=api_key, base_url=provider.base_url)

    return client, provider.model, provider
