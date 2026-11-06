"""OpenAI chat-completions provider (stdlib HTTP, JSON mode).

The API key is read from :func:`aura.config.load_api_key` at call time and
is kept only in the request header — it is never written to logs, result
artefacts or the repository.  All calls use ``temperature`` from the run
config (0.0 for reproducibility, as in the AgentModernize protocol).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Optional

from .base import LLMProvider, approx_tokens

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
RETRYABLE = {408, 409, 429, 500, 502, 503, 504}


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key
        self._last_error = ""

    # ------------------------------------------------------------------
    def _complete(self, task: str, system: str, user: str, schema_hint: Optional[dict]) -> str:
        schema_note = ""
        if schema_hint:
            schema_note = (
                "\n\nReturn ONLY a JSON object matching this schema hint:\n"
                + json.dumps(schema_hint, indent=2)[:2000]
            )
        messages = [
            {"role": "system", "content": system + schema_note},
            {"role": "user", "content": user},
        ]
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        last_err = ""
        for attempt in range(4):
            req = urllib.request.Request(
                OPENAI_URL,
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                content = payload["choices"][0]["message"]["content"] or ""
                usage = payload.get("usage", {})
                # account exact usage into the ledger via a shim result
                self._last_usage = (
                    int(usage.get("prompt_tokens", approx_tokens(system + user))),
                    int(usage.get("completion_tokens", approx_tokens(content))),
                )
                return content
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", "replace")[:400]
                except Exception:
                    pass
                last_err = f"HTTP {exc.code}: {detail}"
                if exc.code == 401:
                    raise RuntimeError("OpenAI authentication failed (401) — check OPENAI_API_KEY") from exc
                if exc.code not in RETRYABLE:
                    raise RuntimeError(last_err) from exc
                time.sleep(min(8.0, 1.5 * (2 ** attempt)))
            except Exception as exc:  # noqa: BLE001
                last_err = f"{type(exc).__name__}: {exc}"
                time.sleep(min(8.0, 1.5 * (2 ** attempt)))
        raise RuntimeError(f"OpenAI request failed after retries: {last_err}")

    # account real usage -------------------------------------------------
    def complete_json(self, task, system, user, *, schema_hint=None, fallback=None):  # type: ignore[override]
        self._last_usage = (approx_tokens(system + user), 0)
        res = super().complete_json(task, system, user, schema_hint=schema_hint, fallback=fallback)
        if not res.error and getattr(self, "_last_usage", None):
            res.prompt_tokens, res.completion_tokens = self._last_usage
        else:
            res.prompt_tokens = approx_tokens(system + user)
            res.completion_tokens = approx_tokens(res.text or "")
        return res
