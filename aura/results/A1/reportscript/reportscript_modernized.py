"""Modernized from legacy unit reportscript (AURA specification-driven generation).

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
    """In returns

    Preconditions:
      - RET_AMOUNT > GROSS

    Postconditions:
      - LET REFUND = GROSS.
    (confidence_state=confirmed_static)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: RET_AMOUNT > GROSS
    # REVIEW: postcondition not machine-renderable: LET REFUND = GROSS.
    # TODO: no machine-renderable effect for node N-BR-001
    return s


def N_BR_002(state: dict) -> dict:
    """In sales

    Preconditions:
      - REC_REGION = 'NORTH'

    Postconditions:
      - ACCUMULATE REC_AMOUNT INTO REGION-NORTH.
    (confidence_state=confirmed_static)
    """
    s = dict(state)
    if not _eq(s.get("REC_REGION"), "NORTH"):
        raise RuleViolation("precondition failed: REC_REGION = 'NORTH'")
    # REVIEW: postcondition not machine-renderable: ACCUMULATE REC_AMOUNT INTO REGION-NORTH.
    # TODO: no machine-renderable effect for node N-BR-002
    return s


def N_BR_003(state: dict) -> dict:
    """In sales

    Preconditions:
      - REC_AMOUNT > 100

    Postconditions:
      - LET HIGH-COUNT = HIGH-COUNT + 1.
    (confidence_state=confirmed_static)
    """
    s = dict(state)
    if not ((s.get("REC_AMOUNT") or 0) > 100):
        raise RuleViolation("precondition failed: REC_AMOUNT > 100")
    # REVIEW: postcondition not machine-renderable: LET HIGH-COUNT = HIGH-COUNT + 1.
    # TODO: no machine-renderable effect for node N-BR-003
    return s


def N_BR_004(state: dict) -> dict:
    """In sales

    Preconditions:
      - REC_QTY > 10

    Postconditions:
      - LET DISCOUNT = REC_AMOUNT * 0.9.
    (confidence_state=confirmed_static)
    """
    s = dict(state)
    if not ((s.get("REC_QTY") or 0) > 10):
        raise RuleViolation("precondition failed: REC_QTY > 10")
    # REVIEW: postcondition not machine-renderable: LET DISCOUNT = REC_AMOUNT * 0.9.
    # TODO: no machine-renderable effect for node N-BR-004
    return s


def N_BR_005(state: dict) -> dict:
    """In sales

    Preconditions:
      - REC_REP = 'ANA'

    Postconditions:
      - LET COMM = DISCOUNT * 0.05.
    (confidence_state=confirmed_static)
    """
    s = dict(state)
    if not _eq(s.get("REC_REP"), "ANA"):
        raise RuleViolation("precondition failed: REC_REP = 'ANA'")
    # REVIEW: postcondition not machine-renderable: LET COMM = DISCOUNT * 0.05.
    # TODO: no machine-renderable effect for node N-BR-005
    return s


def N_BR_006(state: dict) -> dict:
    """In sales

    Preconditions:
      - REC_AMOUNT > TOP-AMT

    Postconditions:
      - LET TOP-AMT = REC_AMOUNT.
    (confidence_state=confirmed_static)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: REC_AMOUNT > TOP-AMT
    # REVIEW: postcondition not machine-renderable: LET TOP-AMT = REC_AMOUNT.
    # TODO: no machine-renderable effect for node N-BR-006
    return s


NODE_REGISTRY = {
    "N-BR-001": N_BR_001,
    "N-BR-002": N_BR_002,
    "N-BR-003": N_BR_003,
    "N-BR-004": N_BR_004,
    "N-BR-005": N_BR_005,
    "N-BR-006": N_BR_006,
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
    return s
