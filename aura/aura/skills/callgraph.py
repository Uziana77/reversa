"""Call-graph construction skill (from ASTMap units)."""

from __future__ import annotations

from typing import Dict, List


def build_call_graph(units: List[dict]) -> dict:
    """Return nodes + edges.  An edge u->v exists when unit u mentions a call
    to symbol v (resolved against the unit symbol table)."""
    symbols = {u.get("symbol"): u for u in units if u.get("symbol")}
    nodes = [
        {"id": u.get("symbol"), "file": u.get("file"), "kind": u.get("kind", "unit"),
         "lines": [u.get("line_start", 0), u.get("line_end", 0)]}
        for u in units
    ]
    edges = []
    for u in units:
        for callee in u.get("calls", []) or []:
            name = callee.split("(")[0].strip()
            if name in symbols and name != u.get("symbol"):
                edges.append({"from": u.get("symbol"), "to": name, "kind": "call"})
    return {"nodes": nodes, "edges": edges}
