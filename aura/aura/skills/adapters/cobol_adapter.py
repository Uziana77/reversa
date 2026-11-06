"""COBOL execution adapter: GnuCOBOL when present, bundled cobolite otherwise."""

from __future__ import annotations

import os
import shutil
from typing import Any, Dict

from ..sandbox import run_interpreter
from .base import ExecResult, ExecutionAdapter, Harness
from .cobolite import Interpreter, norm_state, parse_cobol


class CobolAdapter(ExecutionAdapter):
    name = "cobol"
    languages = ("cobol", "cobol-copybook")

    def available(self) -> bool:
        return True   # cobolite is bundled; cobc is a bonus

    def has_toolchain(self) -> bool:
        return shutil.which("cobc") is not None

    def run(self, root: str, harness: Harness, inputs: Dict[str, Any]) -> ExecResult:
        path = os.path.join(root, harness.entry_file)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            return ExecResult(ok=False, fault=f"cannot read {path}: {exc}")
        prog = parse_cobol(text)
        coerced = {}
        for name, typ in (harness.input_fields or {}).items():
            if name in inputs:
                coerced[name] = self.coerce(inputs[name], typ)
        for name, val in inputs.items():
            coerced.setdefault(name, val)
        interp = Interpreter(prog, coerced, max_steps=self.max_steps)
        res = run_interpreter(interp.run, harness.entry_symbol or None)
        if not res.ok:
            return res
        full_state = norm_state(res.state)
        fields = harness.state_fields or list(full_state)
        res.state = {f: full_state.get(f) for f in fields if f in full_state}
        # keep the full state visible in the trace for auditability
        res.trace += "\nFULL_STATE " + repr(full_state)[:2000]
        return res
