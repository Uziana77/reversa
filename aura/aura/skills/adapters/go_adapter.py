"""Go execution adapter — uses the real ``go`` toolchain when present.

In environments without Go (the offline sandbox), the adapter reports
``unresolved: no Go toolchain in sandbox`` — exactly the behaviour the
synopsis prescribes for code with no safe execution path; those rules keep
static-only confidence states instead of execution labels.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any, Dict

from ..sandbox import run_subprocess
from .base import ExecResult, ExecutionAdapter, Harness


class GoAdapter(ExecutionAdapter):
    name = "go"
    languages = ("go",)

    def available(self) -> bool:
        return shutil.which("go") is not None

    def run(self, root: str, harness: Harness, inputs: Dict[str, Any]) -> ExecResult:
        if not self.available():
            return ExecResult(ok=False, fault="unresolved: no Go toolchain in sandbox")
        workdir = tempfile.mkdtemp(prefix="aura-go-")
        src_dir = os.path.join(root, os.path.dirname(harness.entry_file) or ".")
        for fn in os.listdir(src_dir):
            if fn.endswith(".go"):
                shutil.copy(os.path.join(src_dir, fn), workdir)
        entry = harness.entry_symbol or "Run"
        params = ", ".join(f"{n}: {go_type(t)}" for n, t in (harness.input_fields or {}).items())
        assigns = "\n".join(
            f"\t{n}: cast_{n}(inputs[{json.dumps(n)}])," for n in (harness.input_fields or {})
        )
        decls = "\n".join(
            f"func cast_{n}(v interface{{}}) {go_type(t)} {{\n"
            f"\tswitch x := v.(type) {{\n"
            f"\tcase int: return {go_type(t)}(x)\n"
            f"\tcase float64: return {go_type(t)}(x)\n"
            f"\tcase string: {{ var out {go_type(t)}; fmt.Sscanf(x, \"%v\", &out); return out }}\n"
            f"\t}}\n\treturn 0\n}}"
            for n, t in (harness.input_fields or {}).items()
        )
        main_go = f"""package main

import (
\t"encoding/json"
\t"fmt"
\t"os"
)

{decls}

func main() {{
\tvar inputs map[string]interface{{}}
\tjson.Unmarshal([]byte(os.Getenv("AURA_INPUT")), &inputs)
\tstate := {entry}({params})
\tfor _, f := range []string{{ {", ".join(json.dumps(f) for f in (harness.state_fields or []))} }} {{
\t\tv := state[f]
\t\tb, _ := json.Marshal(v)
\t\tfmt.Printf("AURA_STATE %s=%s\\n", f, string(b))
\t}}
}}
"""
        # the entry must accept explicit params and return map[string]interface{}
        with open(os.path.join(workdir, "aura_driver_main.go"), "w", encoding="utf-8") as fh:
            fh.write(main_go)
        env = {"AURA_INPUT": json.dumps(inputs), "GO111MODULE": "off"}
        res = run_subprocess(["go", "run", "."], cwd=workdir,
                             timeout_s=max(self.timeout_s, 30), memory_mb=max(self.memory_mb, 512),
                             env_extra=env)
        if not res.ok:
            return res
        state: Dict[str, Any] = {}
        outputs = []
        for line in res.raw_stdout.splitlines():
            if line.startswith("AURA_STATE "):
                k, _, v = line[len("AURA_STATE "):].partition("=")
                try:
                    state[k] = json.loads(v)
                except Exception:
                    state[k] = v
            elif line.strip():
                outputs.append(line)
        res.state = state
        res.outputs = outputs
        return res


def go_type(t: str) -> str:
    return {
        "int": "int", "long": "int64", "float": "float64", "double": "float64",
        "string": "string", "str": "string", "bool": "bool", "boolean": "bool",
    }.get(str(t).lower(), "float64")
