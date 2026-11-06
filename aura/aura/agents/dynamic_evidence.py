"""Agent 5 — Dynamic Evidence Agent.

Decides (Table 4): what inputs to synthesise, when execution is unsafe.
Skills: sandbox exec, trace capture, input generation.  For each candidate
rule it attempts to reproduce the claimed behaviour by *executing* the
relevant code path in an isolated sandbox with synthesised inputs — never
by re-reading the code.

Outcome labels (synopsis 6.1):
  confirmed    — execution matches the claim
  contradicted — execution differs
  unresolved   — no safe execution path exists (external system, missing
                 toolchain, unparseable code) — such code is never executed

Writes the EvidenceReport artefact.
"""

from __future__ import annotations

import json
from typing import Any, List, Tuple

from ..skills import inputgen
from ..skills.adapters import Harness, get_adapter
from .base import Agent


class DynamicEvidenceAgent(Agent):
    name = "dynamic_evidence"
    goal = ("Check every candidate business rule by executing the relevant "
            "code path in an isolated sandbox with synthesised inputs, and "
            "label it confirmed, contradicted or unresolved. Execution is "
            "evidence: never re-read the code to 'verify' it.")

    def canonical_actions(self, context: dict) -> List[dict]:
        return [
            {"action": "synthesise_inputs", "args": {}},
            {"action": "sandbox_execute_original", "args": {}},
            {"action": "compare_trace_with_claim", "args": {}},
            {"action": "label_rule", "args": {}},
        ]

    def work(self, context: dict, actions: List[dict]) -> Tuple[Any, float, List[dict]]:
        payloads = context["payloads"]
        rules = (payloads.get("RuleInventory") or {}).get("rules", [])
        run = context["run"]
        cfg = run.get("config")
        unit = run.get("unit", {})
        harness = Harness.from_dict(unit.get("harness", {}))
        root = run["root"]

        adapter = get_adapter(
            harness.language or unit.get("language", ""),
            timeout_s=getattr(cfg, "sandbox_timeout_s", 10.0) if cfg else 10.0,
            memory_mb=getattr(cfg, "sandbox_memory_mb", 512) if cfg else 512,
            max_steps=getattr(cfg, "sandbox_max_steps", 2_000_000) if cfg else 2_000_000,
        )
        unsafe_reason = ""
        if adapter is None or not adapter.available():
            unsafe_reason = f"no safe execution path: no toolchain for {harness.language!r} in sandbox"

        findings = []
        traces = {}
        confirmed = 0
        for rule in rules:
            if unsafe_reason:
                findings.append({"rule_id": rule["id"], "label": "unresolved",
                                 "reason": unsafe_reason, "trace": "",
                                 "cases": []})
                continue
            if self._touches_external(rule):
                findings.append({"rule_id": rule["id"], "label": "unresolved",
                                 "reason": "rule depends on an external system (never executed)",
                                 "trace": "", "cases": []})
                continue
            cases = inputgen.synthesise_inputs(rule)
            label, reason, trace, case_results = self._check_rule(rule, cases, adapter, root, harness)
            if label == "confirmed":
                confirmed += 1
            findings.append({"rule_id": rule["id"], "label": label, "reason": reason,
                             "trace": trace[:2000], "cases": case_results})
            traces[rule["id"]] = trace[:4000]

        payload = {
            "findings": findings,
            "executed_rules": sum(1 for f in findings if f["label"] != "unresolved"),
            "confirmed": sum(1 for f in findings if f["label"] == "confirmed"),
            "contradicted": sum(1 for f in findings if f["label"] == "contradicted"),
            "unresolved": sum(1 for f in findings if f["label"] == "unresolved"),
            "traces": traces,
            "sandbox": {"adapter": adapter.name if adapter else None,
                        "unsafe_reason": unsafe_reason},
        }
        conf = confirmed / max(1, len(rules))
        prov = [{"file": (r.get("source") or {}).get("file", "?"),
                 "line_start": (r.get("source") or {}).get("line_start", 1),
                 "line_end": (r.get("source") or {}).get("line_end", 1)} for r in rules]
        return payload, conf, prov

    # ------------------------------------------------------------------
    def _check_rule(self, rule, cases, adapter, root, harness) -> Tuple[str, str, str, list]:
        """Execute the original code on synthesised inputs and compare each
        case against the rule's contract expectation."""
        expect = (rule.get("contract") or {}).get("expect", {}) or {}
        case_results = []
        matches = 0
        executed = 0
        trace_lines = []
        for case in cases:
            res = adapter.run(root, harness, case)
            executed += 1
            trace_lines.append(f"input={case} -> ok={res.ok} state={res.state} fault={res.fault}")
            if not res.ok and res.fault.startswith("unresolved"):
                return "unresolved", res.fault, "\n".join(trace_lines), case_results
            if not res.ok:
                case_results.append({"input": case, "fault": res.fault, "match": False})
                continue
            ok = self._expect_holds(expect, res.state)
            if expect:
                matches += 1 if ok else 0
            else:
                matches += 1  # no explicit expectation: execution succeeded
            case_results.append({"input": case, "match": ok,
                                 "state_excerpt": {k: res.state.get(k) for k in list(res.state)[:6]}})
        if executed == 0:
            return "unresolved", "no inputs could be synthesised", "", []
        trace = "\n".join(trace_lines)
        if not expect:
            return "confirmed", "execution produced no fault on synthesised inputs", trace, case_results
        if matches == executed:
            return "confirmed", f"contract expectation held on all {executed} cases", trace, case_results
        if matches == 0:
            return "contradicted", f"execution contradicts the claim on all {executed} cases", trace, case_results
        return "contradicted", (f"execution contradicts the claim on {executed - matches}/{executed} cases "
                               f"(boundary counterexamples found)"), trace, case_results

    @staticmethod
    def _expect_holds(expect: dict, state: dict) -> bool:
        if not expect:
            return True
        for key, want in expect.items():
            have = state.get(key)
            if have is None and key not in state:
                return False
            try:
                if abs(float(have) - float(want)) <= 1e-6:
                    continue
            except (TypeError, ValueError):
                pass
            if str(have).strip() == str(want).strip():
                continue
            if isinstance(want, str) and want == "changed":
                continue
            return False
        return True

    @staticmethod
    def _touches_external(rule: dict) -> bool:
        blob = json.dumps(rule, default=str).lower()
        return ("external" in blob) or ("exec sql" in blob) or ("external:" in blob)

    def schema_check(self, payload: Any) -> Tuple[bool, str]:
        if "findings" not in payload:
            return False, "missing findings"
        for f in payload["findings"]:
            if f.get("label") not in ("confirmed", "contradicted", "unresolved"):
                return False, f"invalid label {f.get('label')!r}"
            if not f.get("reason"):
                return False, f"finding {f.get('rule_id')} lacks a reason"
        return True, ""
