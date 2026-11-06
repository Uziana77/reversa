"""Modernized from legacy unit go_inventory (AURA specification-driven generation).

Every function below implements one node of the Behavioural
Specification Graph. Guard clauses render preconditions; the
effects and decision tables render the postconditions and the
given/expect pairs captured by executing the original legacy code.
REVIEW/TODO markers mark constructs that were not rendered rather
than guessed.
"""

from __future__ import annotations

class RuleViolation(Exception):
    pass

def _n(x):
    if isinstance(x, bool):
        return 1 if x else 0
    if isinstance(x, (int, float)):
        return x
    s = str(x).strip().upper()
    if s in ("ON", "TRUE", "YES", "P"):
        return 1
    if s in ("OFF", "FALSE", "NO", "Z"):
        return 0
    try:
        return float(s)
    except ValueError:
        return None


def _eq(a, b):
    if a == b:
        return True
    if str(a).strip() == str(b).strip():
        return True
    na, nb = _n(a), _n(b)
    return na is not None and nb is not None and abs(float(na) - float(nb)) < 1e-9


def _eq_any(a, vals):
    return any(_eq(a, v) for v in vals)


def N_BR_005(state: dict) -> dict:
    """In priceOrder, total is computed as units * unitPrice

    Preconditions:
      - inputs available: units, unitPrice

    Postconditions:
      - total = units * unitPrice
    (confidence_state=confirmed_dynamic)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: units, unitPrice
    s["total"] = ((s.get("units") or 0) * (s.get("unitPrice") or 0))
    # rule BR-005: In priceOrder, total is computed as units * unitPrice.
    if _eq(s.get("units"), 1) and _eq(s.get("unitPrice"), 1):
        s["total"] = 1
    return s


def N_BR_007(state: dict) -> dict:
    """In priceOrder, net is computed as total - discount

    Preconditions:
      - inputs available: total, discount

    Postconditions:
      - net = total - discount
    (confidence_state=confirmed_dynamic)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: total, discount
    s["net"] = ((s.get("total") or 0) - (s.get("discount") or 0))
    # rule BR-007: In priceOrder, net is computed as total - discount.
    if _eq(s.get("total"), 1) and _eq(s.get("discount"), 1):
        s["net"] = 0
    return s


NODE_REGISTRY = {
    "N-BR-005": N_BR_005,
    "N-BR-007": N_BR_007,
}


def run(state: dict) -> dict:
    """Run every non-blocked node in sequence (BSG control flow).
    A node whose preconditions do not hold does not fire (its
    rule simply does not apply to this input): skipped, not raised."""
    s = dict(state)
    try:
        s = N_BR_005(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_007(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    return s
