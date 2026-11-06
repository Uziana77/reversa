"""ASTAnalyzer skill core: structural extraction with Tree-sitter where the
language is known and the inferred grammar / line heuristics otherwise
(synopsis 6.1).

Produces the *unit digest* consumed by rule synthesis, call-graph
construction and CRUD extraction::

    {"file", "symbol", "kind", "line_start", "line_end", "signature",
     "conditions": [{"text", "line", "effect"}],
     "assignments": [{"text", "line"}],
     "calls": ["NAME", ...],
     "crud": [{"op", "store", "line"}]}

``parse_method`` is recorded per file (``tree_sitter``, ``cobolite``,
``dialect``, ``heuristic``) so every ASTMap carries its own provenance.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

TS_AVAILABLE = False
try:  # Tree-sitter grammars for known languages
    from tree_sitter_languages import get_parser  # type: ignore

    TS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    get_parser = None  # type: ignore

_TS_LANGS = {"java": "java", "javascript": "javascript", "javascript-react": "javascript",
             "typescript": "javascript", "typescript-react": "javascript", "go": "go",
             "python": "python"}

CRUD_NAME_HINTS = {
    "create": ("insert", "create", "append", "push", "add", "new", "write"),
    "read": ("read", "select", "fetch", "get", "find", "load", "lookup", "query", "open"),
    "update": ("update", "set", "put", "save", "store", "compute", "move", "edit", "assign"),
    "delete": ("delete", "remove", "drop", "clear", "erase", "purge"),
}


# ---------------------------------------------------------------------------
# File-level entry point
# ---------------------------------------------------------------------------

def analyze_file(path: str, text: str, language: Optional[str]) -> dict:
    lang = (language or "").lower()
    if lang in _TS_LANGS and TS_AVAILABLE:
        try:
            return _analyze_tree_sitter(path, text, _TS_LANGS[lang])
        except Exception:
            pass
    if lang.startswith("cobol") or "IDENTIFICATION DIVISION" in text[:400].upper():
        try:
            return _analyze_cobol(path, text)
        except Exception:
            pass
    if lang in ("interlock", "reportscript", "ilg", "rpt"):
        try:
            return _analyze_dialect(path, text, lang)
        except Exception:
            pass
    return _analyze_heuristic(path, text, lang or "unknown")


# ---------------------------------------------------------------------------
# Tree-sitter front-end
# ---------------------------------------------------------------------------

def _analyze_tree_sitter(path: str, text: str, ts_lang: str) -> dict:
    parser = get_parser(ts_lang)
    src = text.encode("utf-8")
    tree = parser.parse(src)
    units: List[dict] = []

    func_types = {
        "java": {"method_declaration", "constructor_declaration"},
        "javascript": {"function_declaration", "arrow_function", "method_definition",
                       "generator_function_declaration"},
        "go": {"function_declaration", "method_declaration"},
        "python": {"function_definition"},
    }[ts_lang]
    class_types = {
        "java": {"class_declaration"},
        "javascript": {"class_declaration"},
        "go": {"type_declaration"},
        "python": {"class_definition"},
    }[ts_lang]

    def node_text(n) -> str:
        return src[n.start_byte : n.end_byte].decode("utf-8", "replace")

    def walk(n, class_name: str = "") -> None:
        if n.type in class_types:
            name = _child_text(n, src, ("identifier", "type_identifier", "type_spec"))
            cname = f"{class_name}.{name}" if class_name else name
            for ch in n.named_children:
                walk(ch, cname)
            return
        if n.type in func_types:
            name = _child_text(n, src, ("identifier", "field_identifier", "type_identifier"))
            if not name:
                name = f"anon@{n.start_point[0] + 1}"
            symbol = f"{class_name}.{name}" if class_name else name
            unit = {
                "file": path,
                "symbol": symbol,
                "kind": "method" if class_name else "function",
                "line_start": n.start_point[0] + 1,
                "line_end": n.end_point[0] + 1,
                "signature": " ".join(node_text(n).splitlines()[:1])[:160],
                "conditions": [],
                "assignments": [],
                "calls": [],
                "crud": [],
            }
            _collect_exprs(n, src, unit)
            units.append(unit)
            return
        for ch in n.named_children:
            walk(ch, class_name)

    walk(tree.root_node)
    if not units:
        return _analyze_heuristic(path, text, ts_lang)
    return {"file": path, "units": units, "parse_method": "tree_sitter", "ok": True}


def _child_text(node, src, types: Tuple[str, ...]) -> str:
    for ch in node.named_children:
        if ch.type in types:
            return src[ch.start_byte : ch.end_byte].decode("utf-8", "replace")
    return ""


def _collect_exprs(node, src, unit: dict) -> None:
    stack = [node]
    while stack:
        n = stack.pop()
        t = n.type
        ntext = src[n.start_byte : n.end_byte].decode("utf-8", "replace")
        if t in ("if_statement", "while_statement", "conditional_expression",
                 "for_statement", "switch_expression", "guard_clause"):
            cond = ""
            for ch in n.children:
                if ch.type in ("parenthesized_expression", "condition_clause", "expression"):
                    cond = src[ch.start_byte : ch.end_byte].decode("utf-8", "replace")
                    break
            effect = _first_stmt_text(n, src)
            if cond:
                unit["conditions"].append(
                    {"text": " ".join(cond.split())[:220], "line": n.start_point[0] + 1,
                     "effect": " ".join(effect.split())[:220]}
                )
        elif t in ("assignment_expression", "short_var_declaration", "variable_declaration",
                   "assignment", "augmented_assignment"):
            unit["assignments"].append(
                {"text": " ".join(ntext.split())[:200], "line": n.start_point[0] + 1}
            )
        elif t in ("method_invocation", "call_expression", "function_call_expression"):
            callee = _callee_name(n, src)
            if callee:
                unit["calls"].append(callee)
                crud = _crud_for(callee)
                if crud:
                    unit["crud"].append({"op": crud, "store": callee, "line": n.start_point[0] + 1})
        stack.extend(reversed(n.named_children))


def _callee_name(node, src) -> str:
    for ch in node.children:
        if ch.type in ("identifier", "field_identifier", "type_identifier", "selector_expression",
                       "field_access", "method_reference"):
            txt = src[ch.start_byte : ch.end_byte].decode("utf-8", "replace")
            return txt.split(".")[-1].split("(")[0].strip()
        if ch.type in ("member_expression", "scoped_identifier"):
            txt = src[ch.start_byte : ch.end_byte].decode("utf-8", "replace")
            return txt.split(".")[-1].split("(")[0].strip()
    return ""


def _first_stmt_text(node, src) -> str:
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type in ("expression_statement", "block", "return_statement", "assignment",
                      "assignment_expression", "raise_statement", "throw_statement",
                      "call_expression", "method_invocation", "short_var_declaration"):
            txt = src[n.start_byte : n.end_byte].decode("utf-8", "replace").strip()
            if txt and n.type != "block":
                return txt
        for ch in reversed(n.named_children):
            stack.append(ch)
    return ""


def _crud_for(name: str) -> Optional[str]:
    low = name.lower()
    for op, hints in CRUD_NAME_HINTS.items():
        if any(h in low for h in hints):
            return op
    return None


# ---------------------------------------------------------------------------
# COBOL front-end (bundled parser)
# ---------------------------------------------------------------------------

def _analyze_cobol(path: str, text: str) -> dict:
    from ..adapters.cobolite import parse_cobol

    prog = parse_cobol(text)
    units: List[dict] = []
    for name, para in prog.paragraphs.items():
        unit = {
            "file": path,
            "symbol": name.title().replace("-", " "),
            "kind": "paragraph",
            "line_start": para.line,
            "line_end": max([para.line] + [s.line for s in para.body]),
            "signature": f"paragraph {name}",
            "conditions": [],
            "assignments": [],
            "calls": [],
            "crud": [],
        }
        for st in para.body:
            _cobol_stmt(st, unit)
        units.append(unit)
    return {"file": path, "units": units, "parse_method": "cobolite", "ok": True}


def _cobol_stmt(st, unit: dict) -> None:
    kind = st.kind
    if kind == "IF":
        unit["conditions"].append(
            {"text": _cond_text(st.a), "line": st.line,
             "effect": _stmt_text(st.body[0]) if st.body else ""}
        )
        for s in st.body + st.else_body:
            _cobol_stmt(s, unit)
    elif kind == "PERFORM_VARYING":
        unit["conditions"].append(
            {"text": f"perform varying {_cond_text(st.d)}", "line": st.line,
             "effect": _stmt_text(st.body[0]) if st.body else ""}
        )
        for s in st.body:
            _cobol_stmt(s, unit)
    elif kind in ("MOVE", "COMPUTE"):
        unit["assignments"].append({"text": _stmt_text(st), "line": st.line})
        unit["crud"].append({"op": "update", "store": "working-storage", "line": st.line})
    elif kind in ("ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
        unit["assignments"].append({"text": _stmt_text(st), "line": st.line})
        unit["crud"].append({"op": "update", "store": "working-storage", "line": st.line})
    elif kind == "PERFORM":
        target = st.a if isinstance(st.a, str) else (st.a[1] if isinstance(st.a, tuple) else "")
        unit["calls"].append(target.title().replace("-", " "))
    elif kind == "EXEC":
        unit["crud"].append({"op": "read", "store": "external:" + (st.a or "")[:40], "line": st.line})
    elif kind == "ACCEPT":
        unit["crud"].append({"op": "read", "store": "input", "line": st.line})
    elif kind == "DISPLAY":
        unit["crud"].append({"op": "read", "store": "output", "line": st.line})


def _cond_text(node) -> str:
    if isinstance(node, tuple):
        if node[0] == "CMP":
            return f"{_val(node[2])} {node[1]} {_val(node[3])}"
        if node[0] == "LOGIC":
            return f"({_cond_text(node[2])} {node[1]} {_cond_text(node[3])})"
        if node[0] == "NOT":
            return f"NOT {_cond_text(node[1])}"
        if node[0] == "TRUTHY":
            return str(_val(node[1]))
        return str(node)
    return str(node)


def _val(node) -> str:
    if isinstance(node, tuple) and node and node[0] == "REF":
        return str(node[1])
    return str(node)


def _stmt_text(st) -> str:
    k = st.kind
    if k == "MOVE":
        return f"{_val(st.a)} -> {', '.join(st.b)}"
    if k == "COMPUTE":
        return f"{st.a} = {_expr_text(st.b)}"
    if k in ("ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
        return f"{k} {' '.join(_val(v) for v in st.a)} -> {', '.join(st.b or [])} {' '.join(st.c or [])}".strip()
    return k


def _expr_text(node) -> str:
    if isinstance(node, tuple):
        if node[0] == "BINOP":
            return f"({_expr_text(node[2])} {node[1]} {_expr_text(node[3])})"
        return _val(node) if node[0] == "REF" else str(node)
    return str(node)


# ---------------------------------------------------------------------------
# Dialect front-end (bundled parsers)
# ---------------------------------------------------------------------------

def _analyze_dialect(path: str, text: str, language: str) -> dict:
    from ..adapters.dsl_interp import DIALECT_BY_LANGUAGE, parse_dialect

    kind = DIALECT_BY_LANGUAGE.get(language.lower(), "ILG")
    program = parse_dialect(language, text)
    units: List[dict] = []
    if kind == "ILG":
        for name, body in program:
            unit = {
                "file": path, "symbol": name.title().replace("-", " "), "kind": "procedure",
                "line_start": 1, "line_end": 1, "signature": f"PROCEDURE {name}",
                "conditions": [], "assignments": [], "calls": [], "crud": [],
            }
            for st in body:
                _ilg_stmt(st, unit)
            units.append(unit)
    else:
        unit = {
            "file": path, "symbol": "Report Script", "kind": "module",
            "line_start": 1, "line_end": 1, "signature": "RPT module",
            "conditions": [], "assignments": [], "calls": [], "crud": [],
        }
        for st in program:
            _rpt_stmt(st, unit)
        units.append(unit)
    return {"file": path, "units": units, "parse_method": "dialect", "ok": True}


def _ilg_stmt(st, unit: dict) -> None:
    kind = st[0]
    if kind == "SET":
        unit["assignments"].append({"text": f"SET {st[1]} TO {_val(st[2])}", "line": st[3]})
        unit["crud"].append({"op": "update", "store": st[1], "line": st[3]})
    elif kind == "IF":
        unit["conditions"].append(
            {"text": _dcond(st[1]), "line": st[4],
             "effect": _dstext(st[2][0]) if st[2] else ""}
        )
        for s in st[2] + st[3]:
            _ilg_stmt(s, unit)
    elif kind == "LOCK":
        unit["conditions"].append(
            {"text": f"LOCK {st[1]}" + (f" UNTIL {_dcond(st[2])}" if st[2] else ""),
             "line": st[3], "effect": f"interlock {st[1]} engaged"}
        )
        unit["crud"].append({"op": "update", "store": st[1], "line": st[3]})
    elif kind == "ASSERT":
        unit["conditions"].append(
            {"text": f"ASSERT {_dcond(st[1])}", "line": st[3],
             "effect": f"alarm {st[2]}" if isinstance(st[2], str) else "ok"}
        )
    elif kind == "TRIP":
        unit["crud"].append({"op": "update", "store": st[1], "line": st[3]})
        unit["conditions"].append({"text": f"TRIP {st[1]}", "line": st[3],
                                   "effect": f"trip {st[1]} signalled"})
    elif kind == "DO":
        unit["calls"].append(st[1].title().replace("-", " "))


def _rpt_stmt(st, unit: dict) -> None:
    kind = st[0]
    if kind == "DEFINE":
        unit["assignments"].append({"text": f"DEFINE {st[1]} = {st[2]}", "line": st[3]})
    elif kind == "LET":
        unit["assignments"].append({"text": f"LET {st[1]} = {_dexpr(st[2])}", "line": st[3]})
    elif kind == "IF":
        unit["conditions"].append(
            {"text": _dcond(st[1]), "line": st[4],
             "effect": _dstext(st[2][0]) if st[2] else ""}
        )
        for s in st[2] + st[3]:
            _rpt_stmt(s, unit)
    elif kind == "FOR":
        unit["conditions"].append(
            {"text": f"FOR EACH {st[1]} IN {st[2]}", "line": st[4],
             "effect": _dstext(st[3][0]) if st[3] else ""}
        )
        for s in st[3]:
            _rpt_stmt(s, unit)
    elif kind == "ACCUM":
        unit["crud"].append({"op": "create", "store": st[2], "line": st[3]})
        unit["assignments"].append({"text": f"ACCUMULATE {st[1]} INTO {st[2]}", "line": st[3]})
    elif kind == "PRINT":
        unit["crud"].append({"op": "read", "store": "report-output", "line": st[2]})
    elif kind == "SORT":
        unit["crud"].append({"op": "update", "store": st[1], "line": st[4]})


def _dcond(node) -> str:
    if isinstance(node, tuple):
        t = node[0]
        if t == "CMP":
            return f"{_dexpr(node[2])} {node[1]} {_dexpr(node[3])}"
        if t == "LOGIC":
            return f"({_dcond(node[2])} {node[1]} {_dcond(node[3])})"
        if t == "NOT":
            return f"NOT {_dcond(node[1])}"
        if t == "TRUTHY":
            return str(_dexpr(node[1]))
    return str(node)


def _dexpr(node) -> str:
    if isinstance(node, tuple):
        t = node[0]
        if t == "VAR":
            return str(node[1])
        if t == "BINOP":
            return f"{_dexpr(node[2])} {node[1]} {_dexpr(node[3])}"
        if t == "AGG":
            return f"{node[1]}({node[2]})"
    return str(node)


def _dstext(st) -> str:
    if not isinstance(st, tuple):
        return str(st)
    t = st[0]
    if t == "SET":
        return f"SET {st[1]} TO {_dexpr(st[2])}"
    if t == "LET":
        return f"LET {st[1]} = {_dexpr(st[2])}"
    if t == "DEFINE":
        return f"DEFINE {st[1]}"
    if t == "ACCUM":
        return f"ACCUMULATE {st[1]} INTO {st[2]}"
    if t == "PRINT":
        return "PRINT " + " ".join(_dexpr(v) for v in st[1])
    return t


# ---------------------------------------------------------------------------
# Heuristic front-end (last resort for unparseable / unknown files)
# ---------------------------------------------------------------------------

FUNC_RE = re.compile(r"^\s*(?:function|def|func|void|int|public|private|static|\w+\s+)+"
                     r"(\w+)\s*\([^)]*\)\s*\{?\s*$", re.M)
IF_RE = re.compile(r"^\s*(?:IF|if|when|While|while)\s+(.+?)(?:\s+THEN|\s+then|\s*do)?\s*$", re.M)
ASSIGN_RE = re.compile(r"^\s*(?:MOVE\s+(.+?)\s+TO\s+(\w+)|(\w+)\s*(?:=|:=)\s*(.+?))\s*$", re.M)


def _analyze_heuristic(path: str, text: str, language: str) -> dict:
    lines = text.splitlines()
    funcs = [(m.group(1), text[: m.start()].count("\n") + 1) for m in FUNC_RE.finditer(text)]
    unit = {
        "file": path,
        "symbol": funcs[0][0] if funcs else os.path.basename(path),
        "kind": "module",
        "line_start": 1,
        "line_end": len(lines),
        "signature": f"{language} module",
        "conditions": [],
        "assignments": [],
        "calls": [],
        "crud": [],
    }
    for i, line in enumerate(lines, 1):
        m = IF_RE.match(line)
        if m:
            unit["conditions"].append({"text": m.group(1).strip()[:200], "line": i,
                                       "effect": lines[i].strip()[:200] if i < len(lines) else ""})
        m = ASSIGN_RE.match(line)
        if m:
            unit["assignments"].append({"text": " ".join(line.split())[:200], "line": i})
        for name, _ln in funcs:
            if f"{name}(" in line and not line.strip().startswith("function"):
                unit["calls"].append(name)
    return {"file": path, "units": [unit], "parse_method": "heuristic", "ok": True}
