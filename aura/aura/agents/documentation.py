"""Agent 9 — Documentation Generator.

Decides (Table 4): document structure, level of detail per component.
Skills: Markdown/JSON render, graph render, provenance walk.

Control rule 5: this is the only agent that reads every artefact; it
produces the audit trail by walking provenance fields back to source
lines.  Output is hierarchical documentation (function, class, module,
system level), a data dictionary, BSG graph renderings and the audit
trail.
"""

from __future__ import annotations

import json
import os
from typing import Any, List, Tuple

from ..skills import render
from ..skills.provenance import audit_walk
from .base import Agent, spans_of


class DocumentationGeneratorAgent(Agent):
    name = "documentation_generator"
    goal = ("Emit hierarchical documentation at function, class, module and "
            "system level, the data dictionary and graph renderings, plus "
            "the audit trail linking every claim to its source lines.")

    def canonical_actions(self, context: dict) -> List[dict]:
        return [
            {"action": "outline_document", "args": {}},
            {"action": "summarise_units", "args": {}},
            {"action": "render_bsg", "args": {}},
            {"action": "build_data_dictionary", "args": {}},
            {"action": "walk_provenance", "args": {}},
        ]

    def work(self, context: dict, actions: List[dict]) -> Tuple[Any, float, List[dict]]:
        payloads = context["payloads"]
        run = context["run"]
        unit = run.get("unit", {})
        out_dir = run.get("output_dir") or os.path.join(run["root"], "_aura_out")
        os.makedirs(out_dir, exist_ok=True)

        repomap = payloads.get("RepoMap") or {}
        astmap = payloads.get("ASTMap") or {}
        rules = (payloads.get("RuleInventory") or {}).get("rules", [])
        evidence = payloads.get("EvidenceReport") or {}
        bsg = payloads.get("BSG") or {}
        modern = payloads.get("ModernizedCode") or {}
        equiv = payloads.get("EquivalenceReport") or {}

        # unit-level summaries (LLM)
        unit_sections = []
        for u in astmap.get("units", [])[:40]:
            res = self.provider.complete_json(
                "summary.function",
                system="You are the AURA Documentation Generator. Summarise one analysis unit.",
                user="CONTEXT_JSON: " + json.dumps({
                    "symbol": u.get("symbol"), "language": u.get("file", ""),
                    "conditions": u.get("conditions", [])[:6],
                    "assignments": u.get("assignments", [])[:6],
                    "calls": u.get("calls", [])[:8],
                    "crud": u.get("crud", [])[:8],
                }, default=str),
                schema_hint={"summary": "str"},
                fallback={"summary": f"{u.get('symbol', 'unit')} ({u.get('file', '')})"},
            )
            unit_sections.append({"symbol": u.get("symbol"), "file": u.get("file"),
                                  "summary": (res.data or {}).get("summary", ""),
                                  "span": {"file": u.get("file"), "line_start": u.get("line_start"),
                                           "line_end": u.get("line_end")}})

        sysres = self.provider.complete_json(
            "summary.system",
            system="You are the AURA Documentation Generator. Summarise the whole system.",
            user="CONTEXT_JSON: " + json.dumps({
                "files": repomap.get("files", []),
                "call_edges": (astmap.get("call_graph") or {}).get("edges", []),
                "crud": astmap.get("crud_table", []),
                "rules_count": len(rules),
                "unit_count": astmap.get("unit_count", 0),
            }, default=str),
            schema_hint={"overview": "str"},
            fallback={"overview": f"Legacy system with {repomap.get('file_count', 0)} files."},
        )
        overview = (sysres.data or {}).get("overview", "")

        # rule blocks with confidence states from the BSG
        state_by_rule = {}
        for n in bsg.get("nodes", []):
            for rid in n.get("rule_ids", []):
                state_by_rule[rid] = n.get("confidence_state", "inferred")
        rule_items = []
        for r in rules:
            finding = next((f for f in evidence.get("findings", []) if f["rule_id"] == r["id"]), {})
            rule_items.append({
                "id": r["id"], "statement": r.get("statement", ""),
                "confidence_state": state_by_rule.get(r["id"], "inferred"),
                "source": r.get("source") or {},
                "dynamic_label": finding.get("label"),
            })

        # data dictionary from CRUD table + rule I/O
        stores: dict = {}
        for c in astmap.get("crud_table", []):
            stores.setdefault(c.get("store", "?"), {"ops": set(), "units": set()})
            stores[c["store"]]["ops"].add(c.get("op", "?"))
            stores[c["store"]]["units"].add(c.get("unit", "?"))
        data_dict = [
            {"store": s, "operations": sorted(v["ops"]), "units": sorted(v["units"])}
            for s, v in sorted(stores.items())
        ]

        # audit trail over every artefact (control rule 5)
        file_lines = {f["path"]: f.get("lines", 1) for f in repomap.get("files", [])}
        all_arts = []
        for t in ("RepoMap", "GrammarHypothesis", "ASTMap", "RuleInventory",
                  "EvidenceReport", "BSG", "ModernizedCode", "EquivalenceReport"):
            all_arts.extend(run.get("state_ref").read_all(t) if run.get("state_ref") else [])
        audit = audit_walk(all_arts, file_lines)

        dist = bsg.get("confidence_distribution", {})
        doc = {
            "title": f"AURA Documentation — {unit.get('id', 'system')}",
            "provider": getattr(context.get("run", {}).get("config"), "provider", "?"),
            "rule_count": len(rules),
            "confidence_distribution": dist,
            "sections": [
                {"depth": 0, "title": "System Overview", "summary": overview,
                 "blocks": [{"kind": "text", "text": (
                     f"Files analysed: {repomap.get('file_count', 0)}. "
                     f"Analysis units: {astmap.get('unit_count', 0)}. "
                     f"Candidate business rules: {len(rules)}. "
                     f"Behavioural equivalence rate: {equiv.get('ber', 'n/a')} "
                     f"(testable share {equiv.get('testable_share', 'n/a')})."
                 )}]},
                {"depth": 0, "title": "Business Rules", "blocks": [
                    {"kind": "rules", "items": rule_items}]},
                {"depth": 0, "title": "Architecture and Data Access",
                 "blocks": [{"kind": "table", "rows": [["Store", "Operations", "Units"]] +
                             [[d["store"], ", ".join(d["operations"]), ", ".join(d["units"])]
                              for d in data_dict]}]},
                {"depth": 0, "title": "Units",
                 "blocks": [{"kind": "text", "text":
                             "\n".join(f"- **{s['symbol']}** ({s['file']}:{s['span']['line_start']}-"
                                       f"{s['span']['line_end']}): {s['summary']}"
                                       for s in unit_sections)}]},
                {"depth": 0, "title": "Modernization", "blocks": [{"kind": "text", "text":
                    f"Mode: {modern.get('mode', 'n/a')}. Files generated: {len(modern.get('files', []))}. "
                    f"Markers: {json.dumps(modern.get('markers', [])[:10])}"}]},
            ],
            "audit": audit,
        }

        markdown = render.render_markdown_doc(doc)
        md_path = os.path.join(out_dir, f"{unit.get('id', 'system')}_documentation.md")
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(markdown)
        json_path = os.path.join(out_dir, f"{unit.get('id', 'system')}_documentation.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, default=str)
        dot_path = os.path.join(out_dir, f"{unit.get('id', 'system')}_bsg.dot")
        with open(dot_path, "w", encoding="utf-8") as fh:
            fh.write(render.render_bsg_dot(bsg))

        payload = {
            "markdown_path": md_path,
            "json_path": json_path,
            "bsg_dot_path": dot_path,
            "sections": [s["title"] for s in doc["sections"]],
            "unit_summaries": len(unit_sections),
            "audit": audit,
            "data_dictionary": data_dict,
            "documentation": doc,
        }
        conf = 1.0 if audit.get("total_references", 0) else 0.6
        return payload, conf, spans_of(payload)

    def schema_check(self, payload: Any) -> Tuple[bool, str]:
        for key in ("markdown_path", "documentation", "audit"):
            if key not in payload:
                return False, f"missing {key}"
        if not os.path.exists(payload["markdown_path"]):
            return False, "markdown file was not written"
        return True, ""
