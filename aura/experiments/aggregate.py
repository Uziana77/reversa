#!/usr/bin/env python3
"""Aggregate experiment results into summary tables + statistics.

Reads ``results/<exp>/<unit>/score.json`` and writes
``results/summary.json`` and ``results/summary.md`` (per-experiment metric
means over units, plus Wilcoxon signed-rank comparisons of AURA (A0)
against each ablation and baseline on the documentation metrics).

Usage:  python experiments/aggregate.py [--results results]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
AURA_ROOT = os.path.dirname(HERE)

METRICS = [
    ("capture_rate", "rule capture"),
    ("statement_bleu4", "statement BLEU-4"),
    ("statement_bertscore_f1", "statement BERTScore-F1"),
    ("unit_coverage", "unit coverage"),
    ("traceability_density", "traceability density"),
    ("valid_span_rate", "valid-span rate"),
]


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def collect(results: str) -> dict:
    out = {}
    for exp in sorted(os.listdir(results)):
        exp_dir = os.path.join(results, exp)
        if not os.path.isdir(exp_dir):
            continue
        out[exp] = {}
        for unit in sorted(os.listdir(exp_dir)):
            sp = os.path.join(exp_dir, unit, "score.json")
            if os.path.isfile(sp):
                out[exp][unit] = _load(sp)
    return out


def mean(vals: List[float]) -> float:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def wilcoxon_signed_rank(a: List[float], b: List[float]) -> Tuple[float, float, float]:
    """Self-implemented Wilcoxon signed-rank (normal approximation) on
    paired samples; returns (W_minus, p_two_sided, rank_biserial)."""
    diffs = [(x - y) for x, y in zip(a, b) if x is not None and y is not None]
    diffs = [d for d in diffs if d != 0]
    n = len(diffs)
    if n < 2:
        return 0.0, 1.0, 0.0
    order = sorted(range(n), key=lambda i: abs(diffs[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(diffs[order[j + 1]]) == abs(diffs[order[i]]):
            j += 1
        avg = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    w_plus = sum(r for d, r in zip(diffs, ranks) if d > 0)
    w_minus = sum(r for d, r in zip(diffs, ranks) if d < 0)
    mu = n * (n + 1) / 4.0
    sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0) or 1.0
    z = (min(w_plus, w_minus) - mu) / sigma
    p = 2.0 * (0.5 * math.erfc(abs(z) / math.sqrt(2.0)))
    rb = (w_plus - w_minus) / (w_plus + w_minus)
    return round(min(w_plus, w_minus), 3), round(min(p, 1.0), 4), round(rb, 3)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default=os.path.join(AURA_ROOT, "results"))
    args = ap.parse_args()
    data = collect(args.results)
    if not data:
        print("no score.json files found")
        return 1

    summary = {"experiments": {}, "comparisons": {}, "units": {}}
    lines = ["# AURA experiment summary", ""]

    for exp, runs in data.items():
        agg = {}
        for key, label in METRICS:
            agg[key] = mean([r.get(key) for r in runs.values()])
        agg["docs_bleu4"] = mean([r.get("docs", {}).get("bleu4") for r in runs.values()])
        agg["docs_bertscore_f1"] = mean([r.get("docs", {}).get("bertscore_f1") for r in runs.values()])
        agg["docs_glossary_recall"] = mean([r.get("docs", {}).get("glossary_recall") for r in runs.values()])
        agg["docs_unit_coverage"] = mean([r.get("docs", {}).get("unit_coverage") for r in runs.values()])
        agg["ber"] = mean([r.get("ber") for r in runs.values()])
        agg["testable_share"] = mean([r.get("testable_share") for r in runs.values()])
        agg["llm_calls"] = mean([r.get("cost", {}).get("llm_calls") for r in runs.values()])
        agg["gate_block_rate"] = mean([r.get("safety_gate", {}).get("block_rate") for r in runs.values()])
        agg["gate_injected"] = mean([r.get("safety_gate", {}).get("injected_total") for r in runs.values()])
        agg["gate_blocked"] = mean([r.get("safety_gate", {}).get("injected_blocked") for r in runs.values()])
        agg["gate_survived"] = mean([r.get("safety_gate", {}).get("injected_survived") for r in runs.values()])
        summary["experiments"][exp] = agg

    for other in sorted(data):
        if other == "A0" or "A0" not in data:
            continue
        common = sorted(set(data["A0"]) & set(data[other]))
        row = {}
        for key in ("docs_bleu4", "docs_bertscore_f1", "docs_glossary_recall",
                    "capture_rate", "ber"):
            a = [data["A0"][u].get(key) if key != "docs_bleu4"
                 else data["A0"][u].get("docs", {}).get("bleu4") for u in common]
            b = [data[other][u].get(key) if key != "docs_bleu4"
                 else data[other][u].get("docs", {}).get("bleu4") for u in common]
            w, p, rb = wilcoxon_signed_rank(a, b)
            row[key] = {"W": w, "p": p, "rank_biserial": rb, "n": len(common)}
        summary["comparisons"][f"A0_vs_{other}"] = row

    for exp, runs in data.items():
        summary["units"].setdefault("per_unit", {})
        for unit, r in runs.items():
            summary["units"]["per_unit"].setdefault(unit, {})[exp] = {
                "capture_rate": r.get("capture_rate"),
                "ber": r.get("ber"),
                "docs_bleu4": r.get("docs", {}).get("bleu4"),
                "docs_bertscore_f1": r.get("docs", {}).get("bertscore_f1"),
                "gate_block_rate": r.get("safety_gate", {}).get("block_rate"),
            }

    with open(os.path.join(args.results, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    # markdown tables
    lines.append("## Mean metrics per experiment")
    lines.append("")
    keys = ["capture_rate", "statement_bleu4", "statement_bertscore_f1",
            "docs_bleu4", "docs_bertscore_f1", "docs_glossary_recall",
            "unit_coverage", "traceability_density", "valid_span_rate",
            "ber", "testable_share", "gate_block_rate", "llm_calls"]
    lines.append("| exp | " + " | ".join(keys) + " |")
    lines.append("|---" * (len(keys) + 1) + "|")
    for exp, agg in summary["experiments"].items():
        lines.append("| " + exp + " | " + " | ".join(str(agg.get(k, "")) for k in keys) + " |")
    lines.append("")
    lines.append("## Safety gate (S1: injected false rules)")
    lines.append("")
    if "S1" in summary["experiments"]:
        s = summary["experiments"]["S1"]
        lines.append(f"- injected: {s['gate_injected']} per unit (mean)")
        lines.append(f"- labelled contradicted (blocked): {s['gate_blocked']}")
        lines.append(f"- survived: {s['gate_survived']} — block rate {s['gate_block_rate']}")
    lines.append("")
    lines.append("## A0 vs ... (Wilcoxon signed-rank, per unit)")
    lines.append("")
    for name, row in summary["comparisons"].items():
        for metric, st in row.items():
            lines.append(f"- {name} on {metric}: W={st['W']}, p={st['p']}, "
                         f"rank-biserial={st['rank_biserial']}, n={st['n']}")
    with open(os.path.join(args.results, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {os.path.join(args.results, 'summary.json')}")
    print(f"wrote {os.path.join(args.results, 'summary.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
