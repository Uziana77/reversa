"""Modernized from legacy unit java_billing (AURA specification-driven generation).

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


def N_BR_001(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: months, monthlyRate

    Postconditions:
      - baseAmount = months * monthlyRate
    (confidence_state=confirmed_dynamic)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: months, monthlyRate
    s["baseAmount"] = ((s.get("months") or 0) * (s.get("monthlyRate") or 0))
    # rule BR-001: In Billing.compute, baseAmount is computed as months * monthlyRate.
    if _eq(s.get("months"), 1) and _eq(s.get("monthlyRate"), 1):
        s["baseAmount"] = 1
    return s


def N_BR_002(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: months, seats, seatPrice

    Postconditions:
      - seatAmount = months * seats * seatPrice
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: months, seats, seatPrice
    s["seatAmount"] = ((s.get("months") or 0) * (s.get("seats") or 0) * (s.get("seatPrice") or 0))
    # rule BR-002: In Billing.compute, seatAmount is computed as months * seats * seatPrice.
    if _eq(s.get("months"), 1) and _eq(s.get("seats"), 1) and _eq(s.get("seatPrice"), 1):
        s["seatAmount"] = 1
    return s


def N_BR_004(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: constant

    Postconditions:
      - discount = 0
    (confidence_state=confirmed_dynamic)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: constant
    s["discount"] = 0
    # rule BR-004: In Billing.compute, discount is computed as 0.
    if _eq(s.get("input"), 0):
        s["discount"] = 0
    return s


def N_BR_007(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: constant

    Postconditions:
      - lateFee = 0
    (confidence_state=confirmed_dynamic)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: constant
    s["lateFee"] = 0
    # rule BR-007: In Billing.compute, lateFee is computed as 0.
    if _eq(s.get("input"), 0):
        s["lateFee"] = 0
    return s


def N_BR_008(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: lateDays

    Postconditions:
      - lateFee = 500 + lateDays * 100
    (confidence_state=confirmed_dynamic)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: lateDays
    s["lateFee"] = (500 + (s.get("lateDays") or 0) * 100)
    # rule BR-008: In Billing.compute, lateFee is computed as 500 + lateDays * 100.
    if _eq(s.get("lateDays"), 100):
        s["lateFee"] = 10500
    return s


def N_BR_013(state: dict) -> dict:
    """In Invoice

    Preconditions:
      - inputs available: constant

    Postconditions:
      - taxAmount = 0
    (confidence_state=confirmed_dynamic)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: constant
    s["taxAmount"] = 0
    # rule BR-013: In Invoice.compute, taxAmount is computed as 0.
    if _eq(s.get("input"), 0):
        s["taxAmount"] = 0
    return s


def N_BR_014(state: dict) -> dict:
    """In Invoice

    Preconditions:
      - inputs available: lineAmount, taxRate

    Postconditions:
      - taxAmount = lineAmount * taxRate / 100
    (confidence_state=confirmed_dynamic)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: lineAmount, taxRate
    s["taxAmount"] = ((s.get("lineAmount") or 0) * (s.get("taxRate") or 0) / 100)
    # rule BR-014: In Invoice.compute, taxAmount is computed as lineAmount * taxRate / 100.
    if _eq(s.get("lineAmount"), 100) and _eq(s.get("taxRate"), 1):
        s["taxAmount"] = 1.0
    return s


def N_BR_015(state: dict) -> dict:
    """In Invoice

    Preconditions:
      - inputs available: constant

    Postconditions:
      - shipping = 900
    (confidence_state=confirmed_dynamic)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: constant
    s["shipping"] = 900
    # rule BR-015: In Invoice.compute, shipping is computed as 900.
    if _eq(s.get("input"), 900):
        s["shipping"] = 900
    return s


NODE_REGISTRY = {
    "N-BR-001": N_BR_001,
    "N-BR-002": N_BR_002,
    "N-BR-004": N_BR_004,
    "N-BR-007": N_BR_007,
    "N-BR-008": N_BR_008,
    "N-BR-013": N_BR_013,
    "N-BR-014": N_BR_014,
    "N-BR-015": N_BR_015,
}


def run(state: dict) -> dict:
    """Run every non-blocked node in sequence (BSG control flow).
    A node whose preconditions do not hold does not fire (its
    rule simply does not apply to this input): skipped, not raised."""
    s = dict(state)
    try:
        s = N_BR_001(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_002(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_004(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_007(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_008(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_013(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_014(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_015(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    return s
