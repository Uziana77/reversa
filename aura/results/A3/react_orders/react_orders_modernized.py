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


def N_BR_001(state: dict) -> dict:
    """In OrderTable

    Preconditions:
      - inputs available: props, lines

    Postconditions:
      - lines = this.props.lines || [];
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: props, lines
    # REVIEW: postcondition not machine-renderable: lines = this.props.lines || [];
    # rule BR-001: In OrderTable.anon@18, lines is computed as this.props.lines || [];.
    if _eq(s.get("props"), 1) and _eq(s.get("lines"), 1):
        s["lines"] = "this.1.1 || [];"
    return s


def N_BR_002(state: dict) -> dict:
    """In lineTotal, if (line

    Preconditions:
      - (line.qty > 10)

    Postconditions:
      - amount = amount - Math.floor(amount / 10);
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: (line.qty > 10)
    # REVIEW: postcondition not machine-renderable: amount = amount - Math.floor(amount / 10);
    # rule BR-002: In lineTotal, if (line.qty > 10) then amount = amount - Math.floor(amount / 10);
    if _eq(s.get("qty"), 10) and _eq(s.get("line"), 1):
        s["amount"] = "amount - Math.floor(amount / 10);"
    return s


def N_BR_003(state: dict) -> dict:
    """In lineTotal, amount is computed as line

    Preconditions:
      - inputs available: line, price, qty

    Postconditions:
      - amount = line.price * line.qty;
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: line, price, qty
    # REVIEW: postcondition not machine-renderable: amount = line.price * line.qty;
    # rule BR-003: In lineTotal, amount is computed as line.price * line.qty;.
    if _eq(s.get("line"), 1) and _eq(s.get("price"), 1) and _eq(s.get("qty"), 1):
        s["amount"] = "1.1 * 1.1;"
    return s


def N_BR_004(state: dict) -> dict:
    """In lineTotal, amount is computed as amount - Math

    Preconditions:
      - inputs available: amount, Math, floor

    Postconditions:
      - amount = amount - Math.floor(amount / 10)
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: amount, Math, floor
    # REVIEW: postcondition not machine-renderable: amount = amount - Math.floor(amount / 10)
    # rule BR-004: In lineTotal, amount is computed as amount - Math.floor(amount / 10).
    if _eq(s.get("amount"), 10) and _eq(s.get("Math"), 1) and _eq(s.get("floor"), 1):
        s["amount"] = "10 - 1.1(10 / 10)"
    return s


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


def N_BR_007(state: dict) -> dict:
    """In discountFor, if (promo === "SAVE10" && subtotal >= 5000) then d = Math

    Preconditions:
      - (promo === "SAVE10" && subtotal >= 5000)

    Postconditions:
      - d = Math.floor(subtotal * 10 / 100);
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: (promo === "SAVE10" && subtotal >= 5000)
    # REVIEW: postcondition not machine-renderable: d = Math.floor(subtotal * 10 / 100);
    # rule BR-007: In discountFor, if (promo === "SAVE10" && subtotal >= 5000) then d = Math.floor(
    if _eq(s.get("promo"), 10) and _eq(s.get("subtotal"), 5000) and _eq(s.get("SAVE10"), 1):
        s["d"] = "Math.floor(5000 * 10 / 100);"
    return s


def N_BR_008(state: dict) -> dict:
    """In discountFor, if (promo === "SAVE20" && subtotal >= 15000) then d = Math

    Preconditions:
      - (promo === "SAVE20" && subtotal >= 15000)

    Postconditions:
      - d = Math.floor(subtotal * 20 / 100);
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: (promo === "SAVE20" && subtotal >= 15000)
    # REVIEW: postcondition not machine-renderable: d = Math.floor(subtotal * 20 / 100);
    # rule BR-008: In discountFor, if (promo === "SAVE20" && subtotal >= 15000) then d = Math.floor
    if _eq(s.get("promo"), 20) and _eq(s.get("subtotal"), 15000) and _eq(s.get("SAVE20"), 1):
        s["d"] = "Math.floor(15000 * 20 / 100);"
    return s


def N_BR_009(state: dict) -> dict:
    """In discountFor, value is computed as Math

    Preconditions:
      - inputs available: Math, floor, subtotal

    Postconditions:
      - value = Math.floor(subtotal * 10 / 100)
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: Math, floor, subtotal
    # REVIEW: postcondition not machine-renderable: value = Math.floor(subtotal * 10 / 100)
    # rule BR-009: In discountFor, value is computed as Math.floor(subtotal * 10 / 100).
    if _eq(s.get("Math"), 100) and _eq(s.get("floor"), 1) and _eq(s.get("subtotal"), 1):
        s["value"] = "100.1(1 * 10 / 100)"
    return s


def N_BR_010(state: dict) -> dict:
    """In discountFor, value is computed as Math

    Preconditions:
      - inputs available: Math, floor, subtotal

    Postconditions:
      - value = Math.floor(subtotal * 20 / 100)
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: Math, floor, subtotal
    # REVIEW: postcondition not machine-renderable: value = Math.floor(subtotal * 20 / 100)
    # rule BR-010: In discountFor, value is computed as Math.floor(subtotal * 20 / 100).
    if _eq(s.get("Math"), 100) and _eq(s.get("floor"), 1) and _eq(s.get("subtotal"), 1):
        s["value"] = "100.1(1 * 20 / 100)"
    return s


def N_BR_011(state: dict) -> dict:
    """In run, if (total >= 20000) then status = "REVIEW";

    Preconditions:
      - (total >= 20000)

    Postconditions:
      - status = "REVIEW";
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: (total >= 20000)
    # REVIEW: postcondition not machine-renderable: status = "REVIEW";
    # rule BR-011: In run, if (total >= 20000) then status = "REVIEW";.
    if _eq(s.get("total"), 20000):
        s["status"] = "\"REVIEW\";"
    return s


def N_BR_012(state: dict) -> dict:
    """In run, if (inputs

    Preconditions:
      - (inputs.country !== "US" && inputs.country !== "CA" && subtotal >= 30000)

    Postconditions:
      - status = "HOLD";
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: (inputs.country !== "US" && inputs.country !== "CA" && subtotal >= 30000)
    # REVIEW: postcondition not machine-renderable: status = "HOLD";
    # rule BR-012: In run, if (inputs.country !== "US" && inputs.country !== "CA" && subtotal >= 30
    if _eq(s.get("inputs"), "CA") and _eq(s.get("subtotal"), 30000) and _eq(s.get("country"), 1) and _eq(s.get("US"), 1) and _eq(s.get("CA"), 1):
        s["status"] = "\"HOLD\";"
    return s


def N_BR_013(state: dict) -> dict:
    """In run, lines is computed as inputs

    Preconditions:
      - inputs available: inputs, lines

    Postconditions:
      - lines = inputs.lines;
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: inputs, lines
    # REVIEW: postcondition not machine-renderable: lines = inputs.lines;
    # rule BR-013: In run, lines is computed as inputs.lines;.
    if _eq(s.get("inputs"), 1) and _eq(s.get("lines"), 1):
        s["lines"] = "1.1;"
    return s


def N_BR_014(state: dict) -> dict:
    """In run, subtotal is computed as 0;

    Preconditions:
      - inputs available: constant

    Postconditions:
      - subtotal = 0;
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: constant
    # REVIEW: postcondition not machine-renderable: subtotal = 0;
    # rule BR-014: In run, subtotal is computed as 0;.
    if _eq(s.get("input"), 0):
        s["subtotal"] = "0;"
    return s


def N_BR_015(state: dict) -> dict:
    """In run, subtotal is computed as subtotal + lineTotal(lines[i])

    Preconditions:
      - inputs available: subtotal, lineTotal, lines

    Postconditions:
      - subtotal = subtotal + lineTotal(lines[i])
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: subtotal, lineTotal, lines
    # REVIEW: postcondition not machine-renderable: subtotal = subtotal + lineTotal(lines[i])
    # rule BR-015: In run, subtotal is computed as subtotal + lineTotal(lines[i]).
    if _eq(s.get("subtotal"), 1) and _eq(s.get("lineTotal"), 1) and _eq(s.get("lines"), 1):
        s["subtotal"] = "1 + 1(1[i])"
    return s


def N_BR_016(state: dict) -> dict:
    """In run, discount is computed as discountFor(subtotal, inputs

    Preconditions:
      - inputs available: discountFor, subtotal, inputs, promo

    Postconditions:
      - discount = discountFor(subtotal, inputs.promo);
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: discountFor, subtotal, inputs, promo
    # REVIEW: postcondition not machine-renderable: discount = discountFor(subtotal, inputs.promo);
    # rule BR-016: In run, discount is computed as discountFor(subtotal, inputs.promo);.
    if _eq(s.get("discountFor"), 1) and _eq(s.get("subtotal"), 1) and _eq(s.get("inputs"), 1) and _eq(s.get("promo"), 1):
        s["discount"] = "1(1, 1.1);"
    return s


def N_BR_017(state: dict) -> dict:
    """In run, shipping is computed as shippingFor(subtotal, inputs

    Preconditions:
      - inputs available: shippingFor, subtotal, inputs, country

    Postconditions:
      - shipping = shippingFor(subtotal, inputs.country);
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: shippingFor, subtotal, inputs, country
    # REVIEW: postcondition not machine-renderable: shipping = shippingFor(subtotal, inputs.country);
    # rule BR-017: In run, shipping is computed as shippingFor(subtotal, inputs.country);.
    if _eq(s.get("shippingFor"), 1) and _eq(s.get("subtotal"), 1) and _eq(s.get("inputs"), 1) and _eq(s.get("country"), 1):
        s["shipping"] = "1(1, 1.1);"
    return s


def N_BR_018(state: dict) -> dict:
    """In run, total is computed as subtotal - discount + shipping;

    Preconditions:
      - inputs available: subtotal, discount, shipping

    Postconditions:
      - total = subtotal - discount + shipping;
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: subtotal, discount, shipping
    # REVIEW: postcondition not machine-renderable: total = subtotal - discount + shipping;
    # rule BR-018: In run, total is computed as subtotal - discount + shipping;.
    if _eq(s.get("subtotal"), 1) and _eq(s.get("discount"), 1) and _eq(s.get("shipping"), 1):
        s["total"] = "1 - 1 + 1;"
    return s


def N_BR_019(state: dict) -> dict:
    """In run, status is computed as "OPEN";

    Preconditions:
      - inputs available: OPEN

    Postconditions:
      - status = "OPEN";
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: OPEN
    # REVIEW: postcondition not machine-renderable: status = "OPEN";
    # rule BR-019: In run, status is computed as "OPEN";.
    if _eq(s.get("OPEN"), "OPEN"):
        s["status"] = "\"OPEN\";"
    return s


def N_BR_020(state: dict) -> dict:
    """In run, status is computed as "REVIEW"

    Preconditions:
      - inputs available: REVIEW

    Postconditions:
      - status = "REVIEW"
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: REVIEW
    s["status"] = 'REVIEW'
    # rule BR-020: In run, status is computed as "REVIEW".
    if _eq(s.get("REVIEW"), "REVIEW"):
        s["status"] = "\"REVIEW\""
    return s


def N_BR_021(state: dict) -> dict:
    """In run, status is computed as "HOLD"

    Preconditions:
      - inputs available: HOLD

    Postconditions:
      - status = "HOLD"
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: HOLD
    s["status"] = 'HOLD'
    # rule BR-021: In run, status is computed as "HOLD".
    if _eq(s.get("HOLD"), "HOLD"):
        s["status"] = "\"HOLD\""
    return s


def N_GAP_001(state: dict) -> dict:
    """uncovered code path: meta.json
    (confidence_state=gap)
    """
    s = dict(state)
    # TODO: no machine-renderable effect for node N-GAP-001
    return s


def N_GAP_002(state: dict) -> dict:
    """uncovered code path: package.json
    (confidence_state=gap)
    """
    s = dict(state)
    # TODO: no machine-renderable effect for node N-GAP-002
    return s


def N_GAP_003(state: dict) -> dict:
    """uncovered code path: work_manifest.json
    (confidence_state=gap)
    """
    s = dict(state)
    # TODO: no machine-renderable effect for node N-GAP-003
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
    "N-BR-018": N_BR_018,
    "N-BR-019": N_BR_019,
    "N-BR-020": N_BR_020,
    "N-BR-021": N_BR_021,
    "N-GAP-001": N_GAP_001,
    "N-GAP-002": N_GAP_002,
    "N-GAP-003": N_GAP_003,
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
    try:
        s = N_BR_018(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_019(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_020(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_BR_021(s)
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
    try:
        s = N_GAP_003(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    return s
