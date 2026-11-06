#!/usr/bin/env python3
"""Run the AURA experiment matrix on the benchmark.

Runs one or more configurations (A0-A3 ablations, S1 safety-gate
injection, B1-B3 baselines) across every benchmark unit and scores each
run against the ground truth.

Usage:
    python experiments/run_matrix.py --provider offline \
        [--exps A0,A1,A2,A3,S1,B1,B2,B3] [--out results] [--units u1,u2]

Output:  <out>/<exp>/<unit>/  with run artefacts + score.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
AURA_ROOT = os.path.dirname(HERE)
BENCH = os.path.join(AURA_ROOT, "bench")
sys.path.insert(0, AURA_ROOT)
sys.path.insert(0, os.path.join(BENCH, "scripts"))

from aura.config import RunConfig  # noqa: E402
from aura.eval.scoring import score_run  # noqa: E402
from aura.llm.registry import make_provider  # noqa: E402
from aura.pipeline import run_unit  # noqa: E402

import prepare_dataset  # noqa: E402
import baselines  # noqa: E402

ABLATIONS = ("A0", "A1", "A2", "A3")
ALL_EXPS = ABLATIONS + ("S1", "B1", "B2", "B3")


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def run_one(exp: str, unit_dir: str, out_root: str, provider_name: str,
            model: str, seed: int) -> dict:
    meta = _load(os.path.join(unit_dir, "meta.json"))
    unit_id = meta.get("id") or os.path.basename(unit_dir)
    out_dir = os.path.join(out_root, exp, unit_id)
    os.makedirs(out_dir, exist_ok=True)

    if exp == "B3":
        baselines.run_b3(unit_dir, meta, out_dir)
    elif exp in ("B1", "B2"):
        provider = make_provider(provider_name, model=model, seed=seed)
        if exp == "B1":
            baselines.run_b1(unit_dir, meta, out_dir, provider)
        else:
            baselines.run_b2(unit_dir, meta, out_dir, provider)
    else:
        inject = exp == "S1"
        manifest = prepare_dataset.build_work(
            unit_dir, out_name="work_injected" if inject else "work",
            attack_file=meta.get("attacks") if inject else None)
        root = os.path.join(unit_dir, "work_injected" if inject else "work")
        cfg = RunConfig.from_ablation(
            exp if exp in ABLATIONS else "A0",
            provider=provider_name, model=model, seed=seed,
            modernization_mode="migration", migration_target="python",
            run_id=f"{unit_id}-{exp}",
        )
        if inject:
            attack = _load(os.path.join(unit_dir, meta.get("attacks", "")))
            cfg.extra["injected_rules"] = attack.get("rules", [])
        run_unit(cfg, root, meta, out_dir)

    score = score_run(unit_dir, out_dir)
    score["exp"] = exp
    score["provider"] = provider_name
    score["model"] = model
    with open(os.path.join(out_dir, "score.json"), "w", encoding="utf-8") as fh:
        json.dump(score, fh, indent=2)
    return score


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provider", default="offline", choices=["offline", "openai"])
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--exps", default=",".join(ALL_EXPS))
    ap.add_argument("--units", default="")
    ap.add_argument("--out", default=os.path.join(AURA_ROOT, "results"))
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    units = []
    for sub in ("dialects", "projects"):
        base = os.path.join(BENCH, sub)
        for name in sorted(os.listdir(base)):
            if os.path.isdir(os.path.join(base, name, "")) and \
                    os.path.exists(os.path.join(base, name, "meta.json")):
                units.append(os.path.join(base, name))
    if args.units:
        keep = set(args.units.split(","))
        units = [u for u in units if os.path.basename(u) in keep]

    exps = [e.strip() for e in args.exps.split(",") if e.strip()]
    bad = 0
    for exp in exps:
        for unit_dir in units:
            unit_id = os.path.basename(unit_dir)
            try:
                score = run_one(exp, unit_dir, args.out, args.provider,
                                args.model, args.seed)
                print(f"[{exp}] {unit_id}: capture={score['capture_rate']} "
                      f"ber={score['ber']} gate={score['safety_gate']['block_rate']}")
            except Exception:
                bad += 1
                print(f"[{exp}] {unit_id}: FAILED")
                traceback.print_exc()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
