"""Modernized from legacy unit interlock (AURA specification-driven generation).

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
    """In aux

    Preconditions:
      - ALARM_HORN = ON AND HORN_SILENCE = 1

    Postconditions:
      - SET ALARM_HORN TO OFF.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not (_eq(s.get("ALARM_HORN"), "ON") and _eq(s.get("HORN_SILENCE"), 1)):
        raise RuleViolation("precondition failed: ALARM_HORN = ON AND HORN_SILENCE = 1")
    s["ALARM_HORN"] = 0
    return s


def N_BR_002(state: dict) -> dict:
    """In aux

    Preconditions:
      - PRESSURE > 220

    Postconditions:
      - TRIP FURNACE REASON 'pressure critical'.
    (confidence_state=contradicted)
    """
    s = dict(state)
    if not ((s.get("PRESSURE") or 0) > 220):
        raise RuleViolation("precondition failed: PRESSURE > 220")
    # REVIEW: postcondition not machine-renderable: TRIP FURNACE REASON 'pressure critical'.
    # TODO: no machine-renderable effect for node N-BR-002
    return s


def N_BR_003(state: dict) -> dict:
    """In aux

    Preconditions:
      - ESCALATION = 1 AND SHIFT_NIGHT = 1

    Postconditions:
      - SET CALL_SUPERVISOR TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not (_eq(s.get("ESCALATION"), 1) and _eq(s.get("SHIFT_NIGHT"), 1)):
        raise RuleViolation("precondition failed: ESCALATION = 1 AND SHIFT_NIGHT = 1")
    s["CALL_SUPERVISOR"] = 1
    return s


def N_BR_004(state: dict) -> dict:
    """In aux

    Preconditions:
      - RESET_REQUEST = 1 AND DOOR_CLOSED = 1 AND PRESSURE < 100

    Postconditions:
      - SET RESET_PERM TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((_eq(s.get("RESET_REQUEST"), 1) and _eq(s.get("DOOR_CLOSED"), 1)) and ((s.get("PRESSURE") or 0) < 100)):
        raise RuleViolation("precondition failed: RESET_REQUEST = 1 AND DOOR_CLOSED = 1 AND PRESSURE < 100")
    s["RESET_PERM"] = 1
    return s


def N_BR_005(state: dict) -> dict:
    """In main

    Preconditions:
      - MODE_KNOB = 2 AND DOOR_CLOSED = 1 AND GUARD_SENSOR = 1

    Postconditions:
      - SET START_PERM TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((_eq(s.get("MODE_KNOB"), 2) and _eq(s.get("DOOR_CLOSED"), 1)) and _eq(s.get("GUARD_SENSOR"), 1)):
        raise RuleViolation("precondition failed: MODE_KNOB = 2 AND DOOR_CLOSED = 1 AND GUARD_SENSOR = 1")
    s["START_PERM"] = 1
    return s


def N_BR_006(state: dict) -> dict:
    """In main

    Preconditions:
      - PRESSURE > 180

    Postconditions:
      - SET RELIEF TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("PRESSURE") or 0) > 180):
        raise RuleViolation("precondition failed: PRESSURE > 180")
    s["RELIEF"] = 1
    return s


def N_BR_007(state: dict) -> dict:
    """In main

    Preconditions:
      - TEMPERATURE > 90

    Postconditions:
      - SET COOLING TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("TEMPERATURE") or 0) > 90):
        raise RuleViolation("precondition failed: TEMPERATURE > 90")
    s["COOLING"] = 1
    return s


def N_BR_008(state: dict) -> dict:
    """In main

    Preconditions:
      - TEMPERATURE < 60

    Postconditions:
      - SET COOLING TO OFF.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("TEMPERATURE") or 0) < 60):
        raise RuleViolation("precondition failed: TEMPERATURE < 60")
    s["COOLING"] = 0
    return s


def N_BR_009(state: dict) -> dict:
    """In main

    Preconditions:
      - PRESSURE > 200 OR TEMPERATURE > 100

    Postconditions:
      - TRIP COMPRESSOR REASON 'critical'.
    (confidence_state=contradicted)
    """
    s = dict(state)
    if not (((s.get("PRESSURE") or 0) > 200) or ((s.get("TEMPERATURE") or 0) > 100)):
        raise RuleViolation("precondition failed: PRESSURE > 200 OR TEMPERATURE > 100")
    # REVIEW: postcondition not machine-renderable: TRIP COMPRESSOR REASON 'critical'.
    # TODO: no machine-renderable effect for node N-BR-009
    return s


def N_BR_010(state: dict) -> dict:
    """In main

    Preconditions:
      - MOTOR_SPEED > 3000 AND GUARD_SENSOR = 0

    Postconditions:
      - SET MOTOR_CUT TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not (((s.get("MOTOR_SPEED") or 0) > 3000) and _eq(s.get("GUARD_SENSOR"), 0)):
        raise RuleViolation("precondition failed: MOTOR_SPEED > 3000 AND GUARD_SENSOR = 0")
    s["MOTOR_CUT"] = 1
    return s


def N_BR_011(state: dict) -> dict:
    """In main

    Preconditions:
      - MOTOR_SPEED > 3800

    Postconditions:
      - SET MOTOR_CUT TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not ((s.get("MOTOR_SPEED") or 0) > 3800):
        raise RuleViolation("precondition failed: MOTOR_SPEED > 3800")
    s["MOTOR_CUT"] = 1
    return s


def N_BR_012(state: dict) -> dict:
    """In main

    Preconditions:
      - SHIFT_NIGHT = 1 AND RELIEF = ON

    Postconditions:
      - SET ALARM_HORN TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not (_eq(s.get("SHIFT_NIGHT"), 1) and _eq(s.get("RELIEF"), "ON")):
        raise RuleViolation("precondition failed: SHIFT_NIGHT = 1 AND RELIEF = ON")
    s["ALARM_HORN"] = 1
    return s


def N_BR_013(state: dict) -> dict:
    """In main

    Preconditions:
      - VENT_OPEN = 1 AND PRESSURE > 150

    Postconditions:
      - SET VENT_PERM TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not (_eq(s.get("VENT_OPEN"), 1) and ((s.get("PRESSURE") or 0) > 150)):
        raise RuleViolation("precondition failed: VENT_OPEN = 1 AND PRESSURE > 150")
    s["VENT_PERM"] = 1
    return s


def N_BR_014(state: dict) -> dict:
    """In main

    Preconditions:
      - START_PERM = ON AND MOTOR_CUT = ON

    Postconditions:
      - SET START_PERM TO OFF.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not (_eq(s.get("START_PERM"), "ON") and _eq(s.get("MOTOR_CUT"), "ON")):
        raise RuleViolation("precondition failed: START_PERM = ON AND MOTOR_CUT = ON")
    s["START_PERM"] = 0
    return s


def N_BR_015(state: dict) -> dict:
    """In main

    Preconditions:
      - MODE_KNOB = 2 AND TEMPERATURE > 85

    Postconditions:
      - SET COOLING TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not (_eq(s.get("MODE_KNOB"), 2) and ((s.get("TEMPERATURE") or 0) > 85)):
        raise RuleViolation("precondition failed: MODE_KNOB = 2 AND TEMPERATURE > 85")
    s["COOLING"] = 1
    return s


def N_BR_016(state: dict) -> dict:
    """In main

    Preconditions:
      - ALARM_HORN = ON OR VENT_PERM = ON

    Postconditions:
      - SET ANNUNCIATE TO ON.
    (confidence_state=confirmed_both)
    """
    s = dict(state)
    if not (_eq(s.get("ALARM_HORN"), "ON") or _eq(s.get("VENT_PERM"), "ON")):
        raise RuleViolation("precondition failed: ALARM_HORN = ON OR VENT_PERM = ON")
    s["ANNUNCIATE"] = 1
    return s


def N_GAP_001(state: dict) -> dict:
    """uncovered code path: meta.json
    (confidence_state=gap)
    """
    s = dict(state)
    # TODO: no machine-renderable effect for node N-GAP-001
    return s


def N_GAP_002(state: dict) -> dict:
    """uncovered code path: work_manifest.json
    (confidence_state=gap)
    """
    s = dict(state)
    # TODO: no machine-renderable effect for node N-GAP-002
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
    "N-GAP-001": N_GAP_001,
    "N-GAP-002": N_GAP_002,
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
        s = N_GAP_001(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_GAP_002(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    return s
