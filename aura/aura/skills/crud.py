"""CRUD table extraction skill (create/read/update/delete against data stores)."""

from __future__ import annotations

from typing import Dict, List

CRUD_PATTERNS = [
    ("update", ("COMPUTE", "MOVE", "ADD ", "SUBTRACT", "MULTIPLY", "DIVIDE", "=", "SET ", "put(")),
    ("create", ("INSERT", "CREATE", "append(", "push(", "ADD ", "new ")),
    ("read", ("READ", "SELECT", "FETCH", "get(", "find(", "lookup", "ACCEPT")),
    ("delete", ("DELETE", "REMOVE", "DROP", "splice(", "clear(")),
]


def extract_crud(units: List[dict]) -> List[dict]:
    """Flatten per-unit CRUD annotations into one table."""
    table: List[dict] = []
    for u in units:
        for c in u.get("crud", []) or []:
            table.append(
                {
                    "unit": u.get("symbol"),
                    "file": u.get("file"),
                    "op": c.get("op", "update"),
                    "store": c.get("store", c.get("target", "state")),
                    "line": c.get("line", u.get("line_start", 0)),
                }
            )
    return table
