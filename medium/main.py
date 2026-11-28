"""Process entry: env -> client -> app -> uvicorn (medium design section 4)."""
import functools
import os
from collections.abc import Callable, Mapping
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from medium.api import create_medium_app
from providers.select import client_from_env, max_tokens_from_env, with_max_tokens
from skeleton.personas.llm import LLMClient

DEFAULT_STORE = "crypt-store"

ClientFactory = Callable[[str | None], LLMClient]


def build_app(
    env: Mapping[str, str] | None = None,
    client_factory: ClientFactory | None = None,
) -> FastAPI:
    """Build the app. Provider and model come from ``env`` (MEDIUM_PROVIDER, MEDIUM_MODEL).

    A missing provider key raises ProviderError naming the variable.
    """
    env = os.environ if env is None else env
    factory = client_factory or functools.partial(client_from_env, env=env)
    llm = with_max_tokens(factory(env.get("MEDIUM_MODEL") or None), max_tokens_from_env(env))
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
