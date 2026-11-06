"""AURA pipeline orchestration.

A small directed-graph execution engine in the LangGraph style: typed
artefact channels over one shared pipeline state, checkpointed after every
agent, with the protocol's retry rule (self-check failure -> re-invoke the
same agent with the failure note, up to three attempts, then escalate).

Stage 1 — structural mapping : Navigator, Language Inference, AST Analyzer
Stage 2 — understanding/evidence : Legacy Analyzer, Dynamic Evidence, BSG Generator
Stage 3 — action and proof : Transformer, Equivalence Validator, Documentation
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from .agents import AGENT_REGISTRY
from .config import RunConfig
from .llm.registry import make_provider
from .state import SharedState

PIPELINE_ORDER = [
    "navigator",
    "language_inference",
    "ast_analyzer",
    "legacy_analyzer",
    "dynamic_evidence",
    "bsg_generator",
    "transformer",
    "equivalence_validator",
    "documentation_generator",
]


class Pipeline:
    def __init__(self, config: RunConfig, provider: Any = None) -> None:
        self.config = config
        self.provider = provider or make_provider(
            config.provider, model=config.model, temperature=config.temperature,
            seed=config.seed, timeout=config.request_timeout, max_calls=config.max_llm_calls,
        )
        self.state = SharedState(config)

    # ------------------------------------------------------------------
    def run(self, root: str, unit: dict, output_dir: str) -> Dict[str, Any]:
        os.makedirs(output_dir, exist_ok=True)
        t0 = time.time()
        unit = dict(unit)
        unit.setdefault("id", os.path.basename(root.rstrip("/")))
        run_ctx = {
            "root": os.path.abspath(root),
            "unit": unit,
            "config": self.config,
            "output_dir": os.path.abspath(output_dir),
            "state_ref": self.state,
        }
        results: Dict[str, Any] = {}
        for agent_name in PIPELINE_ORDER:
            if agent_name == "dynamic_evidence" and not self.config.enable_dynamic:
                # A1: rules keep their static confidence only
                self.state.log("orchestrator", "skip", {"agent": agent_name,
                                                       "reason": "ablation A1: dynamic evidence disabled"})
                results[agent_name] = {"skipped": True, "reason": "ablation A1"}
                continue
            agent_cls = AGENT_REGISTRY[agent_name]
            agent = agent_cls(self.provider, self.config)
            art = self._run_with_retries(agent, run_ctx)
            results[agent_name] = {
                "status": art.status,
                "version": art.version,
                "confidence": art.confidence,
                "notes": art.notes,
            }
            self.state.save(os.path.join(output_dir, "state.json"))
        elapsed = time.time() - t0
        summary = {
            "unit": unit.get("id"),
            "provider": self.provider.name,
            "model": self.provider.model,
            "ablation": self.config.ablation_code,
            "elapsed_s": round(elapsed, 2),
            "agents": results,
            "llm_calls": len(self.provider.ledger.calls),
            "prompt_tokens": self.provider.ledger.prompt_tokens,
            "completion_tokens": self.provider.ledger.completion_tokens,
            "llm_errors": self.provider.ledger.errors,
            "escalations": self.state.escalations,
        }
        return summary

    # ------------------------------------------------------------------
    def _run_with_retries(self, agent, run_ctx: dict):
        """Protocol rule 2: self-check failures are re-run with the failure
        note, up to ``max_retries`` attempts, after which the item is
        escalated and the artefact stays needs_revision."""
        last = None
        for attempt in range(1, self.config.max_retries + 1):
            art = agent.execute(self.state, run_ctx)
            last = art
            if art.status == "ok":
                return art
            self.state.log("orchestrator", "retry", {
                "agent": agent.name, "attempt": attempt, "notes": art.notes,
            })
        self.state.escalate(f"agent:{agent.name}", f"self-check failed after {self.config.max_retries} attempts: {last.notes if last else ''}",
                            agent.name)
        return last


def run_unit(config: RunConfig, root: str, unit: dict, output_dir: str) -> Dict[str, Any]:
    pipe = Pipeline(config)
    summary = pipe.run(root, unit, output_dir)
    pipe.state.save(os.path.join(output_dir, "state.json"))
    with open(os.path.join(output_dir, "llm_usage.json"), "w", encoding="utf-8") as fh:
        import json

        json.dump(pipe.provider.ledger.to_dict(), fh, indent=2)
    return summary
