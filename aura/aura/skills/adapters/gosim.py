"""gosim — a deterministic Go-subset tokenizer/parser/interpreter.

Fallback execution engine for Go code in environments without the Go
toolchain (the adapter prefers ``go run`` when available, e.g. in CI, so
the interpreter is cross-validated against the real compiler).

Supported subset (the one used by the AURA benchmark Go units):

* ``package``/``import`` declarations (imports ignored);
* ``func name(params) (returns) { ... }`` with ``int``/``string``/``bool``
  parameter and result types;
* statements: ``var x T = e``, ``x := e``, ``x = e``, multiple
  assignment from a call, ``if``/``else if``/``else``, 3-clause ``for``
  and condition ``for``, ``return``, ``x++``/``x--``, bare call
  statements, ``//`` comments;
* expressions: integer and string literals, variables, arithmetic
  (integer division truncates toward zero, as in Go), comparisons,
  ``&&``/``||``/``!``, parentheses, user-function calls and the
  builtin casts ``int``/``string``/``bool``.

Every construct above is exercised by ``tests/test_gosim.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class GoSyntaxError(Exception):
    pass


class GoRuntimeError(Exception):
    pass


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(
    r"""(?P<string>"[^"]*") |
        (?P<number>\d+) |
        (?P<ident>[A-Za-z_][A-Za-z0-9_]*) |
        (?P<op>:=|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>=!;,(){}\[\]])""",
    re.X,
)


@dataclass
class Tok:
    kind: str
    value: str
    line: int


def tokenize_go(text: str) -> List[Tok]:
    toks: List[Tok] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = re.sub(r"//.*$", "", raw)
        for m in TOKEN_RE.finditer(line):
            toks.append(Tok(m.lastgroup or "op", m.group(0), lineno))
    return toks


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


@dataclass
class Func:
    name: str
    params: List[str]
    ret_count: int
    body: List[Any]


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
            raise GoSyntaxError(f"expected {value!r}, got {t.value if t else 'EOF'}")

    # -- declarations ------------------------------------------------------
    def parse_program(self) -> Dict[str, Func]:
        funcs: Dict[str, Func] = {}
        while self.i < len(self.toks):
            t = self.peek()
            if t.kind == "ident" and t.value == "package":
                self.next()
                self.next()
                self.eat(";")
            elif t.kind == "ident" and t.value == "import":
                self.next()
                while self.i < len(self.toks) and not self.eat(";"):
                    self.next()
            elif t.kind == "ident" and t.value == "func":
                fn = self.parse_func()
                funcs[fn.name] = fn
            else:
                self.next()
        return funcs

    def parse_func(self) -> Func:
        self.expect("func")
        name = self.next().value
        self.expect("(")
        params: List[str] = []
        while not self.at(")"):
            pname = self.next().value
            self.skip_type()
            params.append(pname)
            self.eat(",")
        self.expect(")")
        ret_count = 1
        if self.at("("):
            self.next()
            ret_count = 0
            while not self.at(")"):
                self.skip_type()
                ret_count += 1
                self.eat(",")
            self.expect(")")
        elif not self.at("{"):
            self.skip_type()
        body = self.parse_block()
        return Func(name=name, params=params, ret_count=ret_count, body=body)

    def skip_type(self) -> None:
        """Consume a type expression (int, string, map[string]X, ...)."""
        depth = 0
        prev = ""
        while self.i < len(self.toks):
            t = self.peek()
            if t.value == "{" and depth == 0 and prev != "interface":
                return
            if t.value in ("[", "{", "("):
                depth += 1
            elif t.value in ("]", "}", ")"):
                if depth == 0:
                    return
                depth -= 1
            elif t.value == "," and depth == 0:
                return
            prev = t.value
            self.next()

    # -- statements --------------------------------------------------------
    def parse_block(self) -> List[Any]:
        self.expect("{")
        out: List[Any] = []
        while not self.at("}"):
            if self.i >= len(self.toks):
                raise GoSyntaxError("missing '}'")
            stmt = self.parse_stmt()
            if stmt is not None:
                out.append(stmt)
            self.eat(";")
        self.expect("}")
        return out

    def parse_stmt(self) -> Any:
        t = self.peek()
        if t is None:
            return None
        if t.kind == "op" and t.value in (";",):
            self.next()
            return None
        if t.kind == "ident":
            v = t.value
            if v == "var":
                self.next()
                name = self.next().value
                self.skip_type()
                init = None
                if self.eat("="):
                    init = self.parse_expr()
                return ("var", name, init, t.line)
            if v == "if":
                return self.parse_if(t.line)
            if v == "for":
                return self.parse_for(t.line)
            if v == "return":
                self.next()
                vals = []
                if not self.at("}") and not self.at(";"):
                    vals.append(self.parse_expr())
                    while self.eat(","):
                        vals.append(self.parse_expr())
                return ("return", vals, t.line)
        # assignment / call / inc-dec
        first = self.parse_expr()
        if self.at(",") and not self.at(")"):
            # multi-target assignment: a, b := f(...)
            targets = [_target_name(first)]
            while self.eat(","):
                targets.append(_target_name(self.parse_expr()))
            if self.at(":=") or self.at("="):
                op = self.next().value
                rhs = self.parse_expr()
                return ("assign", targets, rhs, op == ":=", t.line)
            raise GoSyntaxError(f"unexpected multi-value list (line {t.line})")
        if self.at(":=") or self.at("="):
            op = self.next().value
            if isinstance(first, tuple) and first[0] == "tup":
                targets = [e[1] for e in first[1]]
            elif isinstance(first, tuple) and first[0] == "var":
                targets = [first[1]]
            else:
                targets = [first]
            rhs = self.parse_expr()
            return ("assign", targets, rhs, op == ":=", t.line)
        if self.at("++") or self.at("--"):
            op = self.next().value
            return ("inc", first, op, t.line)
        return ("expr", first, t.line)

    def parse_if(self, line: int) -> Any:
        self.expect("if")
        cond = self.parse_expr()
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
        init = None
        cond = None
        post = None
        if not self.at("{"):
            if self.at(";"):
                self.next()
            else:
                init = self.parse_stmt()
                self.eat(";")
            if not self.at(";") and not self.at("{"):
                cond = self.parse_expr()
            self.eat(";")
            if not self.at("{"):
                post = self.parse_stmt()
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
        node = self.parse_cmp()
        while self.at("&&"):
            self.next()
            node = ("logic", "&&", node, self.parse_cmp())
        return node

    def parse_cmp(self) -> Any:
        node = self.parse_add()
        t = self.peek()
        if t and t.value in ("==", "!=", "<", ">", "<=", ">="):
            self.next()
            node = ("cmp", t.value, node, self.parse_add())
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
            raise GoSyntaxError("unexpected EOF in expression")
        if t.kind == "number":
            self.next()
            return int(t.value)
        if t.kind == "string":
            self.next()
            return t.value[1:-1]
        if t.value == "(":
            self.next()
            e = self.parse_expr()
            items = [e]
            while self.eat(","):
                items.append(self.parse_expr())
            self.expect(")")
            return ("tup", items) if len(items) > 1 else e
        if t.kind == "ident":
            self.next()
            if t.value == "true":
                return True
            if t.value == "false":
                return False
            if self.at("("):
                self.next()
                args = []
                while not self.at(")"):
                    args.append(self.parse_expr())
                    self.eat(",")
                self.expect(")")
                return ("call", t.value, args)
            return ("var", t.value)
        raise GoSyntaxError(f"unexpected token {t.value!r} at line {t.line}")


def parse_go(text: str) -> Dict[str, Func]:
    return _Parser(tokenize_go(text)).parse_program()


def _target_name(node: Any) -> str:
    if isinstance(node, tuple) and node and node[0] == "var":
        return node[1]
    raise GoSyntaxError(f"invalid assignment target {node!r}")


# ---------------------------------------------------------------------------
# Interpreter
# ---------------------------------------------------------------------------


class _Interp:
    def __init__(self, funcs: Dict[str, Func], max_steps: int = 2_000_000) -> None:
        self.funcs = funcs
        self.max_steps = max_steps
        self.steps = 0
        self.trace: List[str] = []

    def tick(self) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise GoRuntimeError("interpreter step budget exceeded")

    def call(self, name: str, args: List[Any]) -> Any:
        if name in ("int", "float64"):
            v = args[0]
            try:
                return int(float(v))
            except (TypeError, ValueError):
                return 0
        if name == "string":
            v = args[0]
            return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
        if name == "bool":
            return bool(args[0])
        fn = self.funcs.get(name)
        if fn is None:
            raise GoRuntimeError(f"undefined function {name}")
        if len(args) != len(fn.params):
            raise GoRuntimeError(f"{name}: expected {len(fn.params)} args, got {len(args)}")
        env: Dict[str, Any] = dict(zip(fn.params, args))
        self.trace.append(f"call {name}({', '.join(repr(a) for a in args)})")
        result = self.exec_block(fn.body, env, fn.name)
        if isinstance(result, tuple) and result and result[0] == "ret":
            vals = result[1]
        else:
            vals = []
        if fn.ret_count <= 1:
            return vals[0] if vals else None
        return tuple(vals)

    def exec_block(self, block: List[Any], env: Dict[str, Any], fname: str) -> Any:
        for stmt in block:
            r = self.exec_stmt(stmt, env, fname)
            if r is not None:
                return r
        return None

    def exec_stmt(self, s: Any, env: Dict[str, Any], fname: str) -> Any:
        self.tick()
        kind = s[0]
        if kind == "var":
            env[s[1]] = self.eval(s[2], env) if s[2] is not None else 0
        elif kind == "assign":
            targets, rhs, declare, line = s[1], s[2], s[3], s[4]
            val = self.eval(rhs, env)
            if len(targets) == 1:
                env[targets[0]] = val
            else:
                if not (isinstance(val, tuple)):
                    raise GoRuntimeError(f"multiple assignment needs multiple values (line {line})")
                for t, v in zip(targets, val):
                    env[t] = v
        elif kind == "inc":
            node, op, line = s[1], s[2], s[3]
            name = node[1] if isinstance(node, tuple) else None
            if name is None:
                raise GoRuntimeError(f"cannot increment (line {line})")
            env[name] = env.get(name, 0) + (1 if op == "++" else -1)
        elif kind == "if":
            if self.eval(s[1], env):
                return self.exec_block(s[2], env, fname)
            return self.exec_block(s[3], env, fname)
        elif kind == "for":
            init, cond, post, body, line = s[1], s[2], s[3], s[4], s[5]
            if init is not None:
                self.exec_stmt(init, env, fname)
            while cond is None or self.eval(cond, env):
                self.tick()
                r = self.exec_block(body, env, fname)
                if r is not None:
                    return r
                if post is not None:
                    self.exec_stmt(post, env, fname)
        elif kind == "return":
            return ("ret", [self.eval(v, env) for v in s[1]])
        elif kind == "expr":
            self.eval(s[1], env)
        return None

    def eval(self, node: Any, env: Dict[str, Any]) -> Any:
        self.tick()
        if not isinstance(node, tuple):
            return node
        kind = node[0]
        if kind == "var":
            name = node[1]
            if name not in env:
                raise GoRuntimeError(f"undefined variable {name}")
            return env[name]
        if kind == "neg":
            return -_num(self.eval(node[1], env))
        if kind == "not":
            return not self.eval(node[1], env)
        if kind == "binop":
            op = node[1]
            a = self.eval(node[2], env)
            b = self.eval(node[3], env)
            if op == "+" and isinstance(a, str):
                return a + str(b)
            a, b = _num(a), _num(b)
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if b == 0:
                    raise GoRuntimeError("integer divide by zero")
                q = abs(a) // abs(b)
                return q if (a >= 0) == (b >= 0) else -q
            if op == "%":
                if b == 0:
                    raise GoRuntimeError("integer divide by zero")
                r = abs(a) % abs(b)
                return r if a >= 0 else -r
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
            val = self.call(node[1], args)
            return val
        if kind == "tup":
            return tuple(self.eval(e, env) for e in node[1])
        return node


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


def run_go(text: str, inputs: Optional[Dict[str, Any]] = None, entry: str = "",
           max_steps: int = 2_000_000) -> Dict[str, Any]:
    funcs = parse_go(text)
    fn = funcs.get(entry) if entry else None
    if fn is None and len(funcs) == 1:
        fn = next(iter(funcs.values()))
    if fn is None:
        raise GoRuntimeError(f"entry function {entry!r} not found")
    interp = _Interp(funcs, max_steps)
    inputs = inputs or {}
    args = [_coerce_in(inputs.get(p, 0)) for p in fn.params]
    val = interp.call(fn.name, args)
    if fn.ret_count <= 1:
        out = {"result": val}
    else:
        out = {f"ret{i}": v for i, v in enumerate(val)}
    return {"state": out, "outputs": [], "trace": "\n".join(interp.trace[:200]), "steps": interp.steps}


def _coerce_in(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return int(v) if float(v).is_integer() else v
    return v
