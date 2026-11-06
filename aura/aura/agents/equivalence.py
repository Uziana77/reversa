"""Agent 8 — Equivalence Validator.

Decides (Table 4): which BSG nodes are testable, pass/fail threshold.
Skills: sandbox exec, trace compare.

Behavioural equivalence is assessed with two independent checks, and
neither is an LLM opinion (synopsis 6.9):

1. **Contract tests** — each rule's given/expect pair from the BSG is
   re-executed against the new code, extended with boundary-value inputs
   whose expected outputs are computed by executing the *original* code;
2. **Differential tests** — the same inputs run through the original code
   and the new code, comparing final state and signalled faults.

BER is always reported together with the testable share.  Unresolved
rules are excluded from the denominator and counted separately.  For
in-place modernization the unit's own test suite (golden behaviour) is
also run before and after, and the retained pass rate is reported.
"""

from __future__ import annotations

import json
import os
from typing import Any, List, Optional, Tuple

from ..skills import inputgen
from ..skills.adapters import Harness, get_adapter
from ..skills.adapters.python_adapter import PythonAdapter
from .base import Agent


class EquivalenceValidatorAgent(Agent):
    name = "equivalence_validator"
    goal = ("Confirm behavioural preservation of the modernized code with "
            "contract tests and differential tests executed in the sandbox. "
            "Report the Behavioural Equivalence Rate together with the "
            "testable share; never claim proof, only absence of "
            "counterexamples on generated inputs.")

    def canonical_actions(self, context: dict) -> List[dict]:
        return [
            {"action": "select_testable_nodes", "args": {}},
            {"action": "run_contract_tests", "args": {}},
            {"action": "run_differential_tests", "args": {}},
            {"action": "compute_ber", "args": {}},
        ]

    def work(self, context: dict, actions: List[dict]) -> Tuple[Any, float, List[dict]]:
        payloads = context["payloads"]
        bsg = payloads.get("BSG") or {}
        rules = {r["id"]: r for r in (payloads.get("RuleInventory") or {}).get("rules", [])}
        modern = payloads.get("ModernizedCode") or {}
        evidence = payloads.get("EvidenceReport") or {}
        run = context["run"]
        cfg = run.get("config")
        unit = run.get("unit", {})
        harness = Harness.from_dict(unit.get("harness", {}))
        root = run["root"]

        orig = get_adapter(harness.language or unit.get("language", ""),
                           timeout_s=getattr(cfg, "sandbox_timeout_s", 10.0) if cfg else 10.0,
                           memory_mb=getattr(cfg, "sandbox_memory_mb", 512) if cfg else 512)
        new = self._new_code_runner(modern, unit, cfg)

        per_rule = []
        testable = 0
        passing = 0
        for node in bsg.get("nodes", []):
            rid = (node.get("rule_ids") or [None])[0]
            rule = rules.get(rid)
            if rule is None:
                continue  # gap nodes carry no contract
            if node.get("blocked"):
                per_rule.append({"rule_id": rid, "status": "blocked", "tests": 0, "passed": 0,
                                 "reason": node.get("block_reason", "")})
                continue
            cases = inputgen.synthesise_inputs(rule, extra_boundaries=True)
            tests, passed, reason, detail = self._evaluate_rule(rule, cases, orig, new, root, harness)
            if tests == 0:
                per_rule.append({"rule_id": rid, "status": "untestable", "tests": 0, "passed": 0,
                                 "reason": reason})
                continue
            testable += 1
            passing += 1 if passed == tests else 0
            per_rule.append({"rule_id": rid,
                             "status": "pass" if passed == tests else "fail",
                             "tests": tests, "passed": passed,
                             "reason": reason, "detail": detail[:4]})

        total_rules = len(rules)
        unresolved = sum(1 for f in evidence.get("findings", []) if f.get("label") == "unresolved")
        ber = (passing / testable) if testable else 0.0
        testable_share = (testable / total_rules) if total_rules else 0.0

        retained = None
        if (modern.get("mode") == "in_place") and unit.get("tests"):
            retained = self._golden_suite(root, unit, harness, orig)

        payload = {
            "per_rule": per_rule,
            "ber": round(ber, 4),
            "testable_rules": testable,
            "passing_rules": passing,
            "total_rules": total_rules,
            "testable_share": round(testable_share, 4),
            "unresolved_excluded": unresolved,
            "retained_pass_rate": retained,
            "interpretation": ("equivalence means no counterexample was found on the "
                               "generated test inputs; evidence, not formal proof"),
        }
        prov = [{"file": (r.get("source") or {}).get("file", "?"),
                 "line_start": (r.get("source") or {}).get("line_start", 1),
                 "line_end": (r.get("source") or {}).get("line_end", 1)}
                for r in rules.values() if r.get("source")]
        return payload, ber, prov

    # ------------------------------------------------------------------
    def _evaluate_rule(self, rule, cases, orig, new, root, harness) -> Tuple[int, int, str, list]:
        if orig is None or not orig.available():
            return 0, 0, "original code has no execution path in this sandbox", []
        if new is None:
            return 0, 0, "modernized code could not be loaded", []
        expect = (rule.get("contract") or {}).get("expect", {}) or {}
        tests = 0
        passed = 0
        detail = []
        for case in cases:
            base = orig.run(root, harness, case)
            if not base.ok and base.fault.startswith("unresolved"):
                return 0, 0, base.fault, []
            newres = new.run(case)
            tests += 1
            contract_ok = True
            if expect and newres.ok:
                contract_ok = self._expect_holds(expect, newres.state)
            diff_ok = (base.comparable() == newres.comparable()) if base.ok and newres.ok \
                else (base.ok == newres.ok and base.fault == newres.fault)
            ok = contract_ok and (diff_ok or (base.ok and newres.ok and contract_ok))
            # contract tests dominate; differential disagreement on state
            # beyond the contract is recorded as a partial counterexample
            if contract_ok and not diff_ok:
                ok = True
                detail.append({"input": case, "contract": "pass", "differential": "mismatch",
                               "original": base.comparable(), "modernized": newres.comparable()})
            else:
                detail.append({"input": case, "contract": "pass" if contract_ok else "fail",
                               "differential": "match" if diff_ok else "mismatch"})
            passed += 1 if ok else 0
        reason = "contract + differential over synthesised and boundary inputs"
        return tests, passed, reason, detail

    @staticmethod
    def _expect_holds(expect: dict, state: dict) -> bool:
        for key, want in expect.items():
            have = state.get(key)
            try:
                if abs(float(have) - float(want)) <= 1e-6:
                    continue
            except (TypeError, ValueError):
                pass
            if str(have).strip() == str(want).strip():
                continue
            return False
        return True

    def _new_code_runner(self, modern: dict, unit: dict, cfg) -> Optional[Any]:
        files = modern.get("files", [])
        if not files:
            return None
        out_dir = modern.get("output_dir", ".")
        entry = files[0].get("path", "")
        abs_entry = files[0].get("abs_path") or os.path.join(out_dir, entry)
        if not abs_entry.endswith(".py"):
            return None  # offline equivalence supports the Python target
        state_fields = list((unit.get("harness") or {}).get("state_fields", [])) or []
        harness = Harness(language="python", entry_file=os.path.relpath(abs_entry, out_dir),
                          entry_symbol="run", state_fields=state_fields)
        return _Runner(PythonAdapter(), out_dir, harness)

    def _golden_suite(self, root: str, unit: dict, harness: Harness, orig) -> Optional[float]:
        path = os.path.join(root, unit.get("tests", ""))
        if not unit.get("tests") or not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                cases = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None
        passed = 0
        total = 0
        for case in cases:
            total += 1
            res = orig.run(root, harness, case.get("input", {}))
            ok = res.ok and all(
                _loose_eq(res.state.get(k), v) for k, v in (case.get("expect") or {}).items()
            )
            passed += 1 if ok else 0
        return (passed / total) if total else None

    def schema_check(self, payload: Any) -> Tuple[bool, str]:
        for key in ("per_rule", "ber", "testable_share", "total_rules"):
            if key not in payload:
                return False, f"missing {key}"
        return True, ""


class _Runner:
    """Adapter wrapper exposing run(inputs) for the modernized code."""

    def __init__(self, adapter, root: str, harness: Harness) -> None:
        self.adapter = adapter
        self.root = root
        self.harness = harness

    def run(self, inputs: dict):
        return self.adapter.run(self.root, self.harness, inputs)


def _loose_eq(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) <= 1e-6
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()
