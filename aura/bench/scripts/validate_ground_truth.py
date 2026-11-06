#!/usr/bin/env python3
"""Validate benchmark ground truth mechanically (synopsis 6.6).

For every unit:

1. resolve each gold rule's ``anchor`` to a source span in the working copy
   (or in ``src/`` when no working copy exists yet);
2. execute every contract ``given`` through the unit harness and assert the
   ``expect`` fields match the behaviour of the real code;
3. run every golden test case and assert its expectations.

Injected false rules are validated too: each must be *wrong* on its given
input (that is the point of the safety-gate attack).  The script exits
non-zero if any check fails — the ground truth is correct by construction
*and* by verification.

Usage:  python bench/scripts/validate_ground_truth.py [unit-dir ...]
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
AURA_ROOT = os.path.dirname(BENCH)
sys.path.insert(0, AURA_ROOT)

from aura.skills.adapters import Harness, get_adapter  # noqa: E402


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def resolve_anchor(root: str, anchor: str) -> dict:
    """Find the first line of any file containing the anchor text."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("reference", "attacks", "tests", "work")]
        for fn in sorted(filenames):
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    for i, line in enumerate(fh, 1):
                        if anchor.strip() in line:
                            return {"file": os.path.relpath(path, root),
                                    "line_start": i, "line_end": i}
            except OSError:
                continue
    return {}


def expect_holds(expect: dict, state: dict, outputs: list) -> bool:
    for key, want in (expect or {}).items():
        if key == "_no_outputs":
            for w in (want if isinstance(want, list) else [want]):
                if any(str(w) in str(h) for h in outputs):
                    return False
            continue
        if key == "_outputs":
            want_list = want if isinstance(want, list) else [want]
            if not want_list:
                if outputs:
                    return False
                continue
            for w in want_list:
                if not any(str(w) in str(h) for h in outputs):
                    return False
            continue
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


def check_unit(unit_dir: str, expect_false: bool = False) -> tuple:
    meta = load_json(os.path.join(unit_dir, "meta.json"))
    root = os.path.join(unit_dir, "work") if os.path.isdir(os.path.join(unit_dir, "work")) else unit_dir
    problems = []
    checked = 0

    harnesses = meta.get("harnesses") or {}
    primary = Harness.from_dict(meta["harness"])

    def harness_for(rule):
        src = ((rule.get("source") or {}).get("file") or rule.get("anchor_file") or "")
        for key, h in harnesses.items():
            if src.endswith(key) or os.path.basename(src) == os.path.basename(key):
                return Harness.from_dict(h), key
        return primary, "primary"

    # ---- gold rules ---------------------------------------------------
    rules_path = os.path.join(unit_dir, meta["gold_rules"])
    rules = load_json(rules_path)["rules"]
    adapter_cache = {}

    def run_case(h: Harness, inputs: dict):
        if h.language not in adapter_cache:
            adapter_cache[h.language] = get_adapter(h.language)
        return adapter_cache[h.language].run(root, h, inputs)

    for rule in rules:
        span = resolve_anchor(root, rule.get("anchor", ""))
        if not span:
            problems.append(f"{rule['id']}: anchor not found: {rule.get('anchor')!r}")
            continue
        rule["source"] = span
        h, hkey = harness_for({**rule, "source": span})
        res = run_case(h, rule["contract"]["given"])
        checked += 1
        if not res.ok:
            problems.append(f"{rule['id']} [{hkey}]: execution fault: {res.fault}")
            continue
        ok = expect_holds(rule["contract"]["expect"], res.state, res.outputs)
        if expect_false:
            if ok:
                problems.append(f"{rule['id']}: expected this false rule to FAIL on its given, but it held")
        else:
            if not ok:
                problems.append(
                    f"{rule['id']} [{hkey}]: contract violated — given={rule['contract']['given']} "
                    f"expect={rule['contract']['expect']} state={res.state} outputs={res.outputs}"
                )

    # ---- injected false rules ------------------------------------------
    attacks_path = os.path.join(unit_dir, meta.get("attacks", "") or "")
    if meta.get("attacks") and os.path.exists(attacks_path):
        for rule in load_json(attacks_path)["rules"]:
            span = resolve_anchor(root, rule.get("anchor", ""))
            if not span:
                problems.append(f"{rule['id']}: anchor not found: {rule.get('anchor')!r}")
                continue
            rule["source"] = span
            h, hkey = harness_for({**rule, "source": span})
            res = run_case(h, rule["contract"]["given"])
            checked += 1
            if not res.ok:
                continue  # a fault also means the false claim does not hold
            ok = expect_holds(rule["contract"]["expect"], res.state, res.outputs)
            if ok:
                problems.append(f"{rule['id']}: false rule unexpectedly HOLDS on its given")

    # ---- golden tests ---------------------------------------------------
    tests_path = os.path.join(unit_dir, meta["tests"])
    if os.path.exists(tests_path):
        for case in load_json(tests_path):
            h = Harness.from_dict(harnesses.get(case.get("harness", ""), meta["harness"]))
            res = run_case(h, case["input"])
            checked += 1
            if not res.ok:
                problems.append(f"golden {case['name']!r}: execution fault: {res.fault}")
                continue
            if not expect_holds(case["expect"], res.state, res.outputs):
                problems.append(
                    f"golden {case['name']!r}: expect={case['expect']} "
                    f"state={res.state} outputs={res.outputs}"
                )

    return checked, problems


def main() -> int:
    args = sys.argv[1:]
    if not args:
        args = [os.path.join(BENCH, "dialects", d) for d in sorted(os.listdir(os.path.join(BENCH, "dialects")))]
        args += [os.path.join(BENCH, "projects", p) for p in sorted(os.listdir(os.path.join(BENCH, "projects")))]
        args = [a for a in args if os.path.isdir(a)]
    total_bad = 0
    for unit_dir in args:
        checked, problems = check_unit(unit_dir)
        status = "OK" if not problems else "PROBLEMS"
        print(f"[{status}] {os.path.relpath(unit_dir, BENCH)}: {checked} checks")
        for p in problems:
            print(f"    - {p}")
        total_bad += len(problems)
    if total_bad:
        print(f"\n{total_bad} problem(s) found.")
        return 1
    print("\nAll ground truth verified against the code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
