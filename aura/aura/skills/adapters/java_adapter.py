"""Java execution adapter.

Compiles and runs the legacy Java unit through the first available
toolchain: ``javac``/``java`` on PATH, a ``JAVA_HOME``, or the JDK bundled
in the optional ``jdk4py`` package (compiled via the ``jdk.compiler``
module, so no ``javac`` launcher is required).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional

from ..sandbox import run_subprocess
from .base import ExecResult, ExecutionAdapter, Harness

JAVA_TYPES = {
    "int": ("int", "%d"),
    "long": ("long", "%d"),
    "double": ("double", "%s"),
    "float": ("double", "%s"),
    "boolean": ("boolean", "%s"),
    "string": ("String", "%s"),
    "str": ("String", "%s"),
}


class JavaAdapter(ExecutionAdapter):
    name = "java"
    languages = ("java",)

    def _toolchain(self) -> Optional[dict]:
        if shutil.which("javac") and shutil.which("java"):
            return {"kind": "path"}
        jh = os.environ.get("JAVA_HOME")
        if jh and os.path.exists(os.path.join(jh, "bin", "java")):
            return {"kind": "home", "home": jh}
        try:
            import jdk4py  # type: ignore

            home = str(jdk4py.JAVA_HOME)
            if os.path.exists(os.path.join(home, "bin", "java")):
                return {"kind": "jdk4py", "home": home}
        except Exception:
            pass
        return None

    def available(self) -> bool:
        return self._toolchain() is not None

    # ------------------------------------------------------------------
    def run(self, root: str, harness: Harness, inputs: Dict[str, Any]) -> ExecResult:
        tc = self._toolchain()
        if tc is None:
            return ExecResult(ok=False, fault="unresolved: no Java toolchain in sandbox")
        src_dir = os.path.join(root, os.path.dirname(harness.entry_file) or ".")
        driver = self._driver(harness, inputs)
        workdir = tempfile.mkdtemp(prefix="aura-java-")
        # copy sources
        for fn in os.listdir(src_dir):
            if fn.endswith(".java"):
                shutil.copy(os.path.join(src_dir, fn), workdir)
        with open(os.path.join(workdir, "AuraDriver.java"), "w", encoding="utf-8") as fh:
            fh.write(driver)

        files = [f for f in sorted(os.listdir(workdir)) if f.endswith(".java")]
        if tc["kind"] == "path":
            compile_cmd = ["javac", "-nowarn", "-d", workdir] + files
            run_cmd = ["java", "-cp", workdir, "AuraDriver"]
        else:
            home = tc["home"]
            java = os.path.join(home, "bin", "java")
            compile_cmd = [java, "-m", "jdk.compiler/com.sun.tools.javac.Main", "-nowarn", "-d", workdir] + files
            run_cmd = [java, "-cp", workdir, "AuraDriver"]

        cres = run_subprocess(compile_cmd, cwd=workdir, timeout_s=self.timeout_s * 3,
                              memory_mb=self.memory_mb)
        if not cres.ok:
            return ExecResult(ok=False, fault=f"javac failed: {cres.fault}")
        rres = run_subprocess(run_cmd, cwd=workdir, timeout_s=self.timeout_s,
                              memory_mb=self.memory_mb)
        if not rres.ok:
            return rres
        return self._parse_state(rres)

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_state(res: ExecResult) -> ExecResult:
        state: Dict[str, Any] = {}
        outputs: List[str] = []
        for line in res.raw_stdout.splitlines():
            if line.startswith("AURA_STATE "):
                k, _, v = line[len("AURA_STATE "):].partition("=")
                try:
                    import json

                    state[k] = json.loads(v)
                except Exception:
                    state[k] = v
            elif line.strip():
                outputs.append(line)
        res.state = state
        res.outputs = outputs
        return res

    # ------------------------------------------------------------------
    @staticmethod
    def _driver(harness: Harness, inputs: Dict[str, Any]) -> str:
        cls = os.path.basename(harness.entry_file).replace(".java", "")
        if harness.extra.get("class"):
            cls = harness.extra["class"]
        entry = harness.entry_symbol or "compute"
        lines = [
            "import java.util.*;",
            "public class AuraDriver {",
            "  public static void main(String[] args) throws Exception {",
            f"    {cls} obj = new {cls}();",
        ]
        for name, typ in (harness.input_fields or {}).items():
            if name not in inputs:
                continue
            val = inputs[name]
            jt = JAVA_TYPES.get(str(typ).lower(), ("String", "%s"))[0]
            if jt == "String":
                lit = '"' + str(val).replace('"', '\\"') + '"'
            elif jt == "boolean":
                lit = "true" if val in (True, "true", "True", 1, "1", "yes", "on") else "false"
            elif jt in ("int", "long"):
                lit = str(int(float(val)))
            else:
                lit = str(float(val))
            lines.append(f"    obj.{name} = {lit};")
        lines.append(f"    obj.{entry}();")
        for name in harness.state_fields or []:
            lines.append(f'    System.out.println("AURA_STATE {name}=" + toJson(obj.{name}));')
        lines += [
            "  }",
            "  static String toJson(Object o) {",
            '    if (o == null) return "null";',
            '    if (o instanceof String) return "\\"" + ((String)o).replace("\\"", "\\\\\\"") + "\\"";',
            '    return String.valueOf(o);',
            "  }",
            "}",
        ]
        return "\n".join(lines)
