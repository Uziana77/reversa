"""Agent 3 — AST Analyzer.

Decides (Table 4): grammar choice per file, fallback on parse failure
(retry with the inferred grammar, fall back to line-level heuristics, or
mark the file unparseable).  Skills: tree-sitter parse, call-graph build,
CRUD extraction.  Writes the ASTMap artefact (per-file AST, call graph,
CRUD table).
"""

from __future__ import annotations

import os
from typing import Any, List, Tuple

from ..skills import astree, callgraph, crud
from .base import Agent


class ASTAnalyzerAgent(Agent):
    name = "ast_analyzer"
    goal = ("Parse every file — Tree-sitter where the language is known and "
            "the inferred grammar otherwise — and produce the AST map, call "
            "graph and CRUD table. Never guess a parse: unparseable files "
            "are recorded as such.")

    def canonical_actions(self, context: dict) -> List[dict]:
        return [
            {"action": "choose_grammar_per_file", "args": {}},
            {"action": "parse_files", "args": {}},
            {"action": "build_call_graph", "args": {}},
            {"action": "extract_crud_table", "args": {}},
        ]

    def work(self, context: dict, actions: List[dict]) -> Tuple[Any, float, List[dict]]:
        payloads = context["payloads"]
        repomap = payloads.get("RepoMap") or {}
        grammar = payloads.get("GrammarHypothesis") or {}
        root = context["run"]["root"]

        inferred_ok = bool(grammar.get("hypotheses")) and any(
            h.get("accepted_for_downstream") for h in grammar.get("hypotheses", [])
        )
        units: List[dict] = []
        file_reports = []
        parse_methods = {}
        for f in repomap.get("files", []):
            rel = f["path"]
            lang = f.get("language")
            try:
                with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
                    text = fh.read(200_000)
            except OSError:
                text = ""
            if f.get("unknown_language") and not inferred_ok:
                file_reports.append({"file": rel, "parse_method": "none",
                                     "ok": False, "note": "no accepted grammar (marked unparseable)"})
                continue
            if f.get("unknown_language") and inferred_ok:
                lang = "interlock" if rel.endswith(".ilg") else "reportscript" if rel.endswith(".rpt") else lang
            try:
                res = astree.analyze_file(rel, text, lang)
            except Exception as exc:  # noqa: BLE001 — parse failure is data, not a crash
                file_reports.append({"file": rel, "parse_method": "failed", "ok": False,
                                     "note": f"{type(exc).__name__}: {exc}"})
                continue
            units.extend(res.get("units", []))
            parse_methods[rel] = res.get("parse_method", "?")
            file_reports.append({"file": rel, "parse_method": res.get("parse_method"),
                                 "ok": res.get("ok", False),
                                 "units": len(res.get("units", []))})

        cg = callgraph.build_call_graph(units)
        crud_table = crud.extract_crud(units)
        payload = {
            "units": units,
            "file_reports": file_reports,
            "parse_methods": parse_methods,
            "call_graph": cg,
            "crud_table": crud_table,
            "unit_count": len(units),
        }
        ok_files = sum(1 for r in file_reports if r.get("ok"))
        conf = ok_files / max(1, len(file_reports))
        prov = [{"file": u["file"], "line_start": u["line_start"], "line_end": u["line_end"]}
                for u in units[:80]]
        return payload, conf, prov

    def schema_check(self, payload: Any) -> Tuple[bool, str]:
        for key in ("units", "call_graph", "crud_table", "file_reports"):
            if key not in payload:
                return False, f"missing {key}"
        for u in payload["units"]:
            if not all(k in u for k in ("file", "symbol", "line_start")):
                return False, "unit missing file/symbol/line_start"
        return True, ""
