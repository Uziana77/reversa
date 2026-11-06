"""Agent 7 — Modernization Transformer.

Decides (Table 4): idiom choice, what to mark REVIEW/TODO.  Skills: LLM
code generation, template fill, diff.

On the user's choice it either upgrades the code in place (same language,
changes needing sign-off marked REVIEW) or migrates it to a target
language (unmappable constructs marked TODO rather than dropped).

The BSG is the trust boundary: nothing is generated from raw extraction.
Blocked nodes are skipped — never guessed (control rule 3).  With the A3
ablation the gate is off and all extracted rules are consumed whatever
their label; the marker stream records that.
"""

from __future__ import annotations

import json
import os
from typing import Any, List, Tuple

from .base import Agent, spans_of


class ModernizationTransformerAgent(Agent):
    name = "transformer"
    goal = ("Produce modernized code from the BSG — in-place upgrade or "
            "migration to the chosen target language — rendering every "
            "interlock as an explicit guard clause and marking unmappable "
            "constructs REVIEW/TODO instead of dropping them.")

    def canonical_actions(self, context: dict) -> List[dict]:
        return [
            {"action": "read_trusted_nodes", "args": {}},
            {"action": "select_idioms", "args": {}},
            {"action": "generate_code", "args": {}},
            {"action": "mark_review_and_todo", "args": {}},
            {"action": "map_nodes_to_spans", "args": {}},
        ]

    def work(self, context: dict, actions: List[dict]) -> Tuple[Any, float, List[dict]]:
        payloads = context["payloads"]
        bsg = payloads.get("BSG") or {}
        rules = (payloads.get("RuleInventory") or {}).get("rules", [])
        run = context["run"]
        cfg = run.get("config")
        unit = run.get("unit", {})
        gate = getattr(cfg, "enable_bsg_gate", True) if cfg else True
        mode = getattr(cfg, "modernization_mode", "migration") if cfg else "migration"
        target = getattr(cfg, "migration_target", "python") if cfg else "python"

        if gate:
            # trust boundary: blocked nodes are skipped, never guessed
            gen_rules = [r for r in rules
                         if not any(n["blocked"] and r["id"] in n.get("rule_ids", [])
                                    for n in bsg.get("nodes", []))]
            gen_nodes = [n for n in bsg.get("nodes", []) if not n.get("blocked")]
        else:
            # A3: no gate — every extracted rule is consumed whatever its
            # label, including contradicted/blocked nodes (marked so the
            # blocked-node-code-leak invariant can measure the damage)
            gen_rules = rules
            gen_nodes = [{**n, "blocked": False,
                          "originally_blocked": bool(n.get("blocked"))}
                         for n in bsg.get("nodes", [])]

        ctx = {
            "unit_id": unit.get("id", "unit"),
            "mode": mode,
            "target": target,
            "bsg": {"nodes": gen_nodes,
                    "edges": bsg.get("edges", [])},
            "rules": gen_rules,
            "blocked_rules": [r for r in rules if r not in gen_rules],
        }
        res = self.provider.complete_json(
            "modernize.generate",
            system=("You are the AURA Modernization Transformer. Generate modernized "
                    "code from the Behavioural Specification Graph. Render every "
                    "interlock as an explicit guard clause; mark unmappable "
                    "constructs REVIEW/TODO rather than dropping them; skip blocked "
                    "nodes entirely."),
            user="CONTEXT_JSON: " + json.dumps(ctx, default=str),
            schema_hint={"files": [{"path": "str", "content": "str"}],
                         "markers": [{"kind": "REVIEW|TODO|SKIPPED", "line": 0, "reason": "str",
                                      "path": "str"}],
                         "node_spans": [{"node_id": "str", "path": "str",
                                         "line_start": 0, "line_end": 0}]},
            fallback={"files": [], "markers": [], "node_spans": []},
        )
        data = res.data or {}
        out_dir = run.get("output_dir") or os.path.join(run["root"], "_aura_out")
        os.makedirs(out_dir, exist_ok=True)
        written = []
        for f in data.get("files", []):
            dest = os.path.join(out_dir, f.get("path", "modernized.py"))
            os.makedirs(os.path.dirname(dest) or out_dir, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(f.get("content", ""))
            written.append({"path": os.path.relpath(dest, out_dir),
                            "abs_path": dest, "lines": f.get("content", "").count("\n") + 1})
        payload = {
            "mode": mode,
            "target": target if mode == "migration" else unit.get("language"),
            "files": written,
            "markers": data.get("markers", []),
            "node_spans": data.get("node_spans", []),
            "skipped_blocked_nodes": [n["id"] for n in bsg.get("nodes", []) if n.get("blocked")] if gate else [],
            "gate_enabled": gate,
            "output_dir": out_dir,
        }
        conf = 0.9 if written else 0.3
        prov = [{"file": f["path"], "line_start": 1, "line_end": f.get("lines", 1)} for f in written]
        return payload, conf, prov

    def schema_check(self, payload: Any) -> Tuple[bool, str]:
        if "files" not in payload or "markers" not in payload:
            return False, "missing files/markers"
        if payload.get("mode") == "migration" and not payload["files"]:
            return False, "migration produced no files"
        for m in payload["markers"]:
            if m.get("kind") not in ("REVIEW", "TODO", "SKIPPED"):
                return False, f"invalid marker kind {m.get('kind')!r}"
        return True, ""
