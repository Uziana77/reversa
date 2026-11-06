"""Adapter for the two invented legacy dialects (ILG, RPT)."""

from __future__ import annotations

import os
from typing import Any, Dict

from ..sandbox import run_interpreter
from .base import ExecResult, ExecutionAdapter, Harness
from .dsl_interp import run_dialect


class DialectAdapter(ExecutionAdapter):
    name = "dialect"
    languages = ("interlock", "reportscript", "ilg", "rpt")

    def available(self) -> bool:
        return True  # bundled interpreters

    def run(self, root: str, harness: Harness, inputs: Dict[str, Any]) -> ExecResult:
        path = os.path.join(root, harness.entry_file)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            return ExecResult(ok=False, fault=f"cannot read {path}: {exc}")
        coerced = {}
        for name, typ in (harness.input_fields or {}).items():
            if name in inputs:
                coerced[name] = self.coerce(inputs[name], typ)
        for name, val in inputs.items():
            coerced.setdefault(name, val)
        res = run_interpreter(
            run_dialect, harness.language, text, coerced,
            harness.entry_symbol or None, self.max_steps,
        )
        if not res.ok:
            return res
        fields = harness.state_fields or list(res.state)
        res.state = {f: res.state.get(f) for f in fields if f in res.state}
        return res
