"""Process entry: env -> client -> app -> uvicorn (medium design section 4)."""
import os
from collections.abc import Callable, Mapping
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from medium.api import create_medium_app
from providers.anthropic_client import AnthropicClient
from skeleton.personas.llm import LLMClient

DEFAULT_MODEL = "claude-haiku-5-5"
DEFAULT_STORE = "crypt-store"

ClientFactory = Callable[[str], LLMClient]


def build_app(
    env: Mapping[str, str] | None = None,
    client_factory: ClientFactory = AnthropicClient.from_env,
) -> FastAPI:
    """Build the app. A missing ANTHROPIC_API_KEY raises ProviderError naming the variable."""
    env = os.environ if env is None else env
    llm = client_factory(env.get("MEDIUM_MODEL") or DEFAULT_MODEL)
    store = Path(env.get("CRYPT_STORE") or DEFAULT_STORE)
    return create_medium_app(store=store, llm=llm)


def main() -> None:
    app = build_app()
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
