"""Modernized from legacy unit react_orders (AURA specification-driven generation).

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
    """In shippingFor, if (country === "US") then return 500;

    Preconditions:
      - (country === "US")

    Postconditions:
      - return 500;
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: (country === "US")
    # REVIEW: postcondition not machine-renderable: return 500;
    # TODO: no machine-renderable effect for node N-BR-005
    return s


def N_BR_006(state: dict) -> dict:
    """In shippingFor, if (country === "CA") then return 1200;

    Preconditions:
      - (country === "CA")

    Postconditions:
      - return 1200;
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: (country === "CA")
    # REVIEW: postcondition not machine-renderable: return 1200;
    # TODO: no machine-renderable effect for node N-BR-006
    return s


NODE_REGISTRY = {
    "N-BR-005": N_BR_005,
    "N-BR-006": N_BR_006,
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
        s = N_BR_006(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    return s
