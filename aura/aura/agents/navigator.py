"""Agent 1 — Codebase Navigator.

Decides (Table 4): traversal order, what is "key", language per file.
Skills it calls: file walk, extension/heuristic language detection,
dependency scan.  Writes the RepoMap artefact.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional, Tuple

from ..skills import filewalk, langdetect
from .base import Agent, spans_of


class CodebaseNavigatorAgent(Agent):
    name = "navigator"
    goal = ("Map the repository: enumerate files, detect each file's language, "
            "flag files whose language cannot be identified, and record "
            "dependency edges between modules.")

    def canonical_actions(self, context: dict) -> List[dict]:
        return [
            {"action": "walk_files", "args": {}},
            {"action": "detect_languages", "args": {}},
            {"action": "scan_dependencies", "args": {}},
            {"action": "mark_unknown_languages", "args": {}},
        ]

    def work(self, context: dict, actions: List[dict]) -> Tuple[Any, float, List[dict]]:
        root = context["run"]["root"]
        entries = filewalk.walk(root)
        files = []
        dep_edges = []
        for e in entries:
            try:
                with open(e.abs_path, encoding="utf-8", errors="replace") as fh:
                    text = fh.read(200_000)
            except OSError:
                text = ""
            lang, conf, method = langdetect.detect(e.path, text)
            unknown = langdetect.is_unknown(lang, conf)
            is_entry = self._is_entry(e.path, text)
            files.append({
                "path": e.path,
                "language": lang,
                "language_confidence": conf,
                "language_method": method,
                "unknown_language": unknown,
                "lines": e.lines,
                "size_bytes": e.size_bytes,
                "is_entry": is_entry,
            })
            for other in files[:-1]:
                if self._mentions(text, other["path"]):
                    dep_edges.append({"from": e.path, "to": other["path"], "kind": "import"})
        plan = self.provider.complete_json(
            "navigator.plan",
            system="You are the AURA Codebase Navigator. Identify key files and a traversal order.",
            user="CONTEXT_JSON: " + __import__("json").dumps({"files": files}, default=str),
            schema_hint={"key_files": ["path"], "traversal_order": ["path"]},
            fallback={"key_files": [f["path"] for f in files if f["is_entry"]],
                      "traversal_order": [f["path"] for f in files]},
        )
        payload = {
            "root": os.path.abspath(root),
            "files": files,
            "dependency_edges": dep_edges,
            "unknown_language_files": [f["path"] for f in files if f["unknown_language"]],
            "key_files": (plan.data or {}).get("key_files", []),
            "traversal_order": (plan.data or {}).get("traversal_order", [f["path"] for f in files]),
            "file_count": len(files),
            "total_lines": sum(f["lines"] for f in files),
        }
        conf = sum(1 for f in files if not f["unknown_language"]) / max(1, len(files))
        return payload, conf, [{"file": f["path"], "line_start": 1, "line_end": 1} for f in files[:50]]

    # ------------------------------------------------------------------
    def schema_check(self, payload: Any) -> Tuple[bool, str]:
        for key in ("files", "dependency_edges", "unknown_language_files", "key_files"):
            if key not in payload:
                return False, f"missing {key}"
        if not payload["files"]:
            return False, "empty file list"
        return True, ""

    def provenance_check(self, payload: Any, provenance: Optional[List[dict]] = None) -> Tuple[bool, str]:
        return (True, "") if (provenance or spans_of(payload)) else (False, "no provenance spans")

    @staticmethod
    def _is_entry(path: str, text: str) -> bool:
        name = os.path.basename(path).lower()
        return name in ("main.cbl", "main.go", "main.java", "index.js", "main.js",
                        "main.rpt", "main.ilg") or "PROGRAM-ID" in text[:300].upper() \
            or text.lstrip().startswith("PROCEDURE ")

    @staticmethod
    def _mentions(text: str, other_path: str) -> bool:
        base = os.path.basename(other_path)
        stem = os.path.splitext(base)[0]
        return len(stem) > 2 and (base in text or f"{stem}(" in text)
