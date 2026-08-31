import os
from dotenv import load_dotenv
from dataclasses import dataclass
from langchain_openai import ChatOpenAI


load_dotenv()


@dataclass(frozen=True)
class Provider:
    name: str
    env_var: str
    is_free: bool 
    base_url: str | None 
    model: str

PROVIDERS = [
    Provider(
        "OpenAI",
        "OPENAI_API_KEY",
        False,
        None,
        "gpt-4o-mini",
    )
]

def select_provider() -> Provider:
    for provider in PROVIDERS:
        if os.getenv(provider.env_var):
            return provider

    #iterated thgrough all providers an was unable to  find api key
    raise RuntimeError("No provider found")

def build_chat_model() -> tuple[ChatOpenAI, Provider]:
    provider = select_provider()
    kwargs: dict = {
        "model": provider.model,
        "api_key": os.getenv(provider.env_var),
    }
    if provider.base_url is not None:
        kwargs["base_url"] = provider.base_url
    return ChatOpenAI(**kwargs), provider