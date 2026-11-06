"""Node.js execution adapter (JavaScript / legacy React logic modules).

Real ``node`` execution of the unit's CommonJS modules.  JSX components are
transpiled with ``esbuild`` when available (npm); otherwise component files
are covered by static analysis only and their logic modules carry the
dynamic evidence.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any, Dict

from ..sandbox import run_subprocess
from .base import ExecResult, ExecutionAdapter, Harness

DRIVER = """\
const path = require('path');
const inputs = JSON.parse(process.env.AURA_INPUT || '{}');
const entryFile = process.env.AURA_ENTRY_FILE;
const entrySymbol = process.env.AURA_ENTRY_SYMBOL;
const stateFields = JSON.parse(process.env.AURA_STATE_FIELDS || '[]');
let mod;
try { mod = require(path.resolve(entryFile)); }
catch (e) {
  if (e && e.code === 'ERR_REQUIRE_ESM') {
    import(path.resolve(entryFile)).then(m => run(m)).catch(err => { console.error(err); process.exit(2); });
  } else { console.error(e); process.exit(2); }
}
if (mod) run(mod);
function run(mod) {
  const fn = (mod && (mod[entrySymbol] || (mod.default && mod.default[entrySymbol]))) || null;
  if (typeof fn !== 'function') { console.error('entry not found: ' + entrySymbol); process.exit(3); }
  Promise.resolve(fn(inputs)).then((out) => {
    out = out || {};
    for (const f of stateFields) {
      const v = (f in out) ? out[f] : inputs[f];
      process.stdout.write('AURA_STATE ' + f + '=' + JSON.stringify(v === undefined ? null : v) + '\\n');
    }
  }).catch(err => { console.error('AURA_FAULT ' + (err && err.message ? err.message : err)); process.exit(4); });
}
"""


class NodeAdapter(ExecutionAdapter):
    name = "node"
    languages = ("javascript", "javascript-react", "typescript", "typescript-react")

    def available(self) -> bool:
        return shutil.which("node") is not None

    def run(self, root: str, harness: Harness, inputs: Dict[str, Any]) -> ExecResult:
        entry = harness.entry_file
        if entry.endswith((".jsx", ".tsx")):
            transpiled = self._transpile(root, entry)
            if transpiled is None:
                return ExecResult(ok=False, fault="unresolved: JSX entry needs esbuild transpiler")
            entry = transpiled
        workdir = tempfile.mkdtemp(prefix="aura-node-")
        with open(os.path.join(workdir, "driver.js"), "w", encoding="utf-8") as fh:
            fh.write(DRIVER)
        env = {
            "AURA_INPUT": json.dumps(inputs),
            "AURA_ENTRY_FILE": os.path.abspath(os.path.join(root, entry)),
            "AURA_ENTRY_SYMBOL": harness.entry_symbol or "run",
            "AURA_STATE_FIELDS": json.dumps(harness.state_fields or []),
            "NODE_PATH": os.path.join(root, "node_modules"),
            # bound the real JS heap; the address-space rlimit must stay
            # generous because V8 reserves large virtual regions up front
            "NODE_OPTIONS": "--max-old-space-size=384",
        }
        res = run_subprocess(["node", "driver.js"], cwd=workdir,
                             timeout_s=self.timeout_s,
                             memory_mb=max(self.memory_mb, 8192),
                             env_extra=env)
        if not res.ok:
            return res
        return self._parse_state(res)

    @staticmethod
    def _parse_state(res: ExecResult) -> ExecResult:
        state: Dict[str, Any] = {}
        outputs = []
        for line in res.raw_stdout.splitlines():
            if line.startswith("AURA_STATE "):
                k, _, v = line[len("AURA_STATE "):].partition("=")
                try:
                    state[k] = json.loads(v)
                except Exception:
                    state[k] = v
            elif line.startswith("AURA_FAULT "):
                res.ok = False
                res.fault = line[len("AURA_FAULT "):]
            elif line.strip():
                outputs.append(line)
        res.state = state
        res.outputs = outputs
        return res

    @staticmethod
    def _transpile(root: str, entry: str) -> str | None:
        """Transpile a JSX/TSX entry to CommonJS with esbuild, if available."""
        if shutil.which("esbuild") is None:
            # try npx from the bench tooling directory
            if shutil.which("npx") is None:
                return None
            cmd_prefix = ["npx", "--yes", "esbuild"]
        else:
            cmd_prefix = ["esbuild"]
        out_path = os.path.join(tempfile.mkdtemp(prefix="aura-jsx-"),
                               os.path.basename(entry).rsplit(".", 1)[0] + ".js")
        res = run_subprocess(
            cmd_prefix + [os.path.join(root, entry), f"--outfile={out_path}",
                          "--loader:.jsx=jsx", "--loader:.tsx=tsx",
                          "--format=cjs", "--jsx=automatic"],
            timeout_s=60,
        )
        return out_path if res.ok else None
