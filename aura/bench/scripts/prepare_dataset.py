#!/usr/bin/env python3
"""Prepare benchmark working copies (synopsis 6.3).

For every unit under ``bench/dialects/`` and ``bench/projects/`` this
script materialises ``work/`` — the pristine, undocumented working copy
the pipeline analyses (``aura run --root <unit>/work --unit
<meta.json>``).  Reference material (``reference/``, ``tests/``,
``attacks/``) stays outside the working copy, exactly as real legacy
estates carry no ground truth.  A ``work_manifest.json`` records file
hashes so later runs can prove the copy is pristine.

Injected-false-rule experiments (B3) are materialised per run by passing
``attack_file`` to :func:`build_work` (or via ``--attack`` for the demo
copy ``work_injected/``), which additionally writes the attack rules into
the working copy and a side file consumed by
``RunConfig.extra["injected_rules"]``.

Usage:
    python bench/scripts/prepare_dataset.py [--attack] [unit-dir ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)

KEEP_DIRS = {"reference", "tests", "attacks", "work", "work_injected", "__pycache__"}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def unit_dirs() -> list:
    out = []
    for sub in ("dialects", "projects"):
        base = os.path.join(BENCH, sub)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            path = os.path.join(base, name)
            if os.path.isdir(path) and os.path.exists(os.path.join(path, "meta.json")):
                out.append(path)
    return out


def build_work(unit_dir: str, out_name: str = "work",
               attack_file: str = None) -> dict:
    """Create ``<unit_dir>/<out_name>/`` and return its manifest."""
    src_root = unit_dir
    dst = os.path.join(unit_dir, out_name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    manifest = {"unit": os.path.basename(unit_dir), "files": {}}
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [d for d in dirnames if d not in KEEP_DIRS]
        for fn in sorted(filenames):
            if fn.endswith((".pyc",)):
                continue
            src = os.path.join(dirpath, fn)
            rel = os.path.relpath(src, src_root)
            tgt = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(tgt), exist_ok=True)
            shutil.copy2(src, tgt)
            manifest["files"][rel] = _sha256(src)
    if attack_file:
        # Attack material is recorded in the manifest but NEVER copied into
        # the analysed tree: injected rules enter the pipeline only through
        # RunConfig.extra["injected_rules"], so the working copy stays
        # indistinguishable from a clean run.
        if os.path.exists(os.path.join(unit_dir, attack_file)):
            manifest["attack"] = attack_file
    with open(os.path.join(dst, "work_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("units", nargs="*", help="unit directories (default: all)")
    ap.add_argument("--attack", action="store_true",
                    help="also build work_injected/ copies carrying the attack rules")
    args = ap.parse_args()
    units = args.units or unit_dirs()
    for unit_dir in units:
        meta_path = os.path.join(unit_dir, "meta.json")
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        m = build_work(unit_dir)
        line = f"[work] {os.path.relpath(unit_dir, BENCH)}: {len(m['files'])} files"
        if args.attack and meta.get("attacks"):
            build_work(unit_dir, out_name="work_injected", attack_file=meta["attacks"])
            line += " (+injected copy)"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
