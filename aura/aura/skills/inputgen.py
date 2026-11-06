"""Input synthesis skill for the Dynamic Evidence Agent (synopsis 6.1)."""

from __future__ import annotations

import json
from typing import Any, Dict, List


def synthesise_inputs(rule: dict, *, extra_boundaries: bool = False) -> List[Dict[str, Any]]:
    """Build execution inputs for one rule.

    The primary input is the rule's contract ``given`` pair (captured from
    the code).  Boundary variants (0, 1, -1, tens, string edge cases) extend
    coverage; the same deterministic set is reused by the Equivalence
    Validator so original and modernized code see identical inputs.
    """
    cases: List[Dict[str, Any]] = []
    contract = rule.get("contract") or {}
    given = dict(contract.get("given", {}) or {})
    if given:
        cases.append(given)
    names = list(given) or list(rule.get("inputs", []) or [])
    for name in names:
        base = given.get(name, 1)
        for val in _variants(base):
            c = dict(given)
            c[name] = val
            cases.append(c)
    if not cases:
        cases.append({})
    if not extra_boundaries:
        # keep the deterministic core set small
        cases = cases[:12]
    seen = set()
    uniq = []
    for c in cases:
        key = json.dumps(c, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq[:24]


def _variants(base: Any) -> List[Any]:
    out: List[Any] = []
    if isinstance(base, bool):
        return [not base]
    if isinstance(base, (int, float)):
        b = float(base)
        for v in (0, 1, -1, b - 1, b + 1, b / 2.0, b * 2.0, 9999):
            iv = int(v) if float(v).is_integer() else v
            if iv != base:
                out.append(iv)
        return out
    if isinstance(base, str):
        for s in ("", "X", "A" * 8, "0"):
            if s != base:
                out.append(s)
        return out
    if isinstance(base, list):
        # list-shaped inputs (record collections): perturb length and items
        out.append([])
        if len(base) > 1:
            out.append(base[1:])
        longer = list(base) + [dict(base[0]) if isinstance(base[0], dict) else base[0]]
        out.append(longer)
        if base and isinstance(base[0], dict):
            bumped = []
            for item in base[:2]:
                it = dict(item)
                for k, v in it.items():
                    if isinstance(v, (int, float)):
                        it[k] = v + 1
                        break
                bumped.append(it)
            out.append(list(base) + bumped)
        return out
    return [0, 1]
