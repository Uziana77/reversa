"""AURA agent framework (synopsis 6.2).

Every agent has the same internal structure:

1. **role specification** — the agent's goal, the inputs it is entitled to
   read from the shared state, and the artefact it is obliged to write back;
2. **planner** — the reasoning loop in which the LLM decides which action
   to take next given the current state (ReAct pattern);
3. **skills** — deterministic tools the planner may call;
4. **memory** — short-term working context plus read access to the
   persistent shared state;
5. **self-check** — a validation step confirming the output artefact
   conforms to its schema and carries provenance before it is committed.

The planner cannot write to the shared state except through the
self-check: an agent can decide *how* to reach its goal, but not *what* it
is allowed to produce.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..llm.base import LLMProvider
from ..state import HANDOFFS, Artefact, SharedState, SourceSpan


class SelfCheckError(Exception):
    def __init__(self, notes: str) -> None:
        super().__init__(notes)
        self.notes = notes


class Agent:
    """Base class for all nine AURA agents."""

    name: str = "agent"
    goal: str = ""

    def __init__(self, provider: LLMProvider, config: Any = None) -> None:
        self.provider = provider
        self.config = config
        self.memory: Dict[str, Any] = {}     # short-term working context

    # ------------------------------------------------------------------
    # Role specification
    # ------------------------------------------------------------------
    @property
    def role_spec(self) -> dict:
        spec = HANDOFFS[self.name]
        return {
            "goal": self.goal,
            "reads": spec["reads"],
            "writes": spec["writes"],
            "receives_from": spec["receives_from"],
        }

    # ------------------------------------------------------------------
    # Memory helpers (control rule 1 enforced by SharedState)
    # ------------------------------------------------------------------
    def read(self, state: SharedState, artefact: str, *, allow_non_ok: bool = False) -> Optional[Artefact]:
        return state.read(self.name, artefact, allow_non_ok=allow_non_ok)

    def load_payloads(self, state: SharedState) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for art_name in HANDOFFS[self.name]["reads"]:
            art = self.read(state, art_name)
            if art is not None:
                out[art_name] = art.payload
        return out

    # ------------------------------------------------------------------
    # Planner (ReAct loop)
    # ------------------------------------------------------------------
    def plan(self, context: dict, canonical_actions: List[dict]) -> List[dict]:
        """Ask the LLM which actions to take next (ReAct).

        The offline provider returns the canonical deterministic action
        sequence; a real model may refine it.  The plan is advisory — the
        agent's contract fixes *what* it may produce.
        """
        res = self.provider.complete_json(
            "plan.step",
            system=(
                f"You are the AURA {self.name} agent. Goal: {self.goal} "
                f"You read {self.role_spec['reads']} and must write exactly one "
                f"{self.role_spec['writes']} artefact. Decide the next actions."
            ),
            user="CONTEXT_JSON: " + json.dumps({
                "agent": self.name,
                "goal": self.goal,
                "canonical_actions": canonical_actions,
                "context_digest": _digest(context),
            }, default=str),
            schema_hint={"thought": "string", "actions": [{"action": "string", "args": "object"}]},
            fallback={"thought": "fallback to canonical plan", "actions": canonical_actions},
        )
        actions = res.data.get("actions") if isinstance(res.data, dict) else None
        return actions if actions else canonical_actions

    # ------------------------------------------------------------------
    # Self-check + commit (the only write path)
    # ------------------------------------------------------------------
    def schema_check(self, payload: Any) -> Tuple[bool, str]:
        return True, ""

    def provenance_check(self, payload: Any, provenance: Optional[List[dict]] = None) -> Tuple[bool, str]:
        if provenance or spans_of(payload):
            return True, ""
        return False, "no provenance spans"

    def commit(
        self,
        state: SharedState,
        payload: Any,
        *,
        confidence: float = 1.0,
        provenance: Optional[List[dict]] = None,
        notes: str = "",
        status: str = "ok",
    ) -> Artefact:
        ok, msg = self.schema_check(payload)
        if not ok:
            raise SelfCheckError(f"schema: {msg}")
        ok, msg = self.provenance_check(payload, provenance)
        if not ok:
            raise SelfCheckError(f"provenance: {msg}")
        return state.write(
            self.name, payload,
            confidence=confidence, status=status, notes=notes,
            provenance=provenance or [],
        )

    # ------------------------------------------------------------------
    def execute(self, state: SharedState, run_ctx: Optional[dict] = None) -> Artefact:
        """Plan, run skills, self-check and commit — the full agent cycle."""
        t0 = time.time()
        state.set_agent(self.name)
        state.log(self.name, "start", {"goal": self.goal})
        payloads = self.load_payloads(state)
        context = {"payloads": payloads, "run": run_ctx or {}}
        canonical = self.canonical_actions(context)
        actions = self.plan(context, canonical)
        self.memory["actions_taken"] = actions
        result = self.work(context, actions)
        payload, confidence, provenance = result
        try:
            art = self.commit(state, payload, confidence=confidence, provenance=provenance)
        except SelfCheckError as exc:
            # control rule 2: needs_revision artefact, orchestrator may retry
            art = state.write(
                self.name, payload,
                confidence=confidence, status="needs_revision",
                notes=str(exc.notes), provenance=provenance or [],
            )
        state.log(self.name, "finish", {"status": art.status, "elapsed_s": round(time.time() - t0, 2)})
        state.set_agent(None)
        return art

    # -- to be specialised -----------------------------------------------
    def canonical_actions(self, context: dict) -> List[dict]:
        return [{"action": "noop", "args": {}}]

    def work(self, context: dict, actions: List[dict]) -> Tuple[Any, float, List[dict]]:
        raise NotImplementedError


def _digest(context: dict, limit: int = 1200) -> str:
    try:
        s = json.dumps(context, default=str)
    except Exception:
        s = str(context)
    return s[:limit]


def spans_of(payload: Any) -> List[dict]:
    """Collect every SourceSpan-ish dict inside a payload."""
    out: List[dict] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if "file" in obj and "line_start" in obj:
                out.append({"file": obj["file"], "line_start": obj["line_start"],
                            "line_end": obj.get("line_end", obj["line_start"])})
            for v in obj.values():
                walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v)

    walk(payload)
    return out
