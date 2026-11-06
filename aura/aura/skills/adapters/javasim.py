"""javasim — a deterministic Java-subset tokenizer/parser/interpreter.

Fallback execution engine for legacy Java code in environments without a
Java *compiler* (the adapter prefers real ``javac``/``java`` when present,
e.g. in CI, so the interpreter is cross-valid against the real
toolchain).  The bundled jdk4py runtime can run bytecode but ships no
``jdk.compiler`` module, which is why this interpreter exists.

Supported subset (the one used by the AURA benchmark Java units):

* ``import`` declarations (ignored); one or more ``public class`` types;
* public fields of type ``int``/``String``/``boolean`` with optional
  initialisers, and methods with typed parameters;
* statements: local declarations, assignment (``=``, ``+=``, ``-=``,
  ``*=``, ``/=``), ``if``/``else if``/``else``, ``while``, 3-clause
  ``for``, ``return``, ``x++``/``x--``, expression statements;
* expressions: integer / string / boolean / ``null`` literals, variables,
  arithmetic with Java integer division (truncation toward zero),
  comparisons, ``&&``/``||``/``!``, string concatenation with ``+``,
  method calls, ``this.m(...)`` calls.

Every construct above is exercised by ``tests/test_javasim.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class JavaSyntaxError(Exception):
    pass


class JavaRuntimeError(Exception):
    pass


TOKEN_RE = re.compile(
    r"""(?P<string>"(?:[^"\\]|\\.)*") |
        (?P<number>\d+) |
        (?P<ident>[A-Za-z_][A-Za-z0-9_]*) |
        (?P<op>==|!=|<=|>=|&&|\|\||\+\+|--|\+=|-=|\*=|/=|[-+*/%<>=!;,(){}\[\].])""",
    re.X,
)

_PRIM_TYPES = {"int", "long", "double", "float", "boolean", "bool", "String", "string", "void"}


@dataclass
class Tok:
    kind: str
    value: str
    line: int


def tokenize_java(text: str) -> List[Tok]:
    toks: List[Tok] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = re.sub(r"//.*$", "", raw)
        line = re.sub(r"/\*.*?\*/", "", line)
        for m in TOKEN_RE.finditer(line):
            toks.append(Tok(m.lastgroup or "op", m.group(0), lineno))
    return toks


@dataclass
class FieldDecl:
    name: str
    typ: str
    init: Any


@dataclass
class MethodDecl:
    name: str
    params: List[Tuple[str, str]]   # (type, name)
    ret: str
    body: List[Any]


@dataclass
class ClassDecl:
    name: str
    fields: List[FieldDecl] = field(default_factory=list)
    methods: Dict[str, List[MethodDecl]] = field(default_factory=dict)


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

    def at(self, value: str) -> bool:
        t = self.peek()
        return t is not None and t.value == value

    def eat(self, value: str) -> bool:
        if self.at(value):
            self.next()
            return True
        return False

    def expect(self, value: str) -> None:
        if not self.eat(value):
            t = self.peek()
            raise JavaSyntaxError(f"expected {value!r}, got {t.value if t else 'EOF'}")

    # -- declarations ------------------------------------------------------
    def parse_program(self) -> Dict[str, ClassDecl]:
        classes: Dict[str, ClassDecl] = {}
        while self.i < len(self.toks):
            t = self.peek()
            if t.kind == "ident" and t.value in ("import", "package"):
                while self.i < len(self.toks) and not self.eat(";"):
                    self.next()
                continue
            mods = []
            while self.peek() and self.peek().kind == "ident" and self.peek().value in (
                    "public", "private", "protected", "static", "final"):
                mods.append(self.next().value)
            if self.at("class"):
                cls = self.parse_class()
                classes[cls.name] = cls
            else:
                self.next()
        return classes

    def parse_class(self) -> ClassDecl:
        self.expect("class")
        cls = ClassDecl(name=self.next().value)
        self.expect("{")
        while not self.at("}"):
            self.parse_member(cls)
        self.expect("}")
        return cls

    def parse_member(self, cls: ClassDecl) -> None:
        while self.peek() and self.peek().kind == "ident" and self.peek().value in (
                "public", "private", "protected", "static", "final"):
            self.next()
        t = self.peek()
        if t is None:
            raise JavaSyntaxError("unexpected EOF in class body")
        if t.kind == "ident" and t.value in _PRIM_TYPES:
            typ = self.next().value
            name = self.next().value
            if self.at("("):
                self.parse_method(cls, typ, name)
            else:
                init = None
                if self.eat("="):
                    init = self.parse_expr()
                self.expect(";")
                cls.fields.append(FieldDecl(name=name, typ=typ, init=init))
            return
        # unknown member: skip to ';'
        while self.i < len(self.toks) and not self.eat(";"):
            self.next()

    def parse_method(self, cls: ClassDecl, ret: str, name: str) -> None:
        self.expect("(")
        params: List[Tuple[str, str]] = []
        while not self.at(")"):
            ptyp = self.next().value
            pname = self.next().value
            params.append((ptyp, pname))
            self.eat(",")
        self.expect(")")
        if self.at("{"):
            body = self.parse_block()
        else:
            self.expect(";")
            body = []
        cls.methods.setdefault(name, []).append(MethodDecl(name, params, ret, body))

    # -- statements --------------------------------------------------------
    def parse_block(self) -> List[Any]:
        self.expect("{")
        out: List[Any] = []
        while not self.at("}"):
            if self.i >= len(self.toks):
                raise JavaSyntaxError("missing '}'")
            stmt = self.parse_stmt()
            if stmt is not None:
                out.append(stmt)
        self.expect("}")
        return out

    def parse_stmt(self) -> Any:
        t = self.peek()
        if t is None:
            raise JavaSyntaxError("unexpected EOF in statement")
        if t.kind == "op" and t.value == ";":
            self.next()
            return None
        if t.kind == "ident":
            if t.value in ("int", "long", "double", "float", "boolean", "bool", "String", "string"):
                typ = self.next().value
                name = self.next().value
                init = None
                if self.eat("="):
                    init = self.parse_expr()
                self.expect(";")
                return ("local", typ, name, init, t.line)
            if t.value == "if":
                return self.parse_if(t.line)
            if t.value == "while":
                self.next()
                self.expect("(")
                cond = self.parse_expr()
                self.expect(")")
                body = self.parse_block()
                return ("while", cond, body, t.line)
            if t.value == "for":
                return self.parse_for(t.line)
            if t.value == "return":
                self.next()
                val = None
                if not self.at(";"):
                    val = self.parse_expr()
                self.expect(";")
                return ("return", val, t.line)
        # assignment / expression statement
        first = self.parse_expr()
        for op in ("+=", "-=", "*=", "/="):
            if self.at(op):
                self.next()
                rhs = self.parse_expr()
                self.expect(";")
                return ("assign", first, rhs, op[0], t.line)
        if self.at("="):
            self.next()
            rhs = self.parse_expr()
            self.expect(";")
            return ("assign", first, rhs, "", t.line)
        if self.at("++") or self.at("--"):
            op = self.next().value
            self.expect(";")
            return ("inc", first, op, t.line)
        self.expect(";")
        return ("expr", first, t.line)

    def parse_if(self, line: int) -> Any:
        self.expect("if")
        self.expect("(")
        cond = self.parse_expr()
        self.expect(")")
        body = self.parse_block()
        else_body: List[Any] = []
        if self.eat("else"):
            if self.at("if"):
                else_body = [self.parse_if(line)]
            else:
                else_body = self.parse_block()
        return ("if", cond, body, else_body, line)

    def parse_for(self, line: int) -> Any:
        self.expect("for")
        self.expect("(")
        init = None
        if not self.at(";"):
            init = self.parse_stmt()  # consumes its own ';'
        else:
            self.next()
        cond = None
        if not self.at(";"):
            cond = self.parse_expr()
        self.expect(";")
        post = None
        if not self.at(")"):
            # 'i++' style post
            tgt = self.parse_expr()
            if self.at("++") or self.at("--"):
                post = ("inc", tgt, self.next().value, line)
            elif self.at("="):
                self.next()
                post = ("assign", tgt, self.parse_expr(), "", line)
        self.expect(")")
        body = self.parse_block()
        return ("for", init, cond, post, body, line)

    # -- expressions -------------------------------------------------------
    def parse_expr(self) -> Any:
        return self.parse_or()

    def parse_or(self) -> Any:
        node = self.parse_and()
        while self.at("||"):
            self.next()
            node = ("logic", "||", node, self.parse_and())
        return node

    def parse_and(self) -> Any:
        node = self.parse_eq()
        while self.at("&&"):
            self.next()
            node = ("logic", "&&", node, self.parse_eq())
        return node

    def parse_eq(self) -> Any:
        node = self.parse_rel()
        while self.at("==") or self.at("!="):
            op = self.next().value
            node = ("cmp", op, node, self.parse_rel())
        return node

    def parse_rel(self) -> Any:
        node = self.parse_add()
        t = self.peek()
        while t and t.value in ("<", ">", "<=", ">="):
            self.next()
            node = ("cmp", t.value, node, self.parse_add())
            t = self.peek()
        return node

    def parse_add(self) -> Any:
        node = self.parse_mul()
        while self.at("+") or self.at("-"):
            op = self.next().value
            node = ("binop", op, node, self.parse_mul())
        return node

    def parse_mul(self) -> Any:
        node = self.parse_unary()
        while self.at("*") or self.at("/") or self.at("%"):
            op = self.next().value
            node = ("binop", op, node, self.parse_unary())
        return node

    def parse_unary(self) -> Any:
        if self.at("-"):
            self.next()
            return ("neg", self.parse_unary())
        if self.at("!"):
            self.next()
            return ("not", self.parse_unary())
        return self.parse_atom()

    def parse_atom(self) -> Any:
        t = self.peek()
        if t is None:
            raise JavaSyntaxError("unexpected EOF in expression")
        if t.kind == "number":
            self.next()
            return int(t.value)
        if t.kind == "string":
            self.next()
            return ("str", t.value[1:-1].replace('\\"', '"').replace("\\\\", "\\"))
        if t.value == "(":
            self.next()
            e = self.parse_expr()
            self.expect(")")
            return e
        if t.kind == "ident":
            self.next()
            if t.value == "true":
                return True
            if t.value == "false":
                return False
            if t.value == "null":
                return None
            if t.value == "this":
                self.expect(".")
                name = self.next().value
                args = self.parse_args()
                return ("call", name, args)
            if self.at("."):
                # qualified call: ignore the qualifier (single class)
                self.next()
                name = self.next().value
                if self.at("("):
                    args = self.parse_args()
                    return ("call", name, args)
                return ("var", name)
            if self.at("("):
                args = self.parse_args()
                return ("call", t.value, args)
            return ("var", t.value)
        raise JavaSyntaxError(f"unexpected token {t.value!r} at line {t.line}")

    def parse_args(self) -> List[Any]:
        self.expect("(")
        args: List[Any] = []
        while not self.at(")"):
            args.append(self.parse_expr())
            self.eat(",")
        self.expect(")")
        return args


def parse_java(text: str) -> Dict[str, ClassDecl]:
    return _Parser(tokenize_java(text)).parse_program()


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------


class _Interp:
    def __init__(self, cls: ClassDecl, max_steps: int = 2_000_000) -> None:
        self.cls = cls
        self.max_steps = max_steps
        self.steps = 0
        self.trace: List[str] = []
        self.fields: Dict[str, Any] = {}

    def tick(self) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise JavaRuntimeError("interpreter step budget exceeded")

    def init_fields(self) -> None:
        for f in self.cls.fields:
            self.fields[f.name] = self.eval(f.init, {}) if f.init is not None else _default(f.typ)

    def call(self, name: str, args: List[Any]) -> Any:
        overloads = self.cls.methods.get(name)
        if not overloads:
            raise JavaRuntimeError(f"undefined method {name}")
        fn = overloads[0]
        env = {p[1]: v for p, v in zip(fn.params, args)}
        self.trace.append(f"call {name}({', '.join(repr(a) for a in args)})")
        r = self.exec_block(fn.body, env)
        return r[1] if isinstance(r, tuple) and r and r[0] == "ret" else None

    def exec_block(self, block: List[Any], env: Dict[str, Any]) -> Any:
        for stmt in block:
            r = self.exec_stmt(stmt, env)
            if r is not None:
                return r
        return None

    def exec_stmt(self, s: Any, env: Dict[str, Any]) -> Any:
        self.tick()
        kind = s[0]
        if kind == "local":
            env[s[2]] = self.eval(s[3], env) if s[3] is not None else _default(s[1])
        elif kind == "assign":
            target, rhs, bop, line = s[1], s[2], s[3], s[4]
            val = self.eval(rhs, env)
            if bop:
                cur = self.eval(target, env)
                val = _arith(bop, cur, val)
            self.assign(target, val, env)
        elif kind == "inc":
            node, op, line = s[1], s[2], s[3]
            cur = self.eval(node, env)
            self.assign(node, cur + (1 if op == "++" else -1), env)
        elif kind == "if":
            if self.eval(s[1], env):
                return self.exec_block(s[2], env)
            return self.exec_block(s[3], env)
        elif kind == "while":
            while self.eval(s[1], env):
                self.tick()
                r = self.exec_block(s[2], env)
                if r is not None:
                    return r
        elif kind == "for":
            init, cond, post, body, line = s[1], s[2], s[3], s[4], s[5]
            if init is not None:
                self.exec_stmt(init, env)
            while cond is None or self.eval(cond, env):
                self.tick()
                r = self.exec_block(body, env)
                if r is not None:
                    return r
                if post is not None:
                    self.exec_stmt(post, env)
        elif kind == "return":
            return ("ret", self.eval(s[1], env) if s[1] is not None else None)
        elif kind == "expr":
            self.eval(s[1], env)
        return None

    def assign(self, node: Any, val: Any, env: Dict[str, Any]) -> None:
        if isinstance(node, tuple) and node[0] == "var":
            name = node[1]
            if name in env:
                env[name] = val
            elif name in self.fields:
                self.fields[name] = val
            else:
                raise JavaRuntimeError(f"undefined variable {name}")
        else:
            raise JavaRuntimeError(f"cannot assign to {node!r}")

    def eval(self, node: Any, env: Dict[str, Any]) -> Any:
        self.tick()
        if not isinstance(node, tuple):
            return node
        kind = node[0]
        if kind == "str":
            return node[1]
        if kind == "var":
            name = node[1]
            if name in env:
                return env[name]
            if name in self.fields:
                return self.fields[name]
            raise JavaRuntimeError(f"undefined variable {name}")
        if kind == "neg":
            return -_num(self.eval(node[1], env))
        if kind == "not":
            return not self.eval(node[1], env)
        if kind == "binop":
            op = node[1]
            a = self.eval(node[2], env)
            b = self.eval(node[3], env)
            return _arith(op, a, b)
        if kind == "cmp":
            op = node[1]
            a = self.eval(node[2], env)
            b = self.eval(node[3], env)
            if isinstance(a, str) or isinstance(b, str):
                a, b = str(a), str(b)
            else:
                a, b = _num(a), _num(b)
            return {"==": a == b, "!=": a != b, "<": a < b, ">": a > b,
                    "<=": a <= b, ">=": a >= b}[op]
        if kind == "logic":
            if node[1] == "&&":
                return bool(self.eval(node[2], env)) and bool(self.eval(node[3], env))
            return bool(self.eval(node[2], env)) or bool(self.eval(node[3], env))
        if kind == "call":
            args = [self.eval(a, env) for a in node[2]]
            return self.call(node[1], args)
        return node


def _arith(op: str, a: Any, b: Any) -> Any:
    if op == "+" and (isinstance(a, str) or isinstance(b, str)):
        return _jstr(a) + _jstr(b)
    a, b = _num(a), _num(b)
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise JavaRuntimeError("integer divide by zero")
        q = abs(a) // abs(b)
        return q if (a >= 0) == (b >= 0) else -q
    if op == "%":
        if b == 0:
            raise JavaRuntimeError("integer divide by zero")
        r = abs(a) % abs(b)
        return r if a >= 0 else -r
    raise JavaRuntimeError(f"bad operator {op}")


def _num(v: Any) -> int:
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    try:
        return int(str(v).strip())
    except ValueError:
        return 0


def _jstr(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _default(typ: str) -> Any:
    t = typ.lower()
    if t in ("string",):
        return ""
    if t in ("boolean", "bool"):
        return False
    return 0


def run_java(text: str, inputs: Optional[Dict[str, Any]] = None, entry: str = "",
             class_name: str = "", max_steps: int = 2_000_000) -> Dict[str, Any]:
    classes = parse_java(text)
    cls = classes.get(class_name) if class_name else None
    if cls is None and len(classes) == 1:
        cls = next(iter(classes.values()))
    if cls is None:
        raise JavaRuntimeError(f"class {class_name!r} not found")
    interp = _Interp(cls, max_steps)
    interp.init_fields()
    for k, v in (inputs or {}).items():
        interp.fields[k] = v
    method = entry or "compute"
    interp.call(method, [])
    return {"state": dict(interp.fields), "outputs": [],
            "trace": "\n".join(interp.trace[:200]), "steps": interp.steps}
