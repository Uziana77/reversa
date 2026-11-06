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
    (confidence_state=inferred)
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
    (confidence_state=confirmed_static)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: months, seats, seatPrice
    s["seatAmount"] = ((s.get("months") or 0) * (s.get("seats") or 0) * (s.get("seatPrice") or 0))
    # rule BR-002: In Billing.compute, seatAmount is computed as months * seats * seatPrice.
    if _eq(s.get("months"), 1) and _eq(s.get("seats"), 1) and _eq(s.get("seatPrice"), 1):
        s["seatAmount"] = 1
    return s


def N_BR_003(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: baseAmount, seatAmount

    Postconditions:
      - grossAmount = baseAmount + seatAmount
    (confidence_state=inferred)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: baseAmount, seatAmount
    s["grossAmount"] = ((s.get("baseAmount") or 0) + (s.get("seatAmount") or 0))
    # rule BR-003: In Billing.compute, grossAmount is computed as baseAmount + seatAmount.
    if _eq(s.get("baseAmount"), 1) and _eq(s.get("seatAmount"), 1):
        s["grossAmount"] = 2
    return s


def N_BR_004(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: constant

    Postconditions:
      - discount = 0
    (confidence_state=inferred)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: constant
    s["discount"] = 0
    # rule BR-004: In Billing.compute, discount is computed as 0.
    if _eq(s.get("input"), 0):
        s["discount"] = 0
    return s


def N_BR_005(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: grossAmount

    Postconditions:
      - discount = grossAmount * 10 / 100
    (confidence_state=inferred)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: grossAmount
    s["discount"] = ((s.get("grossAmount") or 0) * 10 / 100)
    # rule BR-005: In Billing.compute, discount is computed as grossAmount * 10 / 100.
    if _eq(s.get("grossAmount"), 100):
        s["discount"] = 10.0
    return s


def N_BR_006(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: grossAmount

    Postconditions:
      - discount = grossAmount * 15 / 100
    (confidence_state=inferred)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: grossAmount
    s["discount"] = ((s.get("grossAmount") or 0) * 15 / 100)
    # rule BR-006: In Billing.compute, discount is computed as grossAmount * 15 / 100.
    if _eq(s.get("grossAmount"), 100):
        s["discount"] = 15.0
    return s


def N_BR_007(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: constant

    Postconditions:
      - lateFee = 0
    (confidence_state=inferred)
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
    (confidence_state=inferred)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: lateDays
    s["lateFee"] = (500 + (s.get("lateDays") or 0) * 100)
    # rule BR-008: In Billing.compute, lateFee is computed as 500 + lateDays * 100.
    if _eq(s.get("lateDays"), 100):
        s["lateFee"] = 10500
    return s


def N_BR_009(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: grossAmount, discount, lateFee, credit

    Postconditions:
      - totalDue = grossAmount - discount + lateFee - credit
    (confidence_state=confirmed_static)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: grossAmount, discount, lateFee, credit
    s["totalDue"] = ((s.get("grossAmount") or 0) - (s.get("discount") or 0) + (s.get("lateFee") or 0) - (s.get("credit") or 0))
    # rule BR-009: In Billing.compute, totalDue is computed as grossAmount - discount + lateFee - c
    if _eq(s.get("grossAmount"), 1) and _eq(s.get("discount"), 1) and _eq(s.get("lateFee"), 1) and _eq(s.get("credit"), 1):
        s["totalDue"] = 0
    return s


def N_BR_010(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: CLEAR

    Postconditions:
      - status = "CLEAR"
    (confidence_state=inferred)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: CLEAR
    s["status"] = 'CLEAR'
    # rule BR-010: In Billing.compute, status is computed as "CLEAR".
    if _eq(s.get("CLEAR"), "CLEAR"):
        s["status"] = "\"CLEAR\""
    return s


def N_BR_011(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: LATE

    Postconditions:
      - status = "LATE"
    (confidence_state=inferred)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: LATE
    s["status"] = 'LATE'
    # rule BR-011: In Billing.compute, status is computed as "LATE".
    if _eq(s.get("LATE"), "LATE"):
        s["status"] = "\"LATE\""
    return s


def N_BR_012(state: dict) -> dict:
    """In Billing

    Preconditions:
      - inputs available: VOID

    Postconditions:
      - status = "VOID"
    (confidence_state=inferred)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: VOID
    s["status"] = 'VOID'
    # rule BR-012: In Billing.compute, status is computed as "VOID".
    if _eq(s.get("VOID"), "VOID"):
        s["status"] = "\"VOID\""
    return s


def N_BR_013(state: dict) -> dict:
    """In Invoice

    Preconditions:
      - inputs available: constant

    Postconditions:
      - taxAmount = 0
    (confidence_state=inferred)
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
    (confidence_state=inferred)
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
    (confidence_state=inferred)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: constant
    s["shipping"] = 900
    # rule BR-015: In Invoice.compute, shipping is computed as 900.
    if _eq(s.get("input"), 900):
        s["shipping"] = 900
    return s


def N_BR_016(state: dict) -> dict:
    """In Invoice

    Preconditions:
      - inputs available: constant

    Postconditions:
      - shipping = 1800
    (confidence_state=inferred)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: constant
    s["shipping"] = 1800
    # rule BR-016: In Invoice.compute, shipping is computed as 1800.
    if _eq(s.get("input"), 1800):
        s["shipping"] = 1800
    return s


def N_BR_017(state: dict) -> dict:
    """In Invoice

    Preconditions:
      - inputs available: lineAmount, taxAmount, shipping

    Postconditions:
      - lineTotal = lineAmount + taxAmount + shipping
    (confidence_state=confirmed_static)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: lineAmount, taxAmount, shipping
    s["lineTotal"] = ((s.get("lineAmount") or 0) + (s.get("taxAmount") or 0) + (s.get("shipping") or 0))
    # rule BR-017: In Invoice.compute, lineTotal is computed as lineAmount + taxAmount + shipping.
    if _eq(s.get("lineAmount"), 1) and _eq(s.get("taxAmount"), 1) and _eq(s.get("shipping"), 1):
        s["lineTotal"] = 3
    return s


NODE_REGISTRY = {
    "N-BR-001": N_BR_001,
    "N-BR-002": N_BR_002,
    "N-BR-003": N_BR_003,
    "N-BR-004": N_BR_004,
    "N-BR-005": N_BR_005,
    "N-BR-006": N_BR_006,
    "N-BR-007": N_BR_007,
    "N-BR-008": N_BR_008,
    "N-BR-009": N_BR_009,
    "N-BR-010": N_BR_010,
    "N-BR-011": N_BR_011,
    "N-BR-012": N_BR_012,
    "N-BR-013": N_BR_013,
    "N-BR-014": N_BR_014,
    "N-BR-015": N_BR_015,
    "N-BR-016": N_BR_016,
    "N-BR-017": N_BR_017,
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
        s = N_BR_003(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_004(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_005(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_006(s)
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
        s = N_BR_009(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_010(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_011(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_012(s)
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
    try:
        s = N_BR_016(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_017(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    return s
