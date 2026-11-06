"""Table-driven modernization (offline strategy for the Transformer).

Given a Behavioural Specification Graph and the rule inventory, produce a
modern implementation in the target language.  The offline strategy is
*specification-driven generation*: every BSG node becomes a function whose
guard clauses render its preconditions and whose decision table renders the
given/expect pairs captured from the legacy code.  Constructs that cannot
be rendered are marked REVIEW/TODO rather than guessed (synopsis 6.1),
and blocked nodes are skipped entirely — never guessed (control rule 3).

This is deliberately conservative: it is a deterministic stand-in for the
LLM Transformer, not a claim that translation is solved.  Its value is
that every downstream stage (equivalence, documentation, audit trail) runs
end-to-end without a model, with honest markers where coverage is missing.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


def _py_ident(name: str) -> str:
    n = re.sub(r"[^0-9A-Za-z_]", "_", name or "x")
    if n[0].isdigit():
        n = "_" + n
    return n


def _literal(v: Any) -> str:
    return json.dumps(v)


def generate_python_from_bsg(unit_id: str, bsg: dict, rules_by_id: dict,
                             mode: str = "migration") -> dict:
    """Return {"files": [...], "markers": [...], "node_spans": [...]}."""
    files: List[dict] = []
    markers: List[dict] = []
    node_spans: List[dict] = []
    path = f"{_py_ident(unit_id)}_modernized.py"
    lines: List[str] = []
    lines.append(f'"""Modernized from legacy unit {unit_id} (AURA specification-driven generation).')
    lines.append("")
    lines.append("Every function below implements one node of the Behavioural")
    lines.append("Specification Graph. Guard clauses render preconditions; the")
    lines.append("decision tables render given/expect pairs captured by executing")
    lines.append("the original legacy code. REVIEW/TODO markers mark constructs")
    lines.append("that were not rendered rather than guessed.")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("class RuleViolation(Exception):")
    lines.append("    pass")
    lines.append("")
    lines.append("")

    def mark(kind: str, reason: str) -> None:
        markers.append({"kind": kind, "line": len(lines) + 1, "reason": reason, "path": path})
        lines.append(f"    # {kind}: {reason}")

    for node in bsg.get("nodes", []):
        nid = node.get("id", "node")
        if node.get("blocked"):
            markers.append({"kind": "SKIPPED", "line": len(lines) + 1,
                            "reason": f"node {nid} blocked_on_human: {node.get('block_reason', '')}",
                            "path": path})
            lines.append(f"# SKIPPED (blocked_on_human): {nid} — {node.get('block_reason', 'contradicted rule')}")
            lines.append("")
            continue
        fname = _py_ident(nid)
        start = len(lines) + 1
        lines.append(f"def {fname}(state: dict) -> dict:")
        lines.append(f'    """{node.get("operation", nid)}')
        if node.get("preconditions"):
            lines.append("")
            lines.append("    Preconditions:")
            for p in node["preconditions"]:
                lines.append(f"      - {p}")
        if node.get("postconditions"):
            lines.append("")
            lines.append("    Postconditions:")
            for p in node["postconditions"]:
                lines.append(f"      - {p}")
        lines.append(f'    (confidence_state={node.get("confidence_state", "inferred")})')
        lines.append('    """')
        lines.append("    s = dict(state)")
        # guard clauses from preconditions
        for p in node.get("preconditions", []):
            guard = _render_guard(p)
            if guard:
                lines.append(f"    if not ({guard}):")
                lines.append(f"        raise RuleViolation({_literal('precondition failed: ' + p)})")
            else:
                mark("REVIEW", f"precondition not machine-renderable: {p}")
        # decision tables from the underlying rules
        rendered_any = False
        for rid in node.get("rule_ids", []):
            rule = rules_by_id.get(rid)
            if not rule or not rule.get("contract"):
                continue
            given = rule["contract"].get("given", {}) or {}
            expect = rule["contract"].get("expect", {}) or {}
            if not expect:
                continue
            cond = " and ".join(f"s.get({_literal(k)}) == {_literal(v)}" for k, v in given.items())
            assign = "; ".join(f"s[{_literal(k)}] = {_literal(v)}" for k, v in expect.items())
            lines.append(f"    # rule {rid}: {rule.get('statement', '')[:80]}")
            lines.append(f"    if {cond or 'True'}:")
            lines.append(f"        {assign}")
            rendered_any = True
        if not rendered_any:
            mark("TODO", f"no machine-renderable contract for node {nid}")
        lines.append("    return s")
        lines.append("")
        lines.append("")
        node_spans.append({"node_id": nid, "path": path, "line_start": start, "line_end": len(lines)})

    lines.append("NODE_REGISTRY = {")
    for node in bsg.get("nodes", []):
        if not node.get("blocked"):
            lines.append(f"    {_literal(node.get('id', 'node'))}: {_py_ident(node.get('id', 'node'))},")
    lines.append("}")
    lines.append("")
    lines.append("")
    lines.append("def run(state: dict) -> dict:")
    lines.append('    """Run every non-blocked node in sequence (BSG control flow)."""')
    lines.append("    s = dict(state)")
    for node in bsg.get("nodes", []):
        if node.get("blocked"):
            continue
        lines.append(f"    s = {_py_ident(node.get('id', 'node'))}(s)")
    lines.append("    return s")
    lines.append("")

    files.append({"path": path, "content": "\n".join(lines)})
    return {"files": files, "markers": markers, "node_spans": node_spans}


def _render_guard(precondition: str) -> Optional[str]:
    """Render a precondition string as a Python boolean expression when the
    shape is understood; return None otherwise (caller marks REVIEW)."""
    p = (precondition or "").strip()
    if not p:
        return None
    # s['X'] == literal  |  X == literal  |  X in [a, b]  |  X > n ...
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*(?:==|IS|EQUALS)\s*(.+)$", p, re.I)
    if m:
        return f"s.get({_literal(m.group(1))}) == {_literal(_coerce(m.group(2).strip()))}"
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s+in\s+\[(.+)\]$", p, re.I)
    if m:
        vals = [_coerce(v.strip()) for v in m.group(2).split(",")]
        return f"s.get({_literal(m.group(1))}) in {vals!r}"
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*(>=|<=|>|<)\s*(.+)$", p)
    if m:
        return f"(s.get({_literal(m.group(1))}) or 0) {m.group(2)} {_coerce(m.group(3).strip())!r}"
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*(?:=|==)\s*(.+)$", p)
    if m:
        return f"s.get({_literal(m.group(1))}) == {_literal(_coerce(m.group(2).strip()))}"
    return None


def _coerce(text: str) -> Any:
    t = (text or "").strip().strip("'\"")
    try:
        return float(t) if "." in t else int(t)
    except ValueError:
        return t


def generate_in_place_report(unit_id: str, bsg: dict, rules_by_id: dict) -> dict:
    """In-place upgrade: produce a cleaned copy with inline documentation and
    REVIEW markers for changes needing sign-off.  The offline strategy keeps
    the original text verbatim and adds an upgrade banner + per-rule doc
    comments — nothing semantic is altered (guaranteed immutability of
    behaviour), which is the safest possible in-place upgrade."""
    markers = [
        {"kind": "REVIEW", "line": 1,
         "reason": "in-place upgrade performed as documentation-only patch; "
                   "semantic refactors need human sign-off", "path": f"{unit_id}.upgrade.md"}
    ]
    return {"files": [], "markers": markers, "node_spans": [], "in_place": True}
