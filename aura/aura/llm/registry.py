"""Provider factory."""

from __future__ import annotations

from typing import Optional

from .base import LLMProvider
from .offline import OfflineProvider


def make_provider(name: str, *, model: str = "", temperature: float = 0.0, seed: int = 0,
                  timeout: float = 120.0, max_calls: int = 400, api_key: Optional[str] = None) -> LLMProvider:
    name = (name or "offline").lower()
    if name == "offline":
        return OfflineProvider(model="offline-heuristic", temperature=0.0, seed=seed,
                               timeout=timeout, max_calls=max_calls)
    if name == "openai":
        from .openai_provider import OpenAIProvider

        key = api_key
        if not key:
            from ..config import load_api_key

            key = load_api_key()
        if not key:
            raise RuntimeError(
                "OpenAI provider requested but no API key found. "
                "Set OPENAI_API_KEY or create aura/.env (see .env.example)."
            )
        return OpenAIProvider(api_key=key, model=model or "gpt-4o-mini",
                              temperature=temperature, seed=seed,
                              timeout=timeout, max_calls=max_calls)
    raise ValueError(f"unknown provider {name!r}")
