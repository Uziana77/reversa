"""Agent 4 — Legacy Analyzer.

Decides (Table 4): which code regions carry business logic, rule
granularity.  Skills: AST query, LLM rule extraction, retrieval over
ASTMap.  Proposes candidate business rules with pre/post-conditions and a
source location, each with a given/expect contract pair so the Dynamic
Evidence Agent can execute it.  Writes the RuleInventory artefact.

Ablation A2 removes the AST/call-graph/CRUD context: the LLM then sees raw
files only, and the extraction is correspondingly weaker (this is exactly
what the ablation is designed to measure).
"""

from __future__ import annotations

import json
import os
from typing import Any, List, Optional, Tuple

from ..skills import heuristics
from .base import Agent, spans_of


class LegacyAnalyzerAgent(Agent):
    name = "legacy_analyzer"
    goal = ("Extract candidate business rules — explicit, implicit and "
            "constraints — from the structural analysis, each with pre/post "
            "conditions, a source span and a confidence score. Nothing is "
            "invented: every rule must point at a real code region.")

    def canonical_actions(self, context: dict) -> List[dict]:
        return [
            {"action": "select_code_regions", "args": {}},
            {"action": "extract_rules", "args": {}},
            {"action": "attach_contract_pairs", "args": {}},
            {"action": "score_confidence", "args": {}},
        ]

    def work(self, context: dict, actions: List[dict]) -> Tuple[Any, float, List[dict]]:
        payloads = context["payloads"]
        astmap = payloads.get("ASTMap") or {}
        run = context["run"]
        use_static = getattr(run.get("config"), "enable_static_context", True)
        if run.get("config") is not None:
            use_static = run["config"].enable_static_context

        if use_static:
            ctx = {"units": astmap.get("units", [])}
        else:
            # A2: raw files only — the same model without structural context
            ctx = {"raw_files": self._raw_files(run["root"], payloads)}
        res = self.provider.complete_json(
            "rules.extract",
            system=("You are the AURA Legacy Analyzer. Extract business rules "
                    "(preconditions, postconditions, inputs, outputs, source span, "
                    "given/expect contract) from the provided code analysis."),
            user="CONTEXT_JSON: " + json.dumps(ctx, default=str),
            schema_hint={"rules": [{"statement": "str", "kind": "explicit|implicit|constraint",
                                    "preconditions": ["str"], "postconditions": ["str"],
                                    "inputs": ["str"], "outputs": ["str"],
                                    "source": {"file": "str", "line_start": 0, "line_end": 0},
                                    "static_confidence": 0.0,
                                    "contract": {"given": {}, "expect": {}}}]},
            fallback={"rules": []},
        )
        rules = []
        for i, r in enumerate((res.data or {}).get("rules", []) or [], 1):
            rule = {
                "id": f"BR-{i:03d}",
                "statement": r.get("statement", ""),
                "kind": r.get("kind", "explicit"),
                "preconditions": r.get("preconditions", []),
                "postconditions": r.get("postconditions", []),
                "inputs": r.get("inputs", []),
                "outputs": r.get("outputs", []),
                "source": r.get("source"),
                "static_confidence": float(r.get("static_confidence", 0.5)),
                "extraction_method": r.get("extraction_method", "llm"),
                "contract": r.get("contract"),
                "dynamic_label": None,
                "dynamic_reason": "",
                "dynamic_trace": "",
                "false_injection": bool(r.get("false_injection", False)),
            }
            rules.append(rule)
        payload = {"rules": rules, "rule_count": len(rules),
                   "context_mode": "ast" if use_static else "raw"}
        conf = sum(r["static_confidence"] for r in rules) / max(1, len(rules))
        prov = spans_of(payload)
        return payload, conf, prov

    def schema_check(self, payload: Any) -> Tuple[bool, str]:
        if "rules" not in payload:
            return False, "missing rules"
        for r in payload["rules"]:
            for key in ("id", "statement", "static_confidence", "source"):
                if key not in r:
                    return False, f"rule missing {key}"
            if r["source"] and "file" not in r["source"]:
                return False, "rule source missing file"
        return True, ""

    def provenance_check(self, payload: Any, provenance: Optional[List[dict]] = None) -> Tuple[bool, str]:
        n = len(spans_of(payload)) + len(provenance or [])
        rules = payload.get("rules", [])
        if rules and n == 0:
            return False, "rules without any source span"
        return True, ""

    # ------------------------------------------------------------------
    def _raw_files(self, root: str, payloads: dict) -> dict:
        repomap = payloads.get("RepoMap") or {}
        files = {}
        for f in repomap.get("files", []):
            try:
                with open(os.path.join(root, f["path"]), encoding="utf-8", errors="replace") as fh:
                    files[f["path"]] = fh.read(60_000)
            except OSError:
                continue
        return files
