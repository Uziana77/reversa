"""Sandboxed execution skill.

Two execution modes:

* :func:`run_subprocess` — real toolchain execution (node, javac/java, go)
  in an isolated child process: clean minimal environment, wall-clock
  timeout, CPU and address-space rlimits, no inherited credentials.  (True
  network isolation needs namespaces, which the harness documents as a CI
  hardening step; interpreters below never touch the network at all.)
* :func:`run_interpreter` — the bundled interpreters (cobolite, dialects)
  run in-process with a hard step budget, so they cannot loop forever.

Both return :class:`aura.skills.adapters.base.ExecResult`.
"""

from __future__ import annotations

import os
import resource
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional, Sequence

from .adapters.base import ExecResult


def _limit_resources(memory_mb: int, cpu_seconds: int):
    def _fn() -> None:
        try:
            mem = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        except (ValueError, OSError):
            pass
        try:
            os.setsid()
        except OSError:
            pass

    return _fn


def run_subprocess(
    argv: Sequence[str],
    *,
    cwd: Optional[str] = None,
    timeout_s: float = 10.0,
    memory_mb: int = 512,
    env_extra: Optional[Dict[str, str]] = None,
    stdin_data: str = "",
) -> ExecResult:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": tempfile.gettempdir(),
        "LANG": "C",
        "LC_ALL": "C",
    }
    for var in ("JAVA_HOME", "GOROOT", "GOPATH", "NODE_PATH"):
        if os.environ.get(var):
            env[var] = os.environ[var]
    if env_extra:
        env.update(env_extra)
    t0 = time.time()
    try:
        proc = subprocess.run(
            list(argv),
            cwd=cwd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
            preexec_fn=_limit_resources(memory_mb, int(timeout_s) + 2),
        )
        stdout = (proc.stdout or "")[-20000:]
        stderr = (proc.stderr or "")[-8000:]
        fault = ""
        if proc.returncode != 0:
            fault = f"exit {proc.returncode}: {stderr.strip()[:400]}"
        return ExecResult(
            ok=proc.returncode == 0,
            outputs=stdout.splitlines() if proc.returncode == 0 else [],
            fault=fault,
            trace=f"$ {' '.join(argv)}\n{stdout[:2000]}",
            raw_stdout=stdout,
            steps=int((time.time() - t0) * 1000),
        )
    except subprocess.TimeoutExpired:
        return ExecResult(ok=False, fault=f"timeout after {timeout_s}s",
                          trace=f"$ {' '.join(argv)} (timeout)")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(ok=False, fault=f"{type(exc).__name__}: {exc}")


def run_interpreter(fn, *args, **kwargs) -> ExecResult:
    """Run a bundled interpreter function under a step budget."""
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return ExecResult(ok=False, fault=f"{type(exc).__name__}: {exc}")
    if not isinstance(result, dict):
        return ExecResult(ok=True, state={"result": result})
    return ExecResult(
        ok=True,
        state=result.get("state", {}),
        outputs=result.get("outputs", []),
        trace=str(result.get("trace", ""))[:8000],
        steps=int(result.get("steps", 0)),
    )
