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
import os
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
        root = run["root"]
        primary = Harness.from_dict(unit.get("harness", {}))

        adapter_cache = {}

        def adapter_for(rule) -> Tuple[Any, Harness]:
            h = _pick_harness(unit, rule) or primary
            key = h.language or unit.get("language", "")
            if key not in adapter_cache:
                adapter_cache[key] = get_adapter(
                    key,
                    timeout_s=getattr(cfg, "sandbox_timeout_s", 10.0) if cfg else 10.0,
                    memory_mb=getattr(cfg, "sandbox_memory_mb", 512) if cfg else 512,
                    max_steps=getattr(cfg, "sandbox_max_steps", 2_000_000) if cfg else 2_000_000,
                )
            return adapter_cache[key], h

        findings = []
        traces = {}
        confirmed = 0
        for rule in rules:
            adapter, harness = adapter_for(rule)
            if adapter is None or not adapter.available():
                findings.append({"rule_id": rule["id"], "label": "unresolved",
                                 "reason": f"no safe execution path: no toolchain for "
                                           f"{harness.language or unit.get('language')!r} in sandbox",
                                 "trace": "", "cases": []})
                continue
            if self._touches_external(rule):
                findings.append({"rule_id": rule["id"], "label": "unresolved",
                                 "reason": "rule depends on an external system (never executed)",
                                 "trace": "", "cases": []})
                continue
            # The claim to reproduce is the rule's contract pair (given -> expect);
            # boundary variants are the Equivalence Validator's concern, where
            # expected values come from executing the ORIGINAL code.
            given = (rule.get("contract") or {}).get("given", {}) or {}
            filled = self._fill_defaults(harness, given)
            cases = [dict(filled)]
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
            "sandbox": {"adapters": {k: (v.name if v else None) for k, v in adapter_cache.items()}},
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
            trace_lines.append(f"input={case} -> ok={res.ok} state={res.state} fault={res.fault}")
            if not res.ok and res.fault.startswith("unresolved"):
                return "unresolved", res.fault, "\n".join(trace_lines), case_results
            if not res.ok:
                # An execution fault is *missing evidence*, not a
                # contradiction: the claim could not be tested safely, so
                # it must not be labelled contradicted (that label is
                # reserved for clean executions that disagree).
                case_results.append({"input": case, "fault": res.fault,
                                     "match": False, "executed": False})
                continue
            executed += 1
            observable = set(res.state) | {"_outputs", "_no_outputs"}
            testable = {k: v for k, v in expect.items() if k in observable}
            if not testable:
                case_results.append({"input": case, "match": False, "executed": True,
                                     "untestable": True,
                                     "state_excerpt": {k: res.state.get(k) for k in list(res.state)[:6]}})
                continue
            ok = self._expect_holds(testable, {**res.state, "_outputs": res.outputs})
            if expect:
                matches += 1 if ok else 0
            else:
                matches += 1  # no explicit expectation: execution succeeded
            case_results.append({"input": case, "match": ok, "executed": True,
                                 "state_excerpt": {k: res.state.get(k) for k in list(res.state)[:6]}})
        if executed == 0:
            faults = [c.get("fault", "") for c in case_results if c.get("fault")]
            if any(c.get("untestable") for c in case_results):
                return "unresolved", ("claim talks only about outputs the harness "
                                      "does not expose"), "\n".join(trace_lines), case_results
            return "unresolved", (
                "no contract case could be executed safely: "
                + (faults[0] if faults else "no inputs could be synthesised")), "\n".join(trace_lines), case_results
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
    def _fill_defaults(harness, given: dict) -> dict:
        """Complete a contract's given with typed defaults for every
        harness input it does not mention, so partial contracts still
        execute against the real harness."""
        defaults = {}
        for name, typ in (getattr(harness, "input_fields", None) or {}).items():
            t = (typ or "any").lower()
            if t in ("int", "long", "number", "numeric", "int9"):
                defaults[name] = 0
            elif t in ("float", "double", "decimal"):
                defaults[name] = 0.0
            elif t in ("bool", "boolean", "flag"):
                defaults[name] = False
            elif t in ("list", "array"):
                defaults[name] = []
            elif t in ("dict", "map", "record"):
                defaults[name] = {}
            else:
                defaults[name] = ""
        defaults.update(given or {})
        return defaults

    @staticmethod
    def _expect_holds(expect: dict, state: dict) -> bool:
        if not expect:
            return True
        for key, want in expect.items():
            if key == "_no_outputs":
                have = state.get("_outputs", [])
                for w in (want if isinstance(want, list) else [want]):
                    if any(str(w) in str(h) for h in have):
                        return False
                continue
            if key == "_outputs":
                have = state.get("_outputs", [])
                want_list = want if isinstance(want, list) else [want]
                if not want_list:
                    if have:
                        return False
                    continue
                for w in want_list:
                    if not any(str(w) in str(h) for h in have):
                        return False
                continue
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


def _pick_harness(unit: dict, rule: dict) -> Any:
    """Choose the harness for a rule by its source file (multi-program units)."""
    harnesses = unit.get("harnesses") or {}
    src = ((rule.get("source") or {}).get("file") or "").replace("\\", "/")
    if not src or not harnesses:
        return None
    for key, h in harnesses.items():
        if src.endswith(key) or key.endswith(src) or os.path.basename(src) == os.path.basename(key):
            return Harness.from_dict(h)
    return None
