#!/usr/bin/env python3
"""Baseline runners B1/B2/B3 (synopsis 6.8).  Each writes a minimal
``state.json`` with a Documentation artefact so the standard scorer can
compare all systems on the same metrics."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import List

HERE = os.path.dirname(os.path.abspath(__file__))
AURA_ROOT = os.path.dirname(HERE)
sys.path.insert(0, AURA_ROOT)

from aura.llm.registry import make_provider  # noqa: E402

FUNC_SPLIT = {
    "go": r"(?m)^(?:func)\s+",
    "java": r"(?m)^\s*(?:public|private|protected)\s+[\w<>\[\]]+\s+\w+\s*\(",
    "cobol": r"(?m)^[A-Z0-9-]+\.\s*$",
    "javascript": r"(?m)^(?:function\s+\w+|(?:const|var|let)\s+\w+\s*=\s*function)",
    "javascript-react": r"(?m)^(?:function\s+\w+|(?:const|var|let)\s+\w+\s*=\s*function)",
}


def _texts_of(data: dict) -> str:
    for key in ("documentation", "summary", "text", "markdown"):
        if data.get(key):
            return str(data[key])
    return " ".join(str(v) for v in data.values() if isinstance(v, (str, int, float)))


def _split_functions(code: str, language: str) -> List[str]:
    pattern = FUNC_SPLIT.get(language)
    if not pattern:
        return [code]
    parts = re.split(pattern, code)
    return [p for p in parts if p.strip()][:40] or [code]


def _write_state(out_dir: str, unit_id: str, docs_md: str, unit_summaries: int) -> None:
    md_path = os.path.join(out_dir, f"{unit_id}_documentation.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(docs_md)
    state = {
        "artefacts": {
            "Documentation": [{
                "producer": "baseline", "artefact": "Documentation", "version": 1,
                "payload": {"markdown_path": md_path, "unit_summaries": unit_summaries},
                "provenance": [], "confidence": 1.0, "status": "ok", "notes": "",
            }],
        },
        "session_log": [], "escalations": [],
    }
    with open(os.path.join(out_dir, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    with open(os.path.join(out_dir, "llm_usage.json"), "w", encoding="utf-8") as fh:
        json.dump({"total_calls": 0, "prompt_tokens": 0, "completion_tokens": 0}, fh)


def run_b1(unit_dir: str, meta: dict, out_dir: str, provider) -> None:
    """One single prompt per source file, no agentic context."""
    os.makedirs(out_dir, exist_ok=True)
    unit_id = meta.get("id", "unit")
    files = meta.get("source_files") or [
        f for f in sorted(os.listdir(unit_dir))
        if os.path.isfile(os.path.join(unit_dir, f))]
    sections = []
    for rel in files:
        path = os.path.join(unit_dir, rel)
        if not os.path.isfile(path):
            continue
        code = open(path, encoding="utf-8", errors="ignore").read()[:8000]
        res = provider.complete_json(
            "summary.system",
            system=("You document one legacy source file for maintainers. "
                    "Write complete documentation of every business rule."),
            user=f"FILE {rel}\n{code}",
            schema_hint={"documentation": "str"},
            fallback={"documentation": ""},
        )
        sections.append(f"# {rel}\n\n{_texts_of(res.data or {})}")
    _write_state(out_dir, unit_id, "\n\n".join(sections), max(len(files), 1))
    with open(os.path.join(out_dir, "llm_usage.json"), "w", encoding="utf-8") as fh:
        json.dump(provider.ledger.to_dict(), fh, indent=2)


def run_b2(unit_dir: str, meta: dict, out_dir: str, provider) -> None:
    """Function-level summarisation: one call per function, no repo context."""
    os.makedirs(out_dir, exist_ok=True)
    unit_id = meta.get("id", "unit")
    files = meta.get("source_files") or [
        f for f in sorted(os.listdir(unit_dir))
        if os.path.isfile(os.path.join(unit_dir, f))]
    summaries = []
    for rel in files:
        path = os.path.join(unit_dir, rel)
        if not os.path.isfile(path):
            continue
        code = open(path, encoding="utf-8", errors="ignore").read()
        for chunk in _split_functions(code, meta.get("language", "")):
            res = provider.complete_json(
                "summary.function",
                system="Summarise what this code fragment does.",
                user=chunk[:3000],
                schema_hint={"summary": "str"},
                fallback={"summary": ""},
            )
            summaries.append(f"- {rel}: {_texts_of(res.data or {})}")
    docs = f"# {unit_id} — function summaries\n\n" + "\n".join(summaries)
    _write_state(out_dir, unit_id, docs, max(len(summaries), 1))
    with open(os.path.join(out_dir, "llm_usage.json"), "w", encoding="utf-8") as fh:
        json.dump(provider.ledger.to_dict(), fh, indent=2)


def run_b3(unit_dir: str, meta: dict, out_dir: str) -> None:
    """Human-engineer baseline: the hand-authored reference documentation."""
    os.makedirs(out_dir, exist_ok=True)
    unit_id = meta.get("id", "unit")
    gold = os.path.join(unit_dir, meta.get("gold_docs", "reference/docs.md"))
    docs = open(gold, encoding="utf-8").read()
    _write_state(out_dir, unit_id, docs, 999)
