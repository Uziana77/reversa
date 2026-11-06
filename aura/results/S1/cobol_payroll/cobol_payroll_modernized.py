"""Modernized from legacy unit cobol_payroll (AURA specification-driven generation).

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
    """In PAYROLL

    Preconditions:
      - HOURS-WORKED > 40

    Postconditions:
      - COMPUTE BASE-PAY = 40 * PAY-RATE
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("HOURS-WORKED") or 0) > 40):
        raise RuleViolation("precondition failed: HOURS-WORKED > 40")
    # REVIEW: postcondition not machine-renderable: COMPUTE BASE-PAY = 40 * PAY-RATE
    # TODO: no machine-renderable effect for node N-BR-001
    return s


def N_BR_002(state: dict) -> dict:
    """In PAYROLL

    Preconditions:
      - SHIFT-CODE = 2

    Postconditions:
      - COMPUTE SHIFT-PREMIUM = BASE-PAY * 0.10
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not _eq(s.get("SHIFT-CODE"), 2):
        raise RuleViolation("precondition failed: SHIFT-CODE = 2")
    # REVIEW: postcondition not machine-renderable: COMPUTE SHIFT-PREMIUM = BASE-PAY * 0.10
    # TODO: no machine-renderable effect for node N-BR-002
    return s


def N_BR_003(state: dict) -> dict:
    """In PAYROLL

    Preconditions:
      - YEARS-OF-SERVICE >= 10

    Postconditions:
      - COMPUTE BONUS-AMT = BASE-PAY * 0.05
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("YEARS-OF-SERVICE") or 0) >= 10):
        raise RuleViolation("precondition failed: YEARS-OF-SERVICE >= 10")
    # REVIEW: postcondition not machine-renderable: COMPUTE BONUS-AMT = BASE-PAY * 0.05
    # TODO: no machine-renderable effect for node N-BR-003
    return s


def N_BR_004(state: dict) -> dict:
    """In PAYROLL

    Preconditions:
      - ABSENT-DAYS > 0

    Postconditions:
      - COMPUTE PENALTY = ABSENT-DAYS * 20
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("ABSENT-DAYS") or 0) > 0):
        raise RuleViolation("precondition failed: ABSENT-DAYS > 0")
    # REVIEW: postcondition not machine-renderable: COMPUTE PENALTY = ABSENT-DAYS * 20
    # TODO: no machine-renderable effect for node N-BR-004
    return s


def N_BR_005(state: dict) -> dict:
    """In PAYROLL

    Preconditions:
      - NET-PAY > 0

    Postconditions:
      - MOVE 'P' TO PAY-STATUS
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("NET-PAY") or 0) > 0):
        raise RuleViolation("precondition failed: NET-PAY > 0")
    # REVIEW: postcondition not machine-renderable: MOVE 'P' TO PAY-STATUS
    # TODO: no machine-renderable effect for node N-BR-005
    return s


def N_BR_006(state: dict) -> dict:
    """In PAYRPT

    Preconditions:
      - GROSS-PAY > 0

    Postconditions:
      - DISPLAY 'SLIP GROSS=' GROSS-PAY
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("GROSS-PAY") or 0) > 0):
        raise RuleViolation("precondition failed: GROSS-PAY > 0")
    # REVIEW: postcondition not machine-renderable: DISPLAY 'SLIP GROSS=' GROSS-PAY
    # TODO: no machine-renderable effect for node N-BR-006
    return s


def N_BR_007(state: dict) -> dict:
    """In PAYRPT

    Preconditions:
      - TAX-AMT > 0

    Postconditions:
      - DISPLAY 'TAX=' TAX-AMT
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("TAX-AMT") or 0) > 0):
        raise RuleViolation("precondition failed: TAX-AMT > 0")
    # REVIEW: postcondition not machine-renderable: DISPLAY 'TAX=' TAX-AMT
    # TODO: no machine-renderable effect for node N-BR-007
    return s


def N_BR_008(state: dict) -> dict:
    """In PAYRPT

    Preconditions:
      - NET-PAY > 0

    Postconditions:
      - DISPLAY 'NET=' NET-PAY
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("NET-PAY") or 0) > 0):
        raise RuleViolation("precondition failed: NET-PAY > 0")
    # REVIEW: postcondition not machine-renderable: DISPLAY 'NET=' NET-PAY
    # TODO: no machine-renderable effect for node N-BR-008
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
    return s
