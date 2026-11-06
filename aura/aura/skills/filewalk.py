"""File-walk skill: enumerate a repository deterministically."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", "target", ".idea", ".vscode", ".tox", ".mypy_cache",
    ".reversa", "_reversa_sdd", ".agents", ".claude", "results", "work",
}

TEXT_EXTENSIONS = {
    ".cbl", ".cob", ".cpy", ".jcl", ".go", ".java", ".js", ".jsx", ".ts", ".tsx",
    ".py", ".rb", ".cs", ".c", ".cpp", ".h", ".hpp", ".pl", ".sh", ".sql", ".rpg",
    ".m", ".asm", ".s", ".bas", ".f", ".f90", ".prg", ".cls", ".frm", ".ilg", ".rpt",
    ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".csv", ".ini", ".cfg", ".toml",
}


@dataclass
class FileEntry:
    path: str                 # relative to the walked root
    abs_path: str
    size_bytes: int
    lines: int
    extension: str

    def to_dict(self) -> dict:
        return {"path": self.path, "size_bytes": self.size_bytes,
                "lines": self.lines, "extension": self.extension}


def walk(root: str, *, include_hidden: bool = False, max_files: int = 2000) -> List[FileEntry]:
    """Deterministic (sorted) file walk over ``root``."""
    entries: List[FileEntry] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if (include_hidden or not d.startswith(".")) and d not in IGNORE_DIRS
        )
        for fname in sorted(filenames):
            if not include_hidden and fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in TEXT_EXTENSIONS:
                continue
            abs_path = os.path.join(dirpath, fname)
            try:
                size = os.path.getsize(abs_path)
                with open(abs_path, "rb") as fh:
                    lines = fh.read().count(b"\n") + 1
            except OSError:
                continue
            rel = os.path.relpath(abs_path, root)
            entries.append(FileEntry(path=rel, abs_path=abs_path, size_bytes=size,
                                     lines=lines, extension=ext))
            if len(entries) >= max_files:
                return entries
    return entries
