"""Interpreters for the two AURA legacy-dialect corpora.

Both dialects are invented domain-specific languages with **no public
grammar**; their grammars were written down first (ground truth) and the
corpora were authored against those grammars, so keyword/block-boundary
metrics can be computed exactly (synopsis 6.5/6.6).

ILG — industrial interlock guard dialect (uppercase, fixed keywords,
``END-IF``-style blocks, alarm/trip semantics over named boolean/numeric
signals).

RPT — report-scripting dialect (DEFINE/FOR EACH/ACCUMULATE/PRINT/SORT
aggregation pipeline over record lists).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class DialectError(Exception):
    pass


# ---------------------------------------------------------------------------
# Shared tokenizer
# ---------------------------------------------------------------------------

TOK_RE = re.compile(
    r"""(?P<string>'[^']*') |
        (?P<number>\d+(?:\.\d+)?) |
        (?P<ident>[A-Za-z_][A-Za-z0-9_\-]*) |
        (?P<op><=|>=|<>|[-+*/=<>()&,\.]) |
        (?P<ws>\s+)""",
    re.X,
)


@dataclass
class DTok:
    kind: str
    value: str
    line: int


def tokenize_dialect(text: str) -> List[DTok]:
    toks: List[DTok] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = re.sub(r"(#|//).*$", "", raw)
        for m in TOK_RE.finditer(line):
            kind = m.lastgroup or "op"
            if kind == "ws":
                continue
            toks.append(DTok(kind, m.group(0), lineno))
    return toks


# ---------------------------------------------------------------------------
# Shared expression evaluation
# ---------------------------------------------------------------------------


class _Ctx:
    def __init__(self, state: Dict[str, Any], max_steps: int = 500_000) -> None:
        self.state = state
        self.outputs: List[str] = []
        self.trace: List[str] = []
        self.steps = 0
        self.max_steps = max_steps
        self.trips: List[str] = []

    def tick(self) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise DialectError("interpreter step budget exceeded")

    def get(self, name: str) -> Any:
        key = name.upper().replace("-", "_")
        if key in self.state:
            return self.state[key]
        raise DialectError(f"undefined variable {name}")

    def set(self, name: str, value: Any) -> None:
        key = name.upper().replace("-", "_")
        self.state[key] = value
        self.trace.append(f"SET {key} = {value!r}")


def _num(v: Any) -> float:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# ILG parser + interpreter
# ---------------------------------------------------------------------------


class ILGParser:
    KEYWORDS = {"PROCEDURE", "SET", "TO", "IF", "THEN", "ELSE", "END-IF", "LOCK",
                "UNTIL", "ASSERT", "ALARM", "TRIP", "REASON", "DO", "AND", "OR",
                "NOT", "ON", "OFF"}

    def __init__(self, toks: List[DTok]) -> None:
        self.toks = toks
        self.i = 0

    def peek(self) -> Optional[DTok]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def next(self) -> DTok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect_period(self) -> None:
        while self.i < len(self.toks):
            t = self.next()
            if t.kind == "op" and t.value == ".":
                return
        raise DialectError("missing '.'")

    def parse_program(self) -> List[Tuple[str, List[Any]]]:
        procs: List[Tuple[str, List[Any]]] = []
        while self.i < len(self.toks):
            t = self.peek()
            if not t:
                break
            if t.kind == "ident" and t.value.upper() == "PROCEDURE":
                self.next()
                name = self.next().value
                self.expect_period()
                body = self.parse_block({"PROCEDURE"})
                procs.append((name, body))
            else:
                self.next()
        return procs

    def parse_block(self, until: set) -> List[Any]:
        out: List[Any] = []
        while self.i < len(self.toks):
            t = self.peek()
            if t is None:
                break
            if t.kind == "ident" and t.value.upper() in until:
                break
            stmt = self.parse_stmt()
            if stmt is not None:
                out.append(stmt)
        return out

    def parse_stmt(self) -> Any:
        t = self.peek()
        if t is None:
            return None
        if t.kind == "op" and t.value == ".":
            self.next()
            return None
        up = t.value.upper()
        line = t.line
        if up == "SET":
            self.next()
            name = self.next().value
            if self.peek() and self.peek().value.upper() == "TO":
                self.next()
            val = self.parse_value()
            self.expect_period()
            return ("SET", name, val, line)
        if up == "IF":
            self.next()
            cond = self.parse_cond()
            if self.peek() and self.peek().value.upper() == "THEN":
                self.next()
            body = self.parse_block({"ELSE", "END-IF"})
            else_body: List[Any] = []
            if self.peek() and self.peek().value.upper() == "ELSE":
                self.next()
                else_body = self.parse_block({"END-IF"})
            if self.peek() and self.peek().value.upper() == "END-IF":
                self.next()
            self.expect_period()
            return ("IF", cond, body, else_body, line)
        if up == "LOCK":
            self.next()
            name = self.next().value
            until = None
            if self.peek() and self.peek().value.upper() == "UNTIL":
                self.next()
                until = self.parse_cond()
            self.expect_period()
            return ("LOCK", name, until, line)
        if up == "ASSERT":
            self.next()
            cond = self.parse_cond()
            alarm = ""
            if self.peek() and self.peek().value.upper() == "ALARM":
                self.next()
                alarm = self.parse_value()
            self.expect_period()
            return ("ASSERT", cond, alarm, line)
        if up == "TRIP":
            self.next()
            name = self.next().value
            reason = ""
            if self.peek() and self.peek().value.upper() == "REASON":
                self.next()
                reason = self.parse_value()
            self.expect_period()
            return ("TRIP", name, reason, line)
        if up == "DO":
            self.next()
            name = self.next().value
            self.expect_period()
            return ("DO", name, line)
        self.next()
        return None

    def parse_value(self) -> Any:
        t = self.peek()
        if t is None:
            return None
        self.next()
        if t.kind == "string":
            return t.value[1:-1]
        if t.kind == "number":
            return float(t.value) if "." in t.value else int(t.value)
        up = t.value.upper()
        if up == "ON":
            return 1
        if up == "OFF":
            return 0
        return ("VAR", t.value)

    def parse_cond(self) -> Any:
        node = self.parse_cmp()
        while self.peek() and self.peek().kind == "ident" and self.peek().value.upper() in ("AND", "OR"):
            op = self.next().value.upper()
            rhs = self.parse_cmp()
            node = ("LOGIC", op, node, rhs)
        return node

    def parse_cmp(self) -> Any:
        negate = False
        if self.peek() and self.peek().kind == "ident" and self.peek().value.upper() == "NOT":
            self.next()
            negate = True
        left = self.parse_value()
        t = self.peek()
        if t and t.kind == "op" and t.value in ("=", "<>", ">", "<", ">=", "<="):
            op = self.next().value
            right = self.parse_value()
            node: Any = ("CMP", op, left, right)
        else:
            node = ("TRUTHY", left)
        return ("NOT", node) if negate else node


def eval_ilg_node(node: Any, ctx: _Ctx) -> Any:
    ctx.tick()
    if not isinstance(node, tuple):
        return node
    tag = node[0]
    if tag == "VAR":
        return ctx.get(node[1])
    if tag == "CMP":
        op = node[1]
        a, b = eval_ilg_node(node[2], ctx), eval_ilg_node(node[3], ctx)
        if isinstance(a, str) or isinstance(b, str):
            a, b = str(a), str(b)
        else:
            a, b = _num(a), _num(b)
        return {"=": a == b, "<>": a != b, ">": a > b, "<": a < b,
                ">=": a >= b, "<=": a <= b}[op]
    if tag == "TRUTHY":
        v = eval_ilg_node(node[1], ctx)
        return bool(v) if isinstance(v, (bool, int, float)) else bool(str(v).strip())
    if tag == "NOT":
        return not eval_ilg_node(node[1], ctx)
    if tag == "LOGIC":
        a = eval_ilg_node(node[2], ctx)
        b = eval_ilg_node(node[3], ctx)
        return (a and b) if node[1] == "AND" else (a or b)
    return node


def run_ilg(procs: List[Tuple[str, List[Any]]], inputs: Dict[str, Any],
            entry: Optional[str] = None, max_steps: int = 500_000) -> Dict[str, Any]:
    ctx = _Ctx({k.upper().replace("-", "_"): v for k, v in inputs.items()}, max_steps)
    table = dict(procs)
    order = [p[0] for p in procs]
    start = [entry] if entry and entry in table else order

    def run_body(body: List[Any]) -> None:
        for stmt in body:
            exec_ilg_stmt(stmt, ctx, table)

    def exec_ilg_stmt(stmt: Any, ctx: _Ctx, table: Dict[str, List[Any]]) -> None:
        ctx.tick()
        kind = stmt[0]
        if kind == "SET":
            val = eval_ilg_node(stmt[2], ctx)
            ctx.set(stmt[1], val)
        elif kind == "IF":
            if eval_ilg_node(stmt[1], ctx):
                run_body(stmt[2])
            else:
                run_body(stmt[3])
        elif kind == "LOCK":
            guard = stmt[2]
            if guard is not None:
                if not eval_ilg_node(guard, ctx):
                    ctx.trips.append(f"{stmt[1]}: lock guard unsatisfied")
                    ctx.trace.append(f"LOCK {stmt[1]} unresolved")
            ctx.trace.append(f"LOCK {stmt[1]}")
        elif kind == "ASSERT":
            if not eval_ilg_node(stmt[1], ctx):
                alarm = stmt[2] if isinstance(stmt[2], str) else ""
                ctx.outputs.append(f"ALARM:{alarm}")
                ctx.trips.append(f"assertion failed: {alarm}")
                ctx.trace.append(f"ASSERT-FAIL {alarm}")
            else:
                ctx.trace.append("ASSERT-OK")
        elif kind == "TRIP":
            ctx.trips.append(f"{stmt[1]}: {stmt[2] if isinstance(stmt[2], str) else ''}")
            ctx.outputs.append(f"TRIP:{stmt[1]}")
            ctx.trace.append(f"TRIP {stmt[1]}")
        elif kind == "DO":
            name = stmt[1]
            if name in table:
                run_body(table[name])

    for name in start:
        if name in table:
            ctx.trace.append(f"PROCEDURE {name}")
            run_body(table[name])
    return {"state": ctx.state, "outputs": ctx.outputs,
            "trace": "\n".join(ctx.trace), "steps": ctx.steps}


# ---------------------------------------------------------------------------
# RPT parser + interpreter
# ---------------------------------------------------------------------------


class RPTParser(ILGParser):
    KEYWORDS = {"DEFINE", "AS", "FOR", "EACH", "IN", "DO", "END-FOR", "LET",
                "IF", "THEN", "ELSE", "END-IF", "PRINT", "ACCUMULATE", "INTO",
                "SORT", "BY", "ASCENDING", "DESCENDING", "AND", "OR", "NOT",
                "SUM", "COUNT", "MIN", "MAX", "AVERAGE"}

    def parse_program(self) -> List[Any]:
        return self.parse_block(set())

    def parse_block(self, until: set) -> List[Any]:
        out: List[Any] = []
        while self.i < len(self.toks):
            t = self.peek()
            if t is None:
                break
            if t.kind == "ident" and t.value.upper() in until:
                break
            stmt = self.parse_stmt()
            if stmt is not None:
                out.append(stmt)
        return out

    def parse_stmt(self) -> Any:
        t = self.peek()
        if t is None:
            return None
        if t.kind == "op" and t.value == ".":
            self.next()
            return None
        up = t.value.upper()
        line = t.line
        if up == "DEFINE":
            self.next()
            name = self.next().value
            init: Any = 0
            if self.peek() and self.peek().value.upper() == "AS":
                self.next()
                self.next()  # type name
                if self.peek() and self.peek().kind == "op" and self.peek().value == "=":
                    self.next()
                    init = self.parse_expr()
            elif self.peek() and self.peek().kind == "op" and self.peek().value == "=":
                self.next()
                init = self.parse_expr()
            self.expect_period()
            return ("DEFINE", name, init, line)
        if up == "LET":
            self.next()
            name = self.next().value
            if self.peek() and self.peek().kind == "op" and self.peek().value == "=":
                self.next()
            expr = self.parse_expr()
            self.expect_period()
            return ("LET", name, expr, line)
        if up == "FOR":
            self.next()
            if self.peek() and self.peek().value.upper() == "EACH":
                self.next()
            var = self.next().value
            if self.peek() and self.peek().value.upper() == "IN":
                self.next()
            coll = self.next().value
            if self.peek() and self.peek().value.upper() == "DO":
                self.next()
            body = self.parse_block({"END-FOR"})
            if self.peek() and self.peek().value.upper() == "END-FOR":
                self.next()
            self.expect_period()
            return ("FOR", var, coll, body, line)
        if up == "IF":
            self.next()
            cond = self.parse_cond()
            if self.peek() and self.peek().value.upper() == "THEN":
                self.next()
            body = self.parse_block({"ELSE", "END-IF"})
            else_body: List[Any] = []
            if self.peek() and self.peek().value.upper() == "ELSE":
                self.next()
                else_body = self.parse_block({"END-IF"})
            if self.peek() and self.peek().value.upper() == "END-IF":
                self.next()
            self.expect_period()
            return ("IF", cond, body, else_body, line)
        if up == "PRINT":
            self.next()
            vals = []
            while self.peek() and not (self.peek().kind == "op" and self.peek().value == "."):
                vals.append(self.parse_expr())
                if self.peek() and self.peek().kind == "op" and self.peek().value == ",":
                    self.next()
            self.expect_period()
            return ("PRINT", vals, line)
        if up == "ACCUMULATE":
            self.next()
            src = self.next().value
            if self.peek() and self.peek().value.upper() == "INTO":
                self.next()
            dst = self.next().value
            self.expect_period()
            return ("ACCUM", src, dst, line)
        if up == "SORT":
            self.next()
            coll = self.next().value
            by = ""
            order = "ASCENDING"
            if self.peek() and self.peek().value.upper() == "BY":
                self.next()
                by = self.next().value
            if self.peek() and self.peek().value.upper() in ("ASCENDING", "DESCENDING"):
                order = self.next().value.upper()
            self.expect_period()
            return ("SORT", coll, by, order, line)
        self.next()
        return None

    def parse_expr(self) -> Any:
        node = self.parse_term()
        while self.peek() and self.peek().kind == "op" and self.peek().value in ("+", "-"):
            op = self.next().value
            node = ("BINOP", op, node, self.parse_term())
        return node

    def parse_term(self) -> Any:
        node = self.parse_atom()
        while self.peek() and self.peek().kind == "op" and self.peek().value in ("*", "/"):
            op = self.next().value
            node = ("BINOP", op, node, self.parse_atom())
        return node

    def parse_atom(self) -> Any:
        t = self.peek()
        if t is None:
            return 0
        if t.kind == "op" and t.value == "(":
            self.next()
            e = self.parse_expr()
            if self.peek() and self.peek().value == ")":
                self.next()
            return e
        if t.kind == "ident" and t.value.upper() in ("SUM", "COUNT", "MIN", "MAX", "AVERAGE"):
            agg = self.next().value.upper()
            name = self.next().value
            return ("AGG", agg, name)
        return self.parse_value()


def run_rpt(program: List[Any], inputs: Dict[str, Any], max_steps: int = 500_000) -> Dict[str, Any]:
    state: Dict[str, Any] = {k.upper().replace("-", "_"): v for k, v in inputs.items()}
    outputs: List[str] = []
    trace: List[str] = []
    steps = [0]

    def tick() -> None:
        steps[0] += 1
        if steps[0] > max_steps:
            raise DialectError("interpreter step budget exceeded")

    def get(name: str) -> Any:
        key = name.upper().replace("-", "_")
        if key in state:
            return state[key]
        raise DialectError(f"undefined variable {name}")

    def set_(name: str, v: Any) -> None:
        key = name.upper().replace("-", "_")
        state[key] = v
        trace.append(f"SET {key} = {v!r}")

    def ev(node: Any) -> Any:
        tick()
        if not isinstance(node, tuple):
            return node
        tag = node[0]
        if tag == "VAR":
            return get(node[1])
        if tag == "BINOP":
            a, b = _num(ev(node[2])), _num(ev(node[3]))
            return {"+": a + b, "-": a - b, "*": a * b, "/": (a / b if b else 0.0)}[node[1]]
        if tag == "AGG":
            coll = ev(("VAR", node[2])) if isinstance(node[2], str) else node[2]
            vals = [_num(r) for r in coll] if isinstance(coll, list) else [_num(coll)]
            if not vals:
                return 0.0
            return {"SUM": sum(vals), "COUNT": len(vals), "MIN": min(vals),
                    "MAX": max(vals), "AVERAGE": sum(vals) / len(vals)}[node[1]]
        if tag == "CMP":
            op = node[1]
            a, b = ev(node[2]), ev(node[3])
            if isinstance(a, str) or isinstance(b, str):
                a, b = str(a), str(b)
            else:
                a, b = _num(a), _num(b)
            return {"=": a == b, "<>": a != b, ">": a > b, "<": a < b,
                    ">=": a >= b, "<=": a <= b}[op]
        if tag == "TRUTHY":
            return bool(ev(node[1]))
        if tag == "NOT":
            return not ev(node[1])
        if tag == "LOGIC":
            a, b = ev(node[2]), ev(node[3])
            return (a and b) if node[1] == "AND" else (a or b)
        return node

    def exec_block(body: List[Any]) -> None:
        for stmt in body:
            exec_stmt(stmt)

    def exec_stmt(stmt: Any) -> None:
        tick()
        kind = stmt[0]
        if kind == "DEFINE":
            set_(stmt[1], ev(stmt[2]))
        elif kind == "LET":
            set_(stmt[1], ev(stmt[2]))
        elif kind == "FOR":
            var, coll_name, body = stmt[1], stmt[2], stmt[3]
            coll = get(coll_name)
            if not isinstance(coll, list):
                coll = [coll]
            for item in coll:
                set_(var, item)
                if isinstance(item, dict):
                    # field access: record fields enter state as VAR_FIELD
                    for k, v in item.items():
                        state[f"{var.upper()}_{k.upper()}"] = v
                exec_block(body)
        elif kind == "IF":
            if ev(stmt[1]):
                exec_block(stmt[2])
            else:
                exec_block(stmt[3])
        elif kind == "PRINT":
            parts = []
            for v in stmt[1]:
                val = ev(v)
                parts.append(str(int(val)) if isinstance(val, float) and val.is_integer() else str(val))
            line = " ".join(parts)
            outputs.append(line)
            trace.append(f"PRINT {line}")
        elif kind == "ACCUM":
            src = get(stmt[1])
            dst = get(stmt[2]) if stmt[2].upper().replace("-", "_") in state else 0
            if isinstance(src, list):
                total = sum(_num(x) for x in src)
            else:
                total = _num(src) + _num(dst)
            set_(stmt[2], total)
        elif kind == "SORT":
            coll = get(stmt[1])
            by = stmt[2]
            reverse = stmt[3] == "DESCENDING"
            if isinstance(coll, list) and by:
                try:
                    coll = sorted(coll, key=lambda r: _num(r.get(by, 0)) if isinstance(r, dict) else _num(r), reverse=reverse)
                except Exception:
                    pass
                set_(stmt[1], coll)

    exec_block(program)
    return {"state": state, "outputs": outputs, "trace": "\n".join(trace), "steps": steps[0]}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

DIALECT_BY_LANGUAGE = {"interlock": "ILG", "reportscript": "RPT", "ilg": "ILG", "rpt": "RPT"}


def parse_dialect(language: str, text: str) -> Any:
    kind = DIALECT_BY_LANGUAGE.get(language.lower())
    toks = tokenize_dialect(text)
    if kind == "ILG":
        return ILGParser(toks).parse_program()
    if kind == "RPT":
        return RPTParser(toks).parse_program()
    raise DialectError(f"unknown dialect {language!r}")


def run_dialect(language: str, text: str, inputs: Optional[Dict[str, Any]] = None,
                entry: Optional[str] = None, max_steps: int = 500_000) -> Dict[str, Any]:
    kind = DIALECT_BY_LANGUAGE.get(language.lower())
    inputs = inputs or {}
    if kind == "ILG":
        procs = parse_dialect(language, text)
        return run_ilg(procs, inputs, entry, max_steps)
    if kind == "RPT":
        program = parse_dialect(language, text)
        return run_rpt(program, inputs, max_steps)
    raise DialectError(f"unknown dialect {language!r}")
