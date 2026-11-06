"""Python execution adapter (used for modernized code and Python units)."""

from __future__ import annotations

import importlib.util
import os
import sys
from typing import Any, Dict

from .base import ExecResult, ExecutionAdapter, Harness


class PythonAdapter(ExecutionAdapter):
    name = "python"
    languages = ("python",)

    def available(self) -> bool:
        return True

    def run(self, root: str, harness: Harness, inputs: Dict[str, Any]) -> ExecResult:
        path = os.path.join(root, harness.entry_file)
        spec = importlib.util.spec_from_file_location("aura_unit", path)
        if spec is None or spec.loader is None:
            return ExecResult(ok=False, fault=f"cannot import {path}")
        mod = importlib.util.module_from_spec(spec)
        old_path = list(sys.path)
        try:
            sys.path.insert(0, os.path.dirname(path))
            spec.loader.exec_module(mod)
        except Exception as exc:  # noqa: BLE001
            return ExecResult(ok=False, fault=f"import error: {type(exc).__name__}: {exc}")
        finally:
            sys.path[:] = old_path
        fn = getattr(mod, harness.entry_symbol or "run", None)
        if not callable(fn):
            return ExecResult(ok=False, fault=f"entry {harness.entry_symbol!r} not found")
        try:
            out = fn(dict(inputs))
        except Exception as exc:  # noqa: BLE001
            return ExecResult(ok=False, fault=f"{type(exc).__name__}: {exc}")
        if not isinstance(out, dict):
            out = {"result": out}
        fields = harness.state_fields or list(out)
        return ExecResult(
            ok=True,
            state={f: out.get(f, inputs.get(f)) for f in fields},
            outputs=[str(v) for v in out.get("_outputs", [])] if isinstance(out.get("_outputs"), list) else [],
            trace=f"run({inputs!r}) -> {str(out)[:2000]}",
        )
