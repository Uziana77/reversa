"""Score pipeline runs against benchmark ground truth (synopsis 6.6).

Reads one run directory (the artefacts written by ``aura run``:
``state.json`` + ``llm_usage.json``) plus the unit's ``meta.json`` /
``reference/rules.json`` / ``reference/glossary.json`` and produces the
metric table used by the experiment runners and REPORT.md.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence

from .metrics import (
    bertscore_proxy,
    bleu4,
    identifier_recall,
    rule_captured,
    spans_overlap,
)


def _load_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def resolve_anchor(root: str, anchor: str) -> dict:
    anchor = (anchor or "").strip()
    data_exts = (".json", ".md", ".txt", ".ebnf", ".csv", ".yaml", ".yml")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in ("reference", "attacks", "tests", "work", "work_injected")]
        for fn in sorted(filenames):
            if fn.endswith(data_exts):
                continue  # anchors resolve to code, never to metadata
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if anchor in line:
                            return {"file": os.path.relpath(path, root),
                                    "line_start": i, "line_end": i}
            except OSError:
                continue
    return {}


def _latest(state: dict, artefact: str) -> dict:
    arts = (state.get("artefacts") or {}).get(artefact) or []
    return (arts[-1].get("payload") or {}) if arts else {}


def score_run(unit_dir: str, run_dir: str) -> Dict[str, Any]:
    unit_dir = unit_dir.rstrip("/")
    meta = _load_json(os.path.join(unit_dir, "meta.json"), {})
    unit_id = meta.get("id") or os.path.basename(unit_dir)
    gold_doc = _load_json(os.path.join(unit_dir, meta.get("gold_rules", "reference/rules.json")), {})
    gold_rules = gold_doc.get("rules", [])
    glossary = (_load_json(os.path.join(unit_dir, meta.get("glossary", "reference/glossary.json")), {})
                or {}).get("terms", {})

    # gold spans resolved against the pristine unit tree
    for g in gold_rules:
        g.setdefault("source", resolve_anchor(unit_dir, g.get("anchor", "")))

    state = _load_json(os.path.join(run_dir, "state.json"), {}) or {}
    usage = _load_json(os.path.join(run_dir, "llm_usage.json"), {}) or {}
    inv = _latest(state, "RuleInventory")
    extracted = inv.get("rules", []) or []
    evidence = _latest(state, "EvidenceReport")
    ber = _latest(state, "EquivalenceReport") or _latest(state, "BERReport")
    modern = _latest(state, "ModernizedCode")

    # ---- rule capture ---------------------------------------------------
    # Injected (attack) rules can never count as captures.
    extracted_real = [r for r in extracted if not r.get("false_injection")]
    captured, capture_rows = [], []
    matched_ext = set()
    for g in gold_rules:
        hit, shared = rule_captured(g, extracted_real)
        row = {"gold": g["id"], "captured": bool(hit),
               "extracted_id": (hit or {}).get("id"),
               "shared_identifier": shared}
        capture_rows.append(row)
        if hit:
            captured.append(g["id"])
            matched_ext.add(id(hit))
    precision_denom = max(len(extracted_real), 1)
    extraction_precision = round(len(matched_ext) / precision_denom, 4)
    capture_rate = round(len(captured) / max(len(gold_rules), 1), 4)

    # ---- statement quality on matched pairs ------------------------------
    bleus, f1s = [], []
    for g in gold_rules:
        hit, _ = rule_captured(g, extracted_real)
        if hit:
            bleus.append(bleu4(hit.get("statement", ""), g.get("statement", "")))
            f1s.append(bertscore_proxy(hit.get("statement", ""), g.get("statement", ""))["f1"])
    stmt_bleu = round(sum(bleus) / max(len(bleus), 1), 4) if bleus else 0.0
    stmt_bert = round(sum(f1s) / max(len(f1s), 1), 4) if f1s else 0.0

    # ---- glossary recall over extracted text -----------------------------
    ext_text = " ".join(
        [r.get("statement", "") for r in extracted]
        + [c for r in extracted for c in (r.get("postconditions") or [])]
    )
    gloss = identifier_recall(list(glossary.keys()), ext_text)

    # ---- structural metrics ----------------------------------------------
    gold_files = {(g.get("source") or {}).get("file") for g in gold_rules if g.get("source")}
    covered_files = {
        (g.get("source") or {}).get("file") for g in gold_rules
        if g["id"] in captured and (g.get("source") or {}).get("file")
    }
    unit_coverage = round(len(covered_files) / max(len(gold_files), 1), 4)

    def _valid_span(r) -> bool:
        sp = r.get("source") or {}
        if not sp or not sp.get("file"):
            return False
        path = os.path.join(unit_dir, sp["file"])
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                n = sum(1 for _ in fh)
            return 1 <= int(sp.get("line_start", 0)) <= n
        except OSError:
            return False

    traceable = [r for r in extracted if r.get("source")]
    traceability = round(len(traceable) / max(len(extracted), 1), 4)
    valid_spans = round(sum(1 for r in extracted if _valid_span(r)) / max(len(extracted), 1), 4)

    bins = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for r in extracted:
        c = float(r.get("static_confidence", 0.0))
        key = min(int(c * 5), 4) / 5.0
        label = {"0.0": "0.0-0.2", "0.2": "0.2-0.4", "0.4": "0.4-0.6",
                 "0.6": "0.6-0.8", "0.8": "0.8-1.0"}[f"{key:.1f}"]
        bins[label] += 1

    gaps = [{"gold": g["id"], "statement": g.get("statement", "")}
            for g in gold_rules if g["id"] not in captured]

    # ---- dynamic evidence + safety gate ----------------------------------
    findings = {f.get("rule_id"): f for f in evidence.get("findings", []) or []}
    dyn = {"confirmed": 0, "contradicted": 0, "unresolved": 0}
    if findings:
        for f in findings.values():
            lab = f.get("label") or "unresolved"
            dyn[lab if lab in dyn else "unresolved"] += 1
    else:
        for r in extracted:
            lab = r.get("dynamic_label") or "unresolved"
            if lab in ("confirmed", "contract_passed", "verified"):
                dyn["confirmed"] += 1
            elif lab in ("contradicted", "contract_failed"):
                dyn["contradicted"] += 1
            else:
                dyn["unresolved"] += 1
    injected = [r for r in extracted if r.get("false_injection")]
    injected_ids = {r["id"] for r in injected}
    gate_blocked = [rid for rid in injected_ids
                    if findings.get(rid, {}).get("label") == "contradicted"]
    safety = {
        "injected_total": len(injected),
        "injected_blocked": len(gate_blocked),
        "injected_survived": len(injected) - len(gate_blocked),
        "block_rate": round(len(gate_blocked) / max(len(injected), 1), 4),
    }
    # invariant: no generated code may come from a blocked BSG node
    bsg = _latest(state, "BSG")
    blocked_nodes = {n.get("id") for n in bsg.get("nodes", []) if n.get("blocked")}
    leaked = [sp.get("node_id") for sp in modern.get("node_spans", []) or []
              if sp.get("node_id") in blocked_nodes]
    safety["blocked_nodes_total"] = len(blocked_nodes)
    safety["blocked_node_code_leak"] = len(leaked)

    # ---- documentation quality vs ground-truth docs -----------------------
    doc_payload = _latest(state, "Documentation")
    gold_docs_path = os.path.join(unit_dir, meta.get("gold_docs", "reference/docs.md"))
    with open(gold_docs_path, encoding="utf-8") as fh:
        gold_docs = fh.read()
    gen_docs = ""
    md_path = doc_payload.get("markdown_path") if isinstance(doc_payload, dict) else ""
    if md_path and os.path.exists(md_path):
        with open(md_path, encoding="utf-8") as fh:
            gen_docs = fh.read()
    astmap = _latest(state, "ASTMap")
    doc_unit_count = max(
        int(doc_payload.get("unit_summaries", 0) or 0), 1) if doc_payload else 1
    ast_units = max(int(astmap.get("unit_count", 0) or 0), 1)
    docs_metrics = {
        "bleu4": round(bleu4(gen_docs, gold_docs), 4),
        "bertscore_f1": round(bertscore_proxy(gen_docs, gold_docs)["f1"], 4),
        "glossary_recall": identifier_recall(list(glossary.keys()), gen_docs)["recall"],
        "unit_coverage": round(min(doc_unit_count / ast_units, 1.0), 4),
        "chars": len(gen_docs),
    }

    # ---- cost -------------------------------------------------------------
    cost = {
        "llm_calls": usage.get("n_calls", usage.get("total_calls", 0)) or 0,
        "prompt_tokens": usage.get("prompt_tokens", 0) or 0,
        "completion_tokens": usage.get("completion_tokens", 0) or 0,
        "estimated_cost_usd": usage.get("estimated_cost_usd", 0.0) or 0.0,
    }

    return {
        "unit": unit_id,
        "run_dir": run_dir,
        "gold_rules": len(gold_rules),
        "extracted_rules": len(extracted),
        "injected_rules": len(injected),
        "capture_rate": capture_rate,
        "extraction_precision": extraction_precision,
        "captured": captured,
        "gaps": gaps,
        "capture_rows": capture_rows,
        "statement_bleu4": stmt_bleu,
        "statement_bertscore_f1": stmt_bert,
        "docs": docs_metrics,
        "glossary_recall": gloss,
        "unit_coverage": unit_coverage,
        "traceability_density": traceability,
        "valid_span_rate": valid_spans,
        "confidence_bins": bins,
        "dynamic_labels": dyn,
        "safety_gate": safety,
        "ber": ber.get("ber"),
        "testable_share": ber.get("testable_share"),
        "retained_pass_rate": ber.get("retained_pass_rate"),
        "total_rules_ber": ber.get("total_rules"),
        "modernization_mode": modern.get("mode"),
        "review_markers": modern.get("review_markers", modern.get("review_count")),
        "cost": cost,
    }


def score_matrix(results_root: str, bench_root: str) -> Dict[str, Any]:
    """Score every ``results_root/<exp>/<unit>/`` run directory."""
    out: Dict[str, Any] = {}
    for exp in sorted(os.listdir(results_root)):
        exp_dir = os.path.join(results_root, exp)
        if not os.path.isdir(exp_dir):
            continue
        out[exp] = {}
        for unit in sorted(os.listdir(exp_dir)):
            run_dir = os.path.join(exp_dir, unit)
            unit_dir = _find_unit(bench_root, unit)
            if not unit_dir or not os.path.isdir(run_dir):
                continue
            out[exp][unit] = score_run(unit_dir, run_dir)
    return out


def _find_unit(bench_root: str, unit_id: str) -> Optional[str]:
    for sub in ("dialects", "projects"):
        path = os.path.join(bench_root, sub, unit_id)
        if os.path.isdir(path):
            return path
    return None
