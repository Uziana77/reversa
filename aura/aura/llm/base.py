"""LLM provider abstraction.

Two providers implement the same interface:

* :class:`OpenAIProvider` — real OpenAI chat-completions calls (JSON mode),
  with retry, timeout and token accounting.  The API key is read from the
  environment / ``.env`` at call time and is never persisted.
* :class:`OfflineProvider` — a deterministic, seeded stand-in used for
  offline dry-runs, CI self-tests and the ablation harness.  It performs
  *real* deterministic work (rule synthesis from structure, templated
  summarisation) so every pipeline stage is exercised end-to-end without
  network access.

Every call is recorded in :class:`UsageLedger` so cost (RQ4) can be reported.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LLMResult:
    data: Any                       # parsed JSON payload (or raw text in "text" key)
    text: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    provider: str = ""
    latency_s: float = 0.0
    error: str = ""


@dataclass
class UsageLedger:
    calls: List[dict] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    errors: int = 0

    def record(self, task: str, result: LLMResult) -> None:
        self.calls.append(
            {
                "task": task,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "latency_s": round(result.latency_s, 3),
                "error": result.error,
            }
        )
        self.prompt_tokens += result.prompt_tokens
        self.completion_tokens += result.completion_tokens
        if result.error:
            self.errors += 1

    def to_dict(self) -> dict:
        return {
            "n_calls": len(self.calls),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "errors": self.errors,
            "calls": self.calls,
        }


class LLMProvider:
    """Base class.  Subclasses implement :meth:`_complete`."""

    name = "base"

    def __init__(self, model: str = "", temperature: float = 0.0, seed: int = 0,
                 timeout: float = 120.0, max_calls: int = 400) -> None:
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.timeout = timeout
        self.max_calls = max_calls
        self.ledger = UsageLedger()
        self._n_calls = 0

    # ------------------------------------------------------------------
    def complete_json(
        self,
        task: str,
        system: str,
        user: str,
        *,
        schema_hint: Optional[dict] = None,
        fallback: Any = None,
    ) -> LLMResult:
        """Return a parsed JSON answer for ``task``.

        ``schema_hint`` documents the expected shape (used by the offline
        provider to shape its deterministic answer and by the OpenAI
        provider in the prompt).  On failure the provider returns
        ``fallback`` with ``error`` set — never an exception, so the
        pipeline can mark items unresolved instead of dying.
        """
        self._n_calls += 1
        if self._n_calls > self.max_calls:
            res = LLMResult(data=fallback if fallback is not None else {}, error="max_llm_calls_exceeded")
            self.ledger.record(task, res)
            return res
        t0 = time.time()
        try:
            text = self._complete(task, system, user, schema_hint)
            data = _parse_json_loosely(text)
            res = LLMResult(
                data=data if data is not None else (fallback if fallback is not None else {}),
                text=text,
                model=self.model,
                provider=self.name,
                latency_s=time.time() - t0,
                error="" if data is not None else "json_parse_error",
            )
        except Exception as exc:  # noqa: BLE001 — pipeline must survive provider errors
            res = LLMResult(
                data=fallback if fallback is not None else {},
                model=self.model,
                provider=self.name,
                latency_s=time.time() - t0,
                error=f"{type(exc).__name__}: {exc}",
            )
        self.ledger.record(task, res)
        return res

    # ------------------------------------------------------------------
    def _complete(self, task: str, system: str, user: str, schema_hint: Optional[dict]) -> str:
        raise NotImplementedError


def _parse_json_loosely(text: str) -> Any:
    """Parse JSON out of a model answer that may carry markdown fences."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
        t = t.strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    # find the first {...} or [...] block
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = t.find(opener), t.rfind(closer)
        if 0 <= i < j:
            try:
                return json.loads(t[i : j + 1])
            except Exception:
                continue
    return None


def approx_tokens(text: str) -> int:
    """Cheap token estimate (~4 chars/token) used when the API omits usage."""
    return max(1, len(text) // 4)


def stable_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()
