"""Process entry: env -> client (or offline) -> app -> uvicorn (design section 6)."""

import functools
import logging
import os
from collections.abc import Callable, Mapping
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from providers.errors import ProviderError
from providers.select import client_from_env, max_tokens_from_env, with_max_tokens
from skeleton.personas.llm import LLMClient, LLMRequest, LLMResponse

from .api import create_collector_app

DEFAULT_STORE = "crypt-store"
DEFAULT_PORT = "8001"  # the Medium uses 8000, so both can run side by side

ClientFactory = Callable[[str | None], LLMClient]

log = logging.getLogger(__name__)


class OfflineClient:
    """Stands in when no provider is configured. Every call fails, so the notice declines."""

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise ProviderError("no provider configured")


def _translate(env: Mapping[str, str]) -> dict[str, str]:
    """Copy of ``env`` in the names ``providers.select`` reads (it reads MEDIUM_*)."""
    out = {k: v for k, v in env.items() if not k.startswith("MEDIUM_")}
    for ours, theirs in (("COLLECTOR_PROVIDER", "MEDIUM_PROVIDER"), ("COLLECTOR_MODEL", "MEDIUM_MODEL")):
        if env.get(ours):
            out[theirs] = env[ours]
    return out


def build_app(
    env: Mapping[str, str] | None = None,
    client_factory: ClientFactory | None = None,
) -> FastAPI:
    """Build the app. A missing provider key falls back to ``OfflineClient``."""
    env = os.environ if env is None else env
    translated = _translate(env)
    factory = client_factory or functools.partial(client_from_env, env=translated)
    try:
        llm: LLMClient = with_max_tokens(
            factory(translated.get("MEDIUM_MODEL") or None), max_tokens_from_env(translated)
        )
    except ProviderError as exc:
        log.warning("collector starting without a model provider: %s", exc)
        llm = OfflineClient()
    store = Path(env.get("CRYPT_STORE") or DEFAULT_STORE)
    return create_collector_app(store=store, llm=llm)


def main() -> None:
    app = build_app()
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", DEFAULT_PORT)),
    )


if __name__ == "__main__":
    main()
