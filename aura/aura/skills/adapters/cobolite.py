"""cobolite — a deterministic COBOL-subset tokenizer/parser/interpreter.

This is a *skill*: no planning, no state between calls, same output for the
same input.  It gives AURA real execution semantics for COBOL programs even
in environments where no GnuCOBOL toolchain exists (the adapter uses
``cobc`` instead when it is available).  The supported subset is the one
used by the AURA benchmark COBOL units — every construct is listed below
and exercised by golden tests in ``tests/test_cobolite.py``.

Subset
------
IDENTIFICATION DIVISION / PROGRAM-ID, DATA DIVISION /
WORKING-STORAGE SECTION (levels 01/05/77, PIC 9(n)[V9(m)] / X(n) / S9(n),
VALUE, 88-levels), PROCEDURE DIVISION with paragraphs and:
MOVE, COMPUTE, ADD, SUBTRACT, MULTIPLY, DIVIDE, IF/ELSE/END-IF,
PERFORM (paragraph [THRU paragraph] [n TIMES]), PERFORM VARYING,
EVALUATE/WHEN/END-EVALUATE, GO TO, DISPLAY, ACCEPT, STOP RUN,
CONTINUE, INITIALIZE, EXEC SQL ... END-EXEC (recorded as an external
store access and refused at run time).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, getcontext, ROUND_DOWN
from typing import Any, Dict, List, Optional, Tuple

getcontext().prec = 28

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(
    r"""(?P<string>'[^']*'|\"[^\"]*\") |
        (?P<number>\d+(?:\.\d+)?) |
        (?P<ident>[A-Za-z][A-Za-z0-9_\-]*) |
        (?P<op>>=|<=|<>|:=|\*\*|[-+*/=<>()&,.;])""",
    re.X,
)


@dataclass
class Tok:
    kind: str
    value: str
    line: int


def tokenize_cobol(text: str) -> List[Tok]:
    toks: List[Tok] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        # fixed format: comment indicator in column 7
        if len(line) > 6 and line[6] == "*" and not line[:6].strip().isdigit():
            continue
        line = re.sub(r"\*>.*$", "", line)
        if not line.strip():
            continue
        # strip fixed-format sequence area (columns 1-6) when purely numeric
        if re.match(r"^\s*\d{4,6}\s+\S", line):
            line = line[7:] if len(line) > 7 else line
        for m in TOKEN_RE.finditer(line):
            kind = m.lastgroup or "op"
            val = m.group(0)
            if kind == "ident":
                kind = "ident"
            toks.append(Tok(kind, val, lineno))
    return toks


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Field:
    name: str
    pic: str
    scale: int = 0
    size: int = 0
    is_numeric: bool = True
    signed: bool = False
    value: Any = None
    level: int = 1
    parent: Optional[str] = None
    line: int = 0
    condition_name: Optional[str] = None   # 88-level
    condition_value: Any = None


@dataclass
class Stmt:
    kind: str
    line: int
    raw: str = ""
    # generic slots consumed by the interpreter
    a: Any = None
    b: Any = None
    c: Any = None
    d: Any = None
    body: List["Stmt"] = field(default_factory=list)
    else_body: List["Stmt"] = field(default_factory=list)
    whens: List[Tuple[Any, List["Stmt"]]] = field(default_factory=list)
    other: List["Stmt"] = field(default_factory=list)


@dataclass
class Paragraph:
    name: str
    line: int
    body: List[Stmt] = field(default_factory=list)


@dataclass
class CobolProgram:
    program_id: str = "PROGRAM"
    fields: Dict[str, Field] = field(default_factory=dict)
    paragraphs: Dict[str, Paragraph] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)          # paragraph run order
    condition_names: Dict[str, Tuple[str, Any]] = field(default_factory=dict)
    external_refs: List[dict] = field(default_factory=list)  # EXEC SQL etc.

    def input_field_names(self) -> List[str]:
        return [f.name for f in self.fields.values() if f.level in (1, 77) and not f.condition_name]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class CobolSyntaxError(Exception):
    pass


class _Parser:
    def __init__(self, toks: List[Tok]) -> None:
        self.toks = toks
        self.i = 0

    def peek(self) -> Optional[Tok]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def next(self) -> Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect_period(self) -> None:
        while self.i < len(self.toks):
            t = self.next()
            if t.kind == "op" and t.value == ".":
                return
        raise CobolSyntaxError("missing period at end of source")

    def at_division(self, name: str) -> bool:
        t = self.peek()
        return bool(t and t.kind == "ident" and t.value.upper() == name and
                    self.i + 1 < len(self.toks) and self.toks[self.i + 1].value.upper() == "DIVISION")

    # -- data division ---------------------------------------------------
    def parse_program(self) -> CobolProgram:
        prog = CobolProgram()
        while self.i < len(self.toks):
            t = self.peek()
            if not t:
                break
            up = t.value.upper()
            if t.kind == "ident" and up == "IDENTIFICATION" and self.at_division("IDENTIFICATION"):
                self.next(); self.next(); self.expect_period()
                if self.peek() and self.peek().value.upper() == "PROGRAM-ID":
                    self.next()
                    if self.peek() and self.peek().value == ".":
                        self.next()
                    name = self.next()
                    prog.program_id = name.value
                    self.expect_period()
            elif t.kind == "ident" and up == "DATA" and self.at_division("DATA"):
                self.next(); self.next(); self.expect_period()
                self._parse_data(prog)
            elif t.kind == "ident" and up == "PROCEDURE" and self.at_division("PROCEDURE"):
                self.next(); self.next(); self.expect_period()
                self._parse_procedure(prog)
            else:
                # skip unknown line-level content
                self.next()
        return prog

    def _parse_data(self, prog: CobolProgram) -> None:
        last_field: Optional[Field] = None
        while self.i < len(self.toks):
            t = self.peek()
            if not t:
                return
            up = t.value.upper()
            if up in ("PROCEDURE", "IDENTIFICATION") and self.i + 1 < len(self.toks) and \
                    self.toks[self.i + 1].value.upper() == "DIVISION":
                return
            if t.kind == "ident" and up in ("WORKING-STORAGE", "LOCAL-STORAGE", "FILE", "LINKAGE") and \
                    self.i + 1 < len(self.toks) and self.toks[self.i + 1].value.upper() == "SECTION":
                self.next(); self.next(); self.expect_period()
                continue
            # level entry: number IDENT ...
            if t.kind == "number" and "." not in t.value:
                level = int(t.value)
                self.next()
                nxt = self.next()
                name = nxt.value
                if name.upper() == "FILLER":
                    name = f"FILLER_{len(prog.fields)}"
                fld = Field(name=name.upper(), pic="", level=level, line=t.line)
                if level == 88:
                    # 88 COND-NAME VALUE literal.
                    if self.peek() and self.peek().value.upper() == "VALUE":
                        self.next()
                        val = self._parse_literal()
                        fld.condition_value = val
                    parent = last_field.name if last_field else "UNKNOWN"
                    prog.condition_names[fld.name] = (parent, fld.condition_value)
                    self.expect_period()
                    continue
                while self.i < len(self.toks):
                    tk = self.peek()
                    if tk.kind == "op" and tk.value == ".":
                        self.next()
                        break
                    w = self.next().value.upper()
                    if w == "PIC" or w == "PICTURE":
                        pic_tok = self.next().value
                        # handle PIC 9(4) / 9(3)V9(2) / X(10) / S9(5)
                        while self.peek() and self.peek().value == "(":
                            self.next()
                            cnt = self.next().value
                            self.next()  # ")"
                            pic_tok += f"({cnt})"
                        fld.pic = pic_tok.upper()
                    elif w == "VALUE":
                        fld.value = self._parse_literal()
                    elif w in ("USAGE", "IS"):
                        continue
                    elif w == "DISPLAY":
                        continue
                    elif w == "COMP-3" or w == "COMPUTATIONAL-3" or w == "COMP":
                        continue
                self._apply_pic(fld)
                prog.fields[fld.name] = fld
                last_field = fld
                continue
            self.next()

    def _parse_literal(self) -> Any:
        t = self.next()
        if t.kind == "string":
            s = t.value[1:-1]
            try:
                return Decimal(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else s
            except InvalidOperation:
                return s
        if t.kind == "number":
            try:
                return Decimal(t.value)
            except InvalidOperation:
                return t.value
        # non-numeric bare word (e.g. ZERO, SPACE)
        up = t.value.upper()
        if up in ("ZERO", "ZEROS", "ZEROES"):
            return Decimal(0)
        if up == "SPACE" or up == "SPACES":
            return ""
        if up == "TRUE":
            return True
        if up == "FALSE":
            return False
        return t.value

    @staticmethod
    def _apply_pic(fld: Field) -> None:
        pic = fld.pic
        if not pic:
            fld.is_numeric = True
            fld.size = 9
            fld.scale = 0
            return
        fld.signed = pic.startswith("S")
        p = pic.lstrip("S")
        if p.startswith("X"):
            fld.is_numeric = False
            m = re.match(r"X(?:\((\d+)\)|(\d)?)", p)
            fld.size = int(m.group(1) or m.group(2) or 1) if m else 1
            fld.scale = 0
        else:
            fld.is_numeric = True
            m = re.match(r"9(?:\((\d+)\)|(\d)?)", p)
            int_part = int(m.group(1) or m.group(2) or 1) if m else 1
            vm = re.search(r"V9(?:\((\d+)\)|(\d)?)", p)
            fld.scale = int(vm.group(1) or vm.group(2) or 0) if vm else 0
            fld.size = int_part + fld.scale

    # -- procedure division ------------------------------------------------
    def _parse_procedure(self, prog: CobolProgram) -> None:
        cur: Optional[Paragraph] = None

        def ensure_para() -> Paragraph:
            nonlocal cur
            if cur is None:
                cur = Paragraph(name="MAIN", line=self.peek().line if self.peek() else 1)
                prog.paragraphs[cur.name] = cur
                prog.order.append(cur.name)
            return cur

        while self.i < len(self.toks):
            t = self.peek()
            if not t:
                return
            up = t.value.upper()
            if up in ("DATA", "IDENTIFICATION") and self.i + 1 < len(self.toks) and \
                    self.toks[self.i + 1].value.upper() == "DIVISION":
                return
            # paragraph header: IDENT .  (word followed by period, next token is a statement keyword or IDENT .)
            if t.kind == "ident" and up not in STATEMENT_KEYWORDS:
                # could be paragraph name or stray token
                j = self.i + 1
                if j < len(self.toks) and self.toks[j].kind == "op" and self.toks[j].value == ".":
                    # lookahead: is the next content a new statement?
                    k = j + 1
                    nxt = self.toks[k] if k < len(self.toks) else None
                    if nxt is None or nxt.kind == "ident" or (nxt.kind == "op" and nxt.value == "."):
                        self.next(); self.next()
                        cur = Paragraph(name=up, line=t.line)
                        prog.paragraphs[cur.name] = cur
                        prog.order.append(cur.name)
                        continue
            para = ensure_para()
            before = self.i
            stmt = self._parse_stmt()
            if stmt is not None:
                para.body.append(stmt)
            elif self.i == before and self.i < len(self.toks):
                self.next()

    # -- statements -------------------------------------------------------
    def _parse_stmt(self) -> Optional[Stmt]:
        t = self.peek()
        if t is None:
            return None
        up = t.value.upper()
        if t.kind == "op" and t.value == ".":
            self.next()
            return None
        if up not in STATEMENT_KEYWORDS:
            return None
        line = t.line
        self.next()

        if up == "MOVE":
            src = self._parse_value()
            if self.peek() and self.peek().value.upper() == "TO":
                self.next()
            targets = []
            while self.peek() and not self._at_stmt_end():
                targets.append(self._parse_ref())
            return Stmt("MOVE", line, a=src, b=targets)

        if up == "COMPUTE":
            tgt = self._parse_ref()
            if self.peek() and self.peek().value == "=":
                self.next()
            expr = self._parse_expr()
            return Stmt("COMPUTE", line, a=tgt, b=expr)

        if up in ("ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
            return self._parse_arith(up, line)

        if up == "IF":
            cond = self._parse_cond()
            if self.peek() and self.peek().value.upper() == "THEN":
                self.next()
            body = self._parse_stmt_block(until={"ELSE", "END-IF"})
            else_body: List[Stmt] = []
            if self.peek() and self.peek().value.upper() == "ELSE":
                self.next()
                else_body = self._parse_stmt_block(until={"END-IF"})
            if self.peek() and self.peek().value.upper() == "END-IF":
                self.next()
            return Stmt("IF", line, a=cond, body=body, else_body=else_body)

        if up == "PERFORM":
            return self._parse_perform(line)

        if up == "EVALUATE":
            subj = self._parse_value()
            whens: List[Tuple[Any, List[Stmt]]] = []
            other: List[Stmt] = []
            while self.peek():
                w = self.peek().value.upper()
                if w == "END-EVALUATE":
                    self.next()
                    break
                if w == "WHEN":
                    self.next()
                    if self.peek() and self.peek().value.upper() == "OTHER":
                        self.next()
                        other = self._parse_stmt_block(until={"WHEN", "END-EVALUATE"})
                    else:
                        val = self._parse_value()
                        if self.peek() and self.peek().value.upper() == "THRU":
                            self.next()
                            hi = self._parse_value()
                            val = ("RANGE", val, hi)
                        whens.append((val, self._parse_stmt_block(until={"WHEN", "END-EVALUATE"})))
                else:
                    self.next()
            return Stmt("EVALUATE", line, a=subj, whens=whens, other=other)

        if up == "GO" or up == "GOTO":
            if self.peek() and self.peek().value.upper() == "TO":
                self.next()
            target = self._parse_ref()
            return Stmt("GOTO", line, a=target)

        if up == "DISPLAY":
            vals = []
            while self.peek() and not self._at_stmt_end():
                if self.peek().value.upper() in ("UPON", "WITH", "NO", "ADVANCING"):
                    while self.peek() and not self._at_stmt_end():
                        self.next()
                    break
                vals.append(self._parse_value())
            return Stmt("DISPLAY", line, a=vals)

        if up == "ACCEPT":
            tgt = self._parse_ref()
            return Stmt("ACCEPT", line, a=tgt)

        if up == "STOP":
            if self.peek() and self.peek().value.upper() == "RUN":
                self.next()
            return Stmt("STOP", line)

        if up == "CONTINUE":
            return Stmt("CONTINUE", line)

        if up == "INITIALIZE":
            tgts = []
            while self.peek() and not self._at_stmt_end():
                tgts.append(self._parse_ref())
            return Stmt("INITIALIZE", line, a=tgts)

        if up == "EXEC":
            # EXEC SQL ... END-EXEC
            parts = []
            while self.i < len(self.toks):
                tk = self.next()
                if tk.kind == "ident" and tk.value.upper() == "END-EXEC":
                    break
                parts.append(tk.value)
            return Stmt("EXEC", line, a=" ".join(parts))

        return Stmt("CONTINUE", line)

    def _parse_perform(self, line: int) -> Stmt:
        if self.peek() and self.peek().value.upper() == "VARYING":
            self.next()
            var = self._parse_ref()
            frm = None
            by = None
            until = None
            if self.peek() and self.peek().value.upper() == "FROM":
                self.next()
                frm = self._parse_value()
            if self.peek() and self.peek().value.upper() == "BY":
                self.next()
                by = self._parse_value()
            if self.peek() and self.peek().value.upper() == "UNTIL":
                self.next()
                until = self._parse_cond()
            body = self._parse_stmt_block(until={"END-PERFORM"})
            if self.peek() and self.peek().value.upper() == "END-PERFORM":
                self.next()
            return Stmt("PERFORM_VARYING", line, a=var, b=frm, c=by, d=until, body=body)
        p1 = self._parse_ref()
        p2 = None
        if self.peek() and self.peek().value.upper() == "THRU":
            self.next()
            p2 = self._parse_ref()
        times = None
        if self.peek() and self.peek().value.upper() == "TIMES":
            self.next()
        else:
            # n TIMES  (number before TIMES)
            if self.peek() and self.peek().kind == "number":
                nxt = self.next()
                if self.peek() and self.peek().value.upper() == "TIMES":
                    self.next()
                    try:
                        times = int(Decimal(nxt.value))
                    except InvalidOperation:
                        times = 1
                else:
                    self.i -= 1
        return Stmt("PERFORM", line, a=p1, b=p2, c=times)

    def _parse_arith(self, op: str, line: int) -> Stmt:
        """Parse ADD/SUBTRACT/MULTIPLY/DIVIDE.

        Slots: a = operands, b = direct target refs (TO/FROM/INTO/BY side,
        updated in place when no GIVING), c = GIVING targets, d = remainder.
        """
        operands: List[Any] = []
        targets: List[str] = []
        giving: List[str] = []
        remainder: Optional[str] = None
        mode = "operands"
        while self.peek() and not self._at_stmt_end():
            w = self.peek().value.upper()
            if w in ("TO", "FROM", "INTO", "BY"):
                self.next()
                mode = "targets"
                continue
            if w == "GIVING":
                self.next()
                mode = "giving"
                continue
            if w == "REMAINDER":
                self.next()
                mode = "remainder"
                continue
            if mode == "operands":
                operands.append(self._parse_value())
            elif mode == "targets":
                targets.append(self._parse_ref())
            elif mode == "giving":
                giving.append(self._parse_ref())
            else:
                remainder = self._parse_ref()
        return Stmt(op, line, a=operands, b=targets, c=giving or None, d=remainder)

    def _parse_stmt_block(self, until: set) -> List[Stmt]:
        out: List[Stmt] = []
        while self.i < len(self.toks):
            t = self.peek()
            if t is None:
                break
            if t.kind == "op" and t.value == ".":
                self.next()
                break
            if t.kind == "ident" and t.value.upper() in until:
                break
            if t.kind == "ident" and t.value.upper() in STATEMENT_KEYWORDS:
                before = self.i
                s = self._parse_stmt()
                if s is not None:
                    out.append(s)
                    continue
                if self.i != before:
                    continue
            self.next()
        return out

    def _at_stmt_end(self) -> bool:
        t = self.peek()
        if t is None:
            return True
        if t.kind == "op" and t.value == ".":
            return True
        if t.kind == "ident" and t.value.upper() in STATEMENT_KEYWORDS:
            return True
        return False

    # -- expressions ------------------------------------------------------
    def _parse_ref(self) -> str:
        t = self.next()
        return t.value.upper()

    def _parse_value(self) -> Any:
        t = self.peek()
        if t is None:
            return None
        if t.kind in ("number", "string"):
            self.next()
            return self._lit(t)
        if t.kind == "ident":
            self.next()
            up = t.value.upper()
            if up in ("ZERO", "ZEROS", "ZEROES"):
                return Decimal(0)
            if up in ("SPACE", "SPACES"):
                return ""
            if up == "TRUE":
                return True
            if up == "FALSE":
                return False
            return ("REF", up)
        if t.kind == "op" and t.value == "(":
            return self._parse_expr()
        self.next()
        return t.value

    @staticmethod
    def _lit(t: Tok) -> Any:
        if t.kind == "string":
            s = t.value[1:-1]
            if re.fullmatch(r"-?\d+(\.\d+)?", s):
                try:
                    return Decimal(s)
                except InvalidOperation:
                    return s
            return s
        try:
            return Decimal(t.value)
        except InvalidOperation:
            return t.value

    def _parse_expr(self) -> Any:
        node = self._parse_term()
        while self.peek() and self.peek().kind == "op" and self.peek().value in ("+", "-"):
            op = self.next().value
            rhs = self._parse_term()
            node = ("BINOP", op, node, rhs)
        return node

    def _parse_term(self) -> Any:
        node = self._parse_factor()
        while self.peek() and self.peek().kind == "op" and self.peek().value in ("*", "/"):
            op = self.next().value
            rhs = self._parse_factor()
            node = ("BINOP", op, node, rhs)
        return node

    def _parse_factor(self) -> Any:
        t = self.peek()
        if t is None:
            return Decimal(0)
        if t.kind == "op" and t.value == "(":
            self.next()
            e = self._parse_expr()
            if self.peek() and self.peek().value == ")":
                self.next()
            return e
        return self._parse_value()

    def _parse_cond(self) -> Any:
        left = self._parse_simple_cond()
        while self.peek() and self.peek().kind == "ident" and self.peek().value.upper() in ("AND", "OR"):
            op = self.next().value.upper()
            right = self._parse_simple_cond()
            left = ("LOGIC", op, left, right)
        return left

    def _parse_simple_cond(self) -> Any:
        negate = False
        if self.peek() and self.peek().kind == "ident" and self.peek().value.upper() == "NOT":
            self.next()
            negate = True
        left = self._parse_value()
        t = self.peek()
        if t and t.kind == "op" and t.value in ("=", ">", "<", ">=", "<=", "<>"):
            op = self.next().value
            right = self._parse_value()
            node: Any = ("CMP", op, left, right)
        elif t and t.kind == "ident" and t.value.upper() in ("=", "GREATER", "LESS", "EQUAL"):
            w = self.next().value.upper()
            if w in ("GREATER", "LESS"):
                if self.peek() and self.peek().value.upper() == "THAN":
                    self.next()
                op = ">" if w == "GREATER" else "<"
                right = self._parse_value()
                node = ("CMP", op, left, right)
            elif w == "EQUAL":
                if self.peek() and self.peek().value.upper() == "TO":
                    self.next()
                right = self._parse_value()
                node = ("CMP", "=", left, right)
            else:
                right = self._parse_value()
                node = ("CMP", "=", left, right)
        else:
            node = ("TRUTHY", left)
        if negate:
            node = ("NOT", node)
        return node


STATEMENT_KEYWORDS = {
    "MOVE", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "IF", "PERFORM",
    "EVALUATE", "GO", "GOTO", "DISPLAY", "ACCEPT", "STOP", "CONTINUE", "INITIALIZE",
    "EXEC", "ELSE", "END-IF", "END-PERFORM", "END-EVALUATE", "THRU", "VARYING",
    "UNTIL", "WHEN", "OTHER", "GIVING", "REMAINDER", "CALL", "EXIT", "GOBACK",
}


def parse_cobol(text: str) -> CobolProgram:
    """Parse COBOL source into a :class:`CobolProgram`."""
    return _Parser(tokenize_cobol(text)).parse_program()


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------


class CobolRuntimeError(Exception):
    pass


class _ExternalStore(CobolRuntimeError):
    """Raised when code touches an external system (EXEC SQL etc.)."""


class Interpreter:
    def __init__(self, prog: CobolProgram, inputs: Optional[Dict[str, Any]] = None,
                 max_steps: int = 2_000_000) -> None:
        self.prog = prog
        self.inputs = dict(inputs or {})
        self.max_steps = max_steps
        self.steps = 0
        self.outputs: List[str] = []
        self.trace: List[str] = []
        self.stopped = False
        self.state: Dict[str, Any] = {}
        for name, fld in prog.fields.items():
            if fld.condition_name:
                continue
            self.state[name] = self._default(fld)
        for name, val in self.inputs.items():
            up = name.upper()
            if up in self.state:
                self.state[up] = self._coerce(val, prog.fields.get(up))
            else:
                self.state[up] = val

    @staticmethod
    def _default(fld: Field) -> Any:
        if fld.value is not None:
            return fld.value
        return Decimal(0) if fld.is_numeric else ""

    @staticmethod
    def _coerce(val: Any, fld: Optional[Field]) -> Any:
        if fld is None:
            return val
        try:
            if fld.is_numeric:
                d = Decimal(str(val))
                q = Decimal(1).scaleb(-fld.scale)
                # COBOL truncates (no rounding) when storing to a smaller scale
                return d.quantize(q, rounding=ROUND_DOWN)
            s = str(val)
            return s[: fld.size].ljust(fld.size) if fld.size else s
        except (InvalidOperation, ValueError):
            return val

    # -- expression evaluation -------------------------------------------
    def _deref(self, node: Any) -> Any:
        if isinstance(node, tuple) and node and node[0] == "REF":
            name = node[1]
            if name in self.state:
                return self.state[name]
            if name in self.prog.condition_names:
                parent, expected = self.prog.condition_names[name]
                return self.state.get(parent) == expected
            raise CobolRuntimeError(f"undefined identifier {name}")
        return node

    def _eval(self, node: Any) -> Any:
        self._tick()
        if not isinstance(node, tuple):
            return node
        tag = node[0]
        if tag == "REF":
            return self._deref(node)
        if tag == "BINOP":
            op = node[1]
            a = self._num(self._eval(node[2]))
            b = self._num(self._eval(node[3]))
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if b == 0:
                    raise CobolRuntimeError("division by zero")
                return a / b
        if tag == "CMP":
            op = node[1]
            a = self._eval(node[2])
            b = self._eval(node[3])
            if isinstance(a, str) or isinstance(b, str):
                a, b = str(a).strip(), str(b).strip()
            else:
                a, b = self._num(a), self._num(b)
            return {
                "=": a == b, ">": a > b, "<": a < b,
                ">=": a >= b, "<=": a <= b, "<>": a != b,
            }[op]
        if tag == "TRUTHY":
            v = self._eval(node[1])
            return bool(v) and v != 0 if not isinstance(v, str) else bool(v.strip())
        if tag == "NOT":
            return not self._eval(node[1])
        if tag == "LOGIC":
            if node[1] == "AND":
                return bool(self._eval(node[2])) and bool(self._eval(node[3]))
            return bool(self._eval(node[2])) or bool(self._eval(node[3]))
        return node

    @staticmethod
    def _num(v: Any) -> Decimal:
        if isinstance(v, Decimal):
            return v
        if isinstance(v, bool):
            return Decimal(1 if v else 0)
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        try:
            return Decimal(str(v).strip() or 0)
        except InvalidOperation:
            return Decimal(0)

    def _tick(self) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise CobolRuntimeError("interpreter step budget exceeded")

    # -- statements -------------------------------------------------------
    def run(self, entry: Optional[str] = None) -> Dict[str, Any]:
        order = list(self.prog.order)
        if entry:
            entry_up = entry.upper()
            if entry_up in self.prog.paragraphs:
                idx = order.index(entry_up) if entry_up in order else 0
                order = order[idx:]
        self._exec_paragraphs(order)
        return {"state": self.state, "outputs": self.outputs, "trace": "\n".join(self.trace),
                "steps": self.steps}

    def _exec_paragraphs(self, names: List[str]) -> None:
        for name in names:
            if self.stopped:
                return
            para = self.prog.paragraphs.get(name)
            if para is None:
                raise CobolRuntimeError(f"unknown paragraph {name}")
            self.trace.append(f"PERFORM {name}")
            self._exec_block(para.body)

    def _exec_block(self, block: List[Stmt]) -> None:
        for stmt in block:
            if self.stopped:
                return
            self._exec(stmt)

    def _exec(self, s: Stmt) -> None:
        self._tick()
        k = s.kind
        if k == "MOVE":
            val = self._eval(s.a)
            for tgt in s.b:
                self._assign(tgt, val)
        elif k == "COMPUTE":
            self._assign(s.a, self._eval(s.b))
        elif k in ("ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
            self._exec_arith(s)
        elif k == "IF":
            if self._eval(s.a):
                self._exec_block(s.body)
            else:
                self._exec_block(s.else_body)
        elif k == "PERFORM":
            self._exec_perform(s)
        elif k == "PERFORM_VARYING":
            var = s.a
            self._assign(var, self._eval(s.b))
            while not self._eval(s.d):
                self._tick()
                self._exec_block(s.body)
                self._assign(var, self._eval(("BINOP", "+", var if isinstance(var, tuple) else ("REF", var), s.c)))
        elif k == "EVALUATE":
            subj = self._eval(s.a)
            done = False
            for val, body in s.whens:
                if isinstance(val, tuple) and val and val[0] == "RANGE":
                    lo = self._num(self._eval(val[1]))
                    hi = self._num(self._eval(val[2]))
                    hit = lo <= self._num(subj) <= hi
                else:
                    hit = self._eval(val) == subj
                if hit:
                    self._exec_block(body)
                    done = True
                    break
            if not done:
                self._exec_block(s.other)
        elif k == "GOTO":
            target = s.a if isinstance(s.a, str) else s.a[1]
            self._jump(target)
        elif k == "DISPLAY":
            parts = []
            for v in s.a:
                val = self._eval(v)
                parts.append(self._fmt(val))
            line = " ".join(parts)
            self.outputs.append(line)
            self.trace.append(f"DISPLAY {line}")
        elif k == "ACCEPT":
            name = s.a if isinstance(s.a, str) else s.a[1]
            if name in self.inputs:
                self.state[name] = self._coerce(self.inputs[name], self.prog.fields.get(name))
            else:
                self.state[name] = self._coerce(0, self.prog.fields.get(name))
        elif k == "STOP":
            self.stopped = True
        elif k == "EXEC":
            raise _ExternalStore(f"external store access refused at run time: {s.a[:80]}")
        # CONTINUE and unknowns: no-op

    def _exec_arith(self, s: Stmt) -> None:
        op = s.kind
        operands = [self._num(self._eval(v)) for v in s.a]
        targets = list(s.b or [])
        giving = list(s.c or [])
        if op == "ADD":
            # ADD a b TO c [GIVING d] -> d (or c) = a + b + c
            acc = Decimal(0)
            for o in operands:
                acc += o
            if targets:
                tval = self._num(self._deref(("REF", targets[0])))
                total = acc + tval
            else:
                total = acc
            for t in (giving or targets):
                self._assign(t, total)
        elif op == "SUBTRACT":
            # SUBTRACT a b FROM c [GIVING d] -> d (or c) = c - (a + b)
            total = Decimal(0)
            for o in operands:
                total += o
            base = self._num(self._deref(("REF", targets[0]))) if targets else Decimal(0)
            result = base - total
            for t in (giving or targets):
                self._assign(t, result)
        elif op == "MULTIPLY":
            # MULTIPLY a BY b [GIVING c] -> c (or b) = a * b
            prod = operands[0] if operands else Decimal(1)
            base = self._num(self._deref(("REF", targets[0]))) if targets else Decimal(1)
            result = prod * base if not giving else prod * base
            for t in (giving or targets):
                self._assign(t, result)
        elif op == "DIVIDE":
            # DIVIDE a INTO b [GIVING c] -> c (or b) = b / a
            a = operands[0] if operands else Decimal(1)
            if a == 0:
                raise CobolRuntimeError("division by zero")
            base = self._num(self._deref(("REF", targets[0]))) if targets else Decimal(0)
            for t in (giving or targets):
                self._assign(t, base / a)
        if s.d is not None:
            self._assign(s.d, Decimal(0))

    def _exec_perform(self, s: Stmt) -> None:
        p1 = s.a if isinstance(s.a, str) else s.a[1]
        p2 = s.b if isinstance(s.b, str) else (s.b[1] if isinstance(s.b, tuple) else None)
        times = s.c if s.c else 1
        names = list(self.prog.order)
        if p1 in names:
            start = names.index(p1)
            end = names.index(p2) if p2 and p2 in names else start
            span = names[start : end + 1]
        else:
            span = [p1] if p1 in self.prog.paragraphs else []
        for _ in range(int(times)):
            if self.stopped:
                return
            self._exec_paragraphs(span)

    def _jump(self, target: str) -> None:
        names = list(self.prog.order)
        if target in names:
            self._exec_paragraphs(names[names.index(target) :])

    def _assign(self, target: Any, value: Any) -> None:
        name = target if isinstance(target, str) else target[1] if isinstance(target, tuple) else str(target)
        fld = self.prog.fields.get(name)
        self.state[name] = self._coerce(value, fld)
        self.trace.append(f"SET {name} = {self._fmt(self.state[name])}")

    @staticmethod
    def _fmt(v: Any) -> str:
        if isinstance(v, Decimal):
            s = format(v.normalize(), "f")
            return s
        return str(v).rstrip()


def run_cobol(text: str, inputs: Optional[Dict[str, Any]] = None,
              entry: Optional[str] = None, max_steps: int = 2_000_000) -> Dict[str, Any]:
    prog = parse_cobol(text)
    return Interpreter(prog, inputs, max_steps).run(entry)


def norm_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise interpreter state to JSON-comparable values."""
    out = {}
    for k, v in state.items():
        if isinstance(v, Decimal):
            out[k] = float(format(v.normalize(), "f"))
        elif isinstance(v, bool):
            out[k] = v
        elif isinstance(v, str):
            out[k] = v.rstrip()
        else:
            out[k] = v
    return out
