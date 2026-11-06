"""Offline LLM provider — deterministic stand-in for a real model.

It answers each AURA task with the deterministic heuristics in
:mod:`aura.skills.heuristics` and :mod:`aura.skills.codegen`.  All answers
are pure functions of the structured context embedded in the prompt (the
``CONTEXT_JSON: {...}`` block), so runs are reproducible and unit-testable.

This provider exists so that (a) the full pipeline can run without network
access, (b) the ablation harness and CI self-tests are deterministic, and
(c) architecture-level comparisons (AURA vs single-prompt baselines) hold
the model fixed.  It is not presented as a substitute for LLM quality —
results from this provider are labelled "offline dry-run".
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from ..skills import codegen, heuristics
from .base import LLMProvider, approx_tokens

CONTEXT_RE = re.compile(r"CONTEXT_JSON:\s*(\{.*\})\s*$", re.S)


def extract_context(user: str) -> dict:
    m = CONTEXT_RE.search(user or "")
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}


class OfflineProvider(LLMProvider):
    name = "offline"

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("model", "offline-heuristic")
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    def _complete(self, task: str, system: str, user: str, schema_hint: Optional[dict]) -> str:
        ctx = extract_context(user)
        answer = self._answer(task, ctx, system)
        return json.dumps(answer)

    def _answer(self, task: str, ctx: dict, system: str) -> dict:
        if task == "grammar.hypothesize":
            return heuristics.propose_grammar(ctx)
        if task == "rules.extract":
            return {"rules": heuristics.synthesize_rules(ctx)}
        if task == "summary.function":
            return {"summary": heuristics.summarize_function(ctx)}
        if task == "summary.system":
            return heuristics.summarize_system(ctx)
        if task == "modernize.generate":
            bsg = ctx.get("bsg", {})
            rules_by_id = {r.get("id"): r for r in ctx.get("rules", [])}
            unit_id = ctx.get("unit_id", "unit")
            if ctx.get("mode") == "in_place":
                return codegen.generate_in_place_report(unit_id, bsg, rules_by_id)
            return codegen.generate_python_from_bsg(unit_id, bsg, rules_by_id, ctx.get("mode", "migration"))
        if task == "plan.step":
            return self._plan(ctx)
        if task == "equivalence.plan":
            return {"testable": [n.get("id") for n in ctx.get("nodes", []) if not n.get("blocked")]}
        if task == "doc.outline":
            return {"sections": self._doc_outline(ctx)}
        if task == "navigator.plan":
            files = ctx.get("files", [])
            key = [f.get("path") for f in files if f.get("is_entry")][:10]
            return {"key_files": key, "traversal_order": [f.get("path") for f in files]}
        if task == "dynamic_evidence.inputs":
            return {"inputs": _contract_inputs(ctx)}
        # Generic fallback: echo a structured digest of the context so the
        # pipeline can proceed (and the answer is clearly non-inventive).
        return {"note": "offline provider has no strategy for this task", "task": task, "seen_keys": sorted(ctx)[:20]}

    # ------------------------------------------------------------------
    def _plan(self, ctx: dict) -> dict:
        """Canonical ReAct plan: the deterministic action sequence that
        implements this agent's goal.  Agents may deviate; the offline
        provider always executes the canonical plan."""
        return {"thought": "execute canonical deterministic plan for this role",
                "actions": ctx.get("canonical_actions", [])}

    def _doc_outline(self, ctx: dict) -> list:
        units = ctx.get("units", [])
        if not units:
            return [{"level": "system", "title": "System Overview"}]
        outline = [
            {"level": "system", "title": "System Overview"},
            {"level": "module", "title": "Architecture and Data Access"},
        ]
        for u in units:
            outline.append({"level": "unit", "title": u.get("name", u.get("path", "unit"))})
        return outline[:50]


# small helper used by the dynamic-evidence input strategy
def _contract_inputs(ctx: dict) -> list:
    rule = ctx.get("rule", {})
    out = []
    contract = rule.get("contract") or {}
    if contract.get("given"):
        out.append(dict(contract["given"]))
    for name in rule.get("inputs", []) or []:
        for val in (0, 1, -1, 10, 100):
            case = dict(contract.get("given", {}))
            case[name] = val
            out.append(case)
    if not out:
        out.append({})
    # de-duplicate, keep order
    seen = set()
    uniq = []
    for c in out:
        key = json.dumps(c, sort_keys=True)
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq
