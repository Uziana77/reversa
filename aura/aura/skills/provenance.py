"""Provenance and audit-trail skill."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List


def span(file: str, line_start: int, line_end: int = 0) -> dict:
    return {"file": file, "line_start": int(line_start), "line_end": int(line_end or line_start)}


def valid_span(sp: dict, file_lines: Dict[str, int]) -> bool:
    """True when the reference points to a real line range (metric input)."""
    f = sp.get("file")
    if f not in file_lines:
        return False
    n = file_lines[f]
    try:
        a, b = int(sp.get("line_start", 0)), int(sp.get("line_end", 0))
    except (TypeError, ValueError):
        return False
    return 1 <= a <= n and a <= b <= n


def audit_walk(artefacts: List[Any], file_lines: Dict[str, int]) -> dict:
    """Walk provenance fields back to source lines (control rule 5)."""
    refs: List[dict] = []
    valid = 0
    total = 0
    for art in artefacts:
        for p in getattr(art, "provenance", []) or []:
            total += 1
            ok = valid_span(p, file_lines)
            valid += 1 if ok else 0
            refs.append({**p, "valid": ok, "artefact": getattr(art, "artefact", "?")})
    return {
        "references": refs,
        "total_references": total,
        "valid_references": valid,
        "valid_span_rate": (valid / total) if total else 0.0,
    }


def snippet_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
