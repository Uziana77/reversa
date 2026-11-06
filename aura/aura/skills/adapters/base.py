"""Execution adapters — one per language family.

An adapter runs legacy code with synthesised inputs inside the sandbox and
returns a structured result (final state, outputs, faults, trace).  The
Dynamic Evidence Agent and the Equivalence Validator both use this
interface; expected outputs are always produced by *executing the original
code*, never by asking the LLM (synopsis 6.9: "neither is an LLM opinion").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecResult:
    ok: bool
    state: Dict[str, Any] = field(default_factory=dict)   # final named state
    outputs: List[str] = field(default_factory=list)       # displayed/logged output lines
    fault: str = ""                                        # signalled fault (exception, abend)
    trace: str = ""                                        # compact execution trace
    raw_stdout: str = ""
    steps: int = 0

    def comparable(self) -> dict:
        """The part of the result compared by differential tests."""
        return {"state": self.state, "outputs": self.outputs, "fault": self.fault}

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "state": self.state,
            "outputs": self.outputs,
            "fault": self.fault,
            "trace": self.trace,
            "steps": self.steps,
        }


@dataclass
class Harness:
    """How to drive one bench unit as a black box (its 'test suite' surface).

    ``state_fields``: names readable after execution (WORKING-STORAGE fields,
    returned map keys, module exports...).  ``input_fields``: names set
    before execution.  ``entry``: symbol to invoke where applicable.
    """

    language: str
    entry_file: str = ""
    entry_symbol: str = ""
    input_fields: Dict[str, str] = field(default_factory=dict)   # name -> type
    state_fields: List[str] = field(default_factory=list)
    entry_kind: str = "program"        # program | function | method
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Harness":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


class ExecutionAdapter:
    """Interface every adapter implements."""

    name = "base"
    languages: tuple = ()

    def __init__(self, timeout_s: float = 10.0, memory_mb: int = 512, max_steps: int = 2_000_000) -> None:
        self.timeout_s = timeout_s
        self.memory_mb = memory_mb
        self.max_steps = max_steps

    def available(self) -> bool:
        """Whether this adapter can execute in the current environment."""
        return True

    def run(self, root: str, harness: Harness, inputs: Dict[str, Any]) -> ExecResult:
        raise NotImplementedError

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def coerce(value: Any, type_name: str) -> Any:
        t = (type_name or "any").lower()
        try:
            if t in ("int", "long", "number", "numeric", "int9"):
                return int(float(value))
            if t in ("float", "double", "decimal"):
                return float(value)
            if t in ("str", "string", "text", "x"):
                return str(value)
            if t in ("bool", "boolean", "flag"):
                if isinstance(value, str):
                    return value.strip().lower() in ("1", "true", "yes", "on")
                return bool(value)
        except (TypeError, ValueError):
            return value
        return value
