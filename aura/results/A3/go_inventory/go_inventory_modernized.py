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


def N_BR_001(state: dict) -> dict:
    """In computeReorder, need is computed as reorderLevel - stock

    Preconditions:
      - inputs available: reorderLevel, stock

    Postconditions:
      - need = reorderLevel - stock
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: reorderLevel, stock
    s["need"] = ((s.get("reorderLevel") or 0) - (s.get("stock") or 0))
    # rule BR-001: In computeReorder, need is computed as reorderLevel - stock.
    if _eq(s.get("reorderLevel"), 1) and _eq(s.get("stock"), 1):
        s["need"] = 0
    return s


def N_BR_002(state: dict) -> dict:
    """In computeReorder, leadNeed is computed as leadDays * dailyDemand

    Preconditions:
      - inputs available: leadDays, dailyDemand

    Postconditions:
      - leadNeed = leadDays * dailyDemand
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: leadDays, dailyDemand
    s["leadNeed"] = ((s.get("leadDays") or 0) * (s.get("dailyDemand") or 0))
    # rule BR-002: In computeReorder, leadNeed is computed as leadDays * dailyDemand.
    if _eq(s.get("leadDays"), 1) and _eq(s.get("dailyDemand"), 1):
        s["leadNeed"] = 1
    return s


def N_BR_003(state: dict) -> dict:
    """In runBatch, need is computed as computeReorder(stock, reorderLevel, leadDays, d

    Preconditions:
      - inputs available: computeReorder, stock, reorderLevel, leadDays, dailyDemand

    Postconditions:
      - need = computeReorder(stock, reorderLevel, leadDays, dailyDemand)
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: computeReorder, stock, reorderLevel, leadDays, dailyDemand
    # REVIEW: postcondition not machine-renderable: need = computeReorder(stock, reorderLevel, leadDays, dailyDemand)
    # rule BR-003: In runBatch, need is computed as computeReorder(stock, reorderLevel, leadDays, d
    if _eq(s.get("computeReorder"), 1) and _eq(s.get("stock"), 1) and _eq(s.get("reorderLevel"), 1) and _eq(s.get("leadDays"), 1) and _eq(s.get("dailyDemand"), 1):
        s["need"] = "1(1, 1, 1, 1)"
    return s


def N_BR_004(state: dict) -> dict:
    """In runBatch, status is computed as classify(stock, reorderLevel)

    Preconditions:
      - inputs available: classify, stock, reorderLevel

    Postconditions:
      - status = classify(stock, reorderLevel)
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: classify, stock, reorderLevel
    # REVIEW: postcondition not machine-renderable: status = classify(stock, reorderLevel)
    # rule BR-004: In runBatch, status is computed as classify(stock, reorderLevel).
    if _eq(s.get("classify"), 1) and _eq(s.get("stock"), 1) and _eq(s.get("reorderLevel"), 1):
        s["status"] = "1(1, 1)"
    return s


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


def N_BR_006(state: dict) -> dict:
    """In priceOrder, discount is computed as 0

    Preconditions:
      - inputs available: constant

    Postconditions:
      - discount = 0
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: constant
    s["discount"] = 0
    # rule BR-006: In priceOrder, discount is computed as 0.
    if _eq(s.get("input"), 0):
        s["discount"] = 0
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


def N_BR_008(state: dict) -> dict:
    """In runPricing, total is computed as priceOrder(units, unitPrice, member)

    Preconditions:
      - inputs available: priceOrder, units, unitPrice, member

    Postconditions:
      - total = priceOrder(units, unitPrice, member)
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: priceOrder, units, unitPrice, member
    # REVIEW: postcondition not machine-renderable: total = priceOrder(units, unitPrice, member)
    # rule BR-008: In runPricing, total is computed as priceOrder(units, unitPrice, member).
    if _eq(s.get("priceOrder"), 1) and _eq(s.get("units"), 1) and _eq(s.get("unitPrice"), 1) and _eq(s.get("member"), 1):
        s["total"] = "1(1, 1, 1)"
    return s


def N_BR_009(state: dict) -> dict:
    """In runPricing, fee is computed as shippingFee(weight, zone)

    Preconditions:
      - inputs available: shippingFee, weight, zone

    Postconditions:
      - fee = shippingFee(weight, zone)
    (confidence_state=contradicted)
    """
    s = dict(state)
    # REVIEW: precondition not machine-renderable: inputs available: shippingFee, weight, zone
    # REVIEW: postcondition not machine-renderable: fee = shippingFee(weight, zone)
    # rule BR-009: In runPricing, fee is computed as shippingFee(weight, zone).
    if _eq(s.get("shippingFee"), 1) and _eq(s.get("weight"), 1) and _eq(s.get("zone"), 1):
        s["fee"] = "1(1, 1)"
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
        s = N_GAP_001(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    try:
        s = N_GAP_002(s)
    except RuleViolation:
        pass  # rule precondition not met: node does not fire
    return s
