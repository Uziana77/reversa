"""Adapter registry — pick the right execution adapter per language."""

from __future__ import annotations

from typing import Optional

from .base import ExecutionAdapter


def _classes():
    from .cobol_adapter import CobolAdapter
    from .dsl_adapter import DialectAdapter
    from .go_adapter import GoAdapter
    from .java_adapter import JavaAdapter
    from .node_adapter import NodeAdapter
    from .python_adapter import PythonAdapter

    return [CobolAdapter, DialectAdapter, GoAdapter, JavaAdapter, NodeAdapter, PythonAdapter]


_ALIASES = {
    "cobol": "cobol", "cobol-copybook": "cobol",
    "interlock": "interlock", "reportscript": "reportscript",
    "ilg": "interlock", "rpt": "reportscript",
    "go": "go",
    "java": "java",
    "javascript": "javascript", "javascript-react": "javascript",
    "typescript": "javascript", "typescript-react": "javascript",
    "python": "python",
}


def get_adapter(language: str, **kwargs) -> Optional[ExecutionAdapter]:
    key = _ALIASES.get((language or "").lower(), (language or "").lower())
    for cls in _classes():
        if key in cls.languages:
            return cls(**kwargs)
    return None


def detect_adapter(path: str, language: str, **kwargs) -> Optional[ExecutionAdapter]:
    return get_adapter(language, **kwargs)
