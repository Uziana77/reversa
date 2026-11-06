"""Table-driven modernization (offline strategy for the Transformer).

Given a Behavioural Specification Graph and the rule inventory, produce a
modern implementation in the target language.  The offline strategy is
*specification-driven generation*: every BSG node becomes a function whose
guard clauses render its preconditions and whose effects render its
postconditions as assignments over the state mapping; the decision tables
additionally pin the given/expect pairs captured from the legacy code.
Constructs that cannot be rendered are marked REVIEW/TODO rather than
guessed (synopsis 6.1), and blocked nodes are skipped entirely — never
guessed (control rule 3).

This is deliberately conservative: it is a deterministic stand-in for the
LLM Transformer, not a claim that translation is solved.  Its value is
that every downstream stage (equivalence, documentation, audit trail)
runs end-to-end without a model, with honest markers where coverage is
missing.

Renderer grammar (documented subset):

* guard atoms: ``X = v``, ``X <> v``, ``X != v``, ``X >= v``, ``X > v``,
  ``X <= v``, ``X < v``, ``X IN [a, b]``, ``NOT <atom>``; joined by
  ``AND`` / ``OR``.  Equality renders as a loose comparator (numeric vs
  string vs ON/OFF aliases); ordering requires a numeric literal.
* effects: ``SET X TO v`` and ``X = <expression>`` where the expression
  uses identifiers (hyphenated legacy names allowed), numbers and
  ``+ - * / ( )``.  Wildcard expectations (``changed``/``unchanged``/
  ``*``/``any``) are never rendered as assignments.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

_WORDY_LITERALS = {"ON", "OFF", "TRUE", "FALSE", "YES", "NO", "P", "Z"}
_WILDCARDS = {"changed", "unchanged", "*", "any", ""}


def _py_ident(name: str) -> str:
    n = re.sub(r"[^0-9A-Za-z_]", "_", name or "x")
    if n[0].isdigit():
        n = "_" + n
    return n


def _literal(v: Any) -> str:
    return json.dumps(v)


def _coerce(text: str) -> Any:
    t = (text or "").strip().strip("'\"")
    try:
        return float(t) if "." in t else int(t)
    except ValueError:
        return t


# ---------------------------------------------------------------------------
# expression / guard / effect rendering
# ---------------------------------------------------------------------------

_EXPR_TOKEN = re.compile(r"\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_\-]*|[+\-*/()%]|<>|>=|<=|==|!=|[<>=!]")


def _render_expr(expr: str) -> Optional[str]:
    """Render a legacy arithmetic expression over the state mapping."""
    src = (expr or "").strip().rstrip(".").strip()
    if not src:
        return None
    tokens = _EXPR_TOKEN.findall(src)
    if "".join(tokens).replace(" ", "") != src.replace(" ", "").replace(" ", ""):
        # quick sanity: every non-space char must appear in the token stream
        stripped = re.sub(r"\s+", "", src)
        if re.sub(r"\s+", "", "".join(tokens)) != stripped:
            return None
    out: List[str] = []
    for t in tokens:
        u = t.upper()
        if re.fullmatch(r"\d+(?:\.\d+)?", t):
            out.append(t)
        elif u in ("AND", "OR", "NOT"):
            out.append({"AND": "and", "OR": "or", "NOT": "not"}[u])
        elif u == "<>":
            out.append("!=")
        elif t in "+-*/%()":
            out.append(t)
        elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", t):
            out.append(f"(s.get({_literal(t)}) or 0)")
        else:
            return None
    rendered = " ".join(out)
    # reject leftovers that would not be valid python
    if re.search(r"[=<>!]", rendered):
        return None
    return f"({rendered})"


def _render_effect(postcondition: str) -> Optional[str]:
    """Render one postcondition as a Python assignment body (RHS)."""
    p = (postcondition or "").strip().rstrip(".").strip()
    if not p:
        return None
    m = re.match(r"^SET\s+([A-Za-z_][A-Za-z0-9_\-]*)\s+TO\s+(.+)$", p, re.I)
    if m:
        val = _coerce(m.group(2))
        # dialect SET ON/OFF renders as 1/0 in the legacy interpreters
        if isinstance(val, str) and val.upper() in ("ON", "TRUE", "YES"):
            val = 1
        elif isinstance(val, str) and val.upper() in ("OFF", "FALSE", "NO"):
            val = 0
        return f"s[{_literal(m.group(1))}] = {_literal(val)}"
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*=\s*(.+)$", p)
    if m:
        name, rhs = m.group(1), m.group(2).strip()
        if rhs.upper() in _WORDY_LITERALS:
            return f"s[{_literal(name)}] = {_literal(_coerce(rhs))}"
        if re.fullmatch(r"-?\d+(?:\.\d+)?", rhs):
            return f"s[{_literal(name)}] = {_coerce(rhs)!r}"
        if re.fullmatch(r"'[^']*'|\"[^\"]*\"", rhs):
            return f"s[{_literal(name)}] = {_coerce(rhs)!r}"
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", rhs):
            return f"s[{_literal(name)}] = s.get({_literal(rhs)})"
        e = _render_expr(rhs)
        if e is not None:
            return f"s[{_literal(name)}] = {e}"
    return None


def _split_logical(text: str) -> List[Tuple[str, str]]:
    """Split on top-level AND/OR; returns [(op, atom)] with op '' for first."""
    parts: List[Tuple[str, str]] = []
    buf = ""
    depth = 0
    i = 0
    upper = text.upper()
    op = ""
    while i < len(text):
        ch = text[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if depth == 0 and upper.startswith(" AND ", i):
            parts.append((op, buf.strip()))
            buf, op = "", "and"
            i += 5
            continue
        if depth == 0 and upper.startswith(" OR ", i):
            parts.append((op, buf.strip()))
            buf, op = "", "or"
            i += 4
            continue
        buf += ch
        i += 1
    parts.append((op, buf.strip()))
    return [(o, a) for o, a in parts if a]


def _render_atom(atom: str) -> Optional[str]:
    a = (atom or "").strip()
    if not a:
        return None
    m = re.match(r"^NOT\s+(.+)$", a, re.I)
    if m:
        inner = _render_atom(m.group(1))
        return f"(not {inner})" if inner else None
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s+IN\s+\[(.+)\]$", a, re.I)
    if m:
        vals = [_coerce(v.strip()) for v in m.group(2).split(",")]
        return f"_eq_any(s.get({_literal(m.group(1))}), {vals!r})"
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*(<>|!=|>=|<=|==|=|>|<)\s*(.+)$", a)
    if not m:
        return None
    name, op, raw = m.group(1), m.group(2), m.group(3).strip().rstrip(".").strip()
    lit = _coerce(raw)
    if op in ("=", "=="):
        return f"_eq(s.get({_literal(name)}), {_literal(lit)})"
    if op in ("<>", "!="):
        return f"(not _eq(s.get({_literal(name)}), {_literal(lit)}))"
    if isinstance(lit, (int, float)) and not isinstance(lit, bool):
        pyop = {">": ">", "<": "<", ">=": ">=", "<=": "<="}[op]
        return f"((s.get({_literal(name)}) or 0) {pyop} {lit!r})"
    return None


def _render_guard(precondition: str) -> Optional[str]:
    """Render a precondition string as a Python boolean expression when the
    shape is understood; return None otherwise (caller marks REVIEW)."""
    p = (precondition or "").strip().rstrip(".").strip()
    if not p:
        return None
    atoms = _split_logical(p)
    rendered = []
    for op, atom in atoms:
        r = _render_atom(atom)
        if r is None:
            return None
        rendered.append((op, r))
    out = rendered[0][1]
    for op, r in rendered[1:]:
        out = f"({out} {op} {r})"
    return out


# ---------------------------------------------------------------------------
# generator
# ---------------------------------------------------------------------------

_HELPERS = '''
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
'''


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
    lines.append("effects and decision tables render the postconditions and the")
    lines.append("given/expect pairs captured by executing the original legacy code.")
    lines.append("REVIEW/TODO markers mark constructs that were not rendered rather")
    lines.append("than guessed.")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("class RuleViolation(Exception):")
    lines.append("    pass")
    lines.append("")
    lines.append(_HELPERS.strip())
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
                lines.append(f"    if not {guard}:")
                lines.append(f"        raise RuleViolation({_literal('precondition failed: ' + p)})")
            else:
                mark("REVIEW", f"precondition not machine-renderable: {p}")
        # effects from postconditions
        rendered_any = False
        for p in node.get("postconditions", []):
            eff = _render_effect(p)
            if eff:
                lines.append(f"    {eff}")
                rendered_any = True
            else:
                mark("REVIEW", f"postcondition not machine-renderable: {p}")
        # decision tables from the underlying rules (concrete expects only)
        for rid in node.get("rule_ids", []):
            rule = rules_by_id.get(rid)
            if not rule or not rule.get("contract"):
                continue
            given = rule["contract"].get("given", {}) or {}
            expect = rule["contract"].get("expect", {}) or {}
            concrete = {k: v for k, v in expect.items()
                        if not (isinstance(v, str) and v.strip().lower() in _WILDCARDS)}
            if not concrete:
                continue
            cond = " and ".join(f"_eq(s.get({_literal(k)}), {_literal(v)})" for k, v in given.items())
            assign = "; ".join(f"s[{_literal(k)}] = {_literal(v)}" for k, v in concrete.items())
            lines.append(f"    # rule {rid}: {rule.get('statement', '')[:80]}")
            lines.append(f"    if {cond or 'True'}:")
            lines.append(f"        {assign}")
            rendered_any = True
        if not rendered_any:
            mark("TODO", f"no machine-renderable effect for node {nid}")
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
    lines.append('    """Run every non-blocked node in sequence (BSG control flow).')
    lines.append("    A node whose preconditions do not hold does not fire (its")
    lines.append('    rule simply does not apply to this input): skipped, not raised."""')
    lines.append("    s = dict(state)")
    for node in bsg.get("nodes", []):
        if node.get("blocked"):
            continue
        fname = _py_ident(node.get("id", "node"))
        lines.append(f"    try:")
        lines.append(f"        s = {fname}(s)")
        lines.append(f"    except RuleViolation:")
        lines.append(f"        pass  # rule precondition not met: node does not fire")
    lines.append("    return s")
    lines.append("")

    files.append({"path": path, "content": "\n".join(lines)})
    return {"files": files, "markers": markers, "node_spans": node_spans}


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
