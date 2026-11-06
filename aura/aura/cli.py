"""Command-line interface for AURA (batch evaluation entry point)."""

from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="aura", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run the AURA pipeline on one unit")
    p_run.add_argument("--root", required=True, help="path to the (undocumented) working copy")
    p_run.add_argument("--unit", required=True, help="path to the unit meta.json (harness)")
    p_run.add_argument("--out", required=True, help="output directory")
    p_run.add_argument("--provider", default="offline", choices=["offline", "openai"])
    p_run.add_argument("--model", default="gpt-4o-mini")
    p_run.add_argument("--ablation", default="A0", choices=["A0", "A1", "A2", "A3"])
    p_run.add_argument("--mode", default="migration", choices=["migration", "in_place"])
    p_run.add_argument("--target", default="python", choices=["python", "java", "go"])
    p_run.add_argument("--max-llm-calls", type=int, default=400)
    p_run.add_argument("--seed", type=int, default=0)

    p_st = sub.add_parser("selftest", help="offline end-to-end smoke test")
    p_st.add_argument("--out", default=".aura-selftest")

    args = parser.parse_args(argv)
    if args.cmd == "run":
        return _cmd_run(args)
    if args.cmd == "selftest":
        return _cmd_selftest(args)
    return 2


def _cmd_run(args) -> int:
    from .config import RunConfig
    from .pipeline import run_unit

    with open(args.unit, encoding="utf-8") as fh:
        unit = json.load(fh)
    cfg = RunConfig.from_ablation(
        args.ablation,
        provider=args.provider,
        model=args.model,
        modernization_mode=args.mode,
        migration_target=args.target,
        max_llm_calls=args.max_llm_calls,
        seed=args.seed,
        run_id=f"{unit.get('id', 'unit')}-{args.ablation}",
    )
    summary = run_unit(cfg, args.root, unit, args.out)
    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))
    return 0


def _cmd_selftest(args) -> int:
    """Tiny synthetic unit: proves the nine agents hand artefacts over
    end-to-end under the offline provider in a couple of seconds."""
    import tempfile

    from .config import RunConfig
    from .pipeline import run_unit

    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "mini")
        os.makedirs(root)
        with open(os.path.join(root, "mini.cbl"), "w", encoding="utf-8") as fh:
            fh.write(
                "IDENTIFICATION DIVISION.\nPROGRAM-ID. MINI.\nDATA DIVISION.\n"
                "WORKING-STORAGE SECTION.\n01 A PIC 9(3) VALUE 0.\n01 B PIC 9(3) VALUE 0.\n"
                "PROCEDURE DIVISION.\nMAIN.\n    IF A > 10 THEN\n        COMPUTE B = A * 2\n"
                "    ELSE\n        COMPUTE B = A\n    END-IF\n    STOP RUN.\n"
            )
        unit = {
            "id": "mini", "language": "cobol",
            "harness": {"language": "cobol", "entry_file": "mini.cbl", "entry_symbol": "MAIN",
                        "input_fields": {"A": "int"}, "state_fields": ["A", "B"]},
        }
        cfg = RunConfig(run_id="selftest", provider="offline")
        out = os.path.join(args.out, "mini")
        summary = run_unit(cfg, root, unit, out)
        ok = all(v.get("status") in ("ok", None) for v in summary["agents"].values())
        print(json.dumps(summary, indent=2))
        print("SELFTEST", "PASS" if ok else "FAIL")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
