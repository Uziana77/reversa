"""Go execution adapter.

Execution order:

1. real toolchain: ``go run`` on the unit sources plus a generated driver
   ``aura_driver_main.go`` (used in CI, where golang-go is installed —
   this cross-validates the bundled interpreter against gc);
2. bundled interpreter: :mod:`aura.skills.adapters.gosim`, a Go-subset
   engine used when no toolchain is available (e.g. in the offline
   research sandbox).  ``available()`` is therefore always True.

Harness convention (bench/README.md): the entry function takes one typed
parameter per ``input_fields`` entry (in order) and returns one value per
``state_fields`` entry (multi-return, in order), e.g.::

    // input_fields: stock:int, demand:int
    // state_fields: final_stock, status
    func runBatch(stock int, demand int) (int, string) { ... }
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from typing import Any, Dict, List

from ..sandbox import run_subprocess
from .base import ExecResult, ExecutionAdapter, Harness

_JSON_LINE = re.compile(r"AURA_STATE (\w+)=(.*)")


def go_type(t: str) -> str:
    return {
        "int": "int", "long": "int64", "float": "float64", "double": "float64",
        "string": "string", "str": "string", "bool": "bool", "boolean": "bool",
    }.get(str(t).lower(), "float64")


def _cast_fn(name: str, typ: str) -> str:
    gt = go_type(typ)
    if gt == "int" or gt == "int64":
        body = (
            f"func cast_{name}(v interface{{}}) {gt} {{\n"
            f"\tswitch x := v.(type) {{\n"
            f"\tcase int: return {gt}(x)\n"
            f"\tcase float64: return {gt}(x)\n"
            f"\tcase string: {{ var out {gt}; fmt.Sscanf(x, \"%v\", &out); return out }}\n"
            f"\t}}\n\treturn 0\n}}"
        )
    elif gt == "bool":
        body = (
            f"func cast_{name}(v interface{{}}) bool {{\n"
            f"\tswitch x := v.(type) {{\n"
            f"\tcase bool: return x\n"
            f"\tcase float64: return x != 0\n"
            f"\tcase string: return x == \"true\" || x == \"1\"\n"
            f"\t}}\n\treturn false\n}}"
        )
    else:
        body = (
            f"func cast_{name}(v interface{{}}) string {{\n"
            f"\treturn fmt.Sprintf(\"%v\", v)\n}}"
        )
    return body


def _driver_source(h: Harness) -> str:
    names = list(h.state_fields or [])
    params = ", ".join(f"cast_{n}(inputs[{json.dumps(n)}])" for n in (h.input_fields or {}))
    decls = "\n".join(_cast_fn(n, t) for n, t in (h.input_fields or {}).items())
    if len(names) == 1:
        assign = f"\tr0 := {h.entry_symbol or 'Run'}({params})"
    else:
        assign = f"\t{', '.join(f'r{i}' for i in range(len(names)))} := {h.entry_symbol or 'Run'}({params})"
    prints = "\n".join(
        f'\tb, _ = json.Marshal(r{i})\n\tfmt.Printf("AURA_STATE {n}=%s\\n", string(b))'
        for i, n in enumerate(names)
    )
    return f"""package main

import (
\t"encoding/json"
\t"fmt"
\t"os"
)

{decls}

func main() {{
\tvar inputs map[string]interface{{}}
\tjson.Unmarshal([]byte(os.Getenv("AURA_INPUT")), &inputs)
{assign}
\tvar b []byte
{prints}
}}
"""


class GoAdapter(ExecutionAdapter):
    name = "go"
    languages = ("go",)

    def available(self) -> bool:
        # the bundled subset interpreter always provides an execution path
        return True

    # ------------------------------------------------------------------
    def run(self, root: str, harness: Harness, inputs: Dict[str, Any]) -> ExecResult:
        names = list(harness.state_fields or [])
        toolchain = shutil.which("go")

        if toolchain:
            res = self._run_toolchain(root, harness, inputs, toolchain, names)
            if res is not None and (res.ok or not res.fault.startswith("unresolved")):
                return res

        return self._run_gosim(root, harness, inputs, names)

    # ------------------------------------------------------------------
    def _run_toolchain(self, root: str, harness: Harness, inputs: Dict[str, Any],
                       go_bin: str, names: List[str]) -> ExecResult:
        try:
            workdir = tempfile.mkdtemp(prefix="aura-go-")
            src_dir = os.path.join(root, os.path.dirname(harness.entry_file) or ".")
            for fn in os.listdir(src_dir):
                if fn.endswith(".go") and fn != "aura_driver_main.go":
                    shutil.copy(os.path.join(src_dir, fn), workdir)
            with open(os.path.join(workdir, "aura_driver_main.go"), "w", encoding="utf-8") as fh:
                fh.write(_driver_source(harness))
            env = {"AURA_INPUT": json.dumps(inputs), "GO111MODULE": "off"}
            res = run_subprocess([go_bin, "run", "."], cwd=workdir,
                                 timeout_s=max(self.timeout_s, 60),
                                 memory_mb=max(self.memory_mb, 512), env_extra=env)
            if not res.ok:
                return res
            state: Dict[str, Any] = {}
            outputs = []
            for line in res.raw_stdout.splitlines():
                m = _JSON_LINE.match(line)
                if m:
                    try:
                        state[m.group(1)] = json.loads(m.group(2))
                    except Exception:
                        state[m.group(1)] = m.group(2)
                elif line.strip():
                    outputs.append(line)
            res.state = {n: state.get(n) for n in names} if names else state
            res.outputs = outputs
            return res
        except Exception as exc:  # toolchain unusable -> interpreter
            return ExecResult(ok=False, fault=f"unresolved: go toolchain failed: {exc}")

    # ------------------------------------------------------------------
    def _run_gosim(self, root: str, harness: Harness, inputs: Dict[str, Any],
                   names: List[str]) -> ExecResult:
        try:
            from .gosim import run_go
            path = os.path.join(root, harness.entry_file or "")
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            result = run_go(text, inputs, entry=harness.entry_symbol or "")
            raw = result.get("state", {})
            if names:
                vals = [raw.get(f"ret{i}", raw.get("result")) for i in range(len(names))]
                state = {n: v for n, v in zip(names, vals)}
            else:
                state = raw
            return ExecResult(ok=True, state=state, outputs=[], fault="",
                              trace=result.get("trace", ""), steps=result.get("steps", 0))
        except Exception as exc:  # noqa: BLE001
            return ExecResult(ok=False, fault=f"gosim: {type(exc).__name__}: {exc}")
