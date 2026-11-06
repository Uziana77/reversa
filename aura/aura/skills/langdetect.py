"""Language detection skill: extension map + token heuristics.

The Navigator marks files whose language cannot be identified; those go to
the Language Inference Agent.  Detection never guesses silently: when no
confident match exists the language is ``None`` and the file is flagged.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

EXTENSION_MAP = {
    ".go": ("go", 0.99),
    ".java": ("java", 0.99),
    ".js": ("javascript", 0.95),
    ".jsx": ("javascript-react", 0.95),
    ".ts": ("typescript", 0.95),
    ".tsx": ("typescript-react", 0.95),
    ".py": ("python", 0.99),
    ".cbl": ("cobol", 0.9),
    ".cob": ("cobol", 0.9),
    ".cpy": ("cobol-copybook", 0.8),
    ".jcl": ("jcl", 0.8),
    ".cs": ("csharp", 0.9),
    ".rb": ("ruby", 0.9),
    ".pl": ("perl", 0.8),
    ".sh": ("shell", 0.8),
    ".ilg": (None, 0.0),     # AURA benchmark interlock dialect — no public grammar
    ".rpt": (None, 0.0),     # AURA benchmark report dialect — no public grammar
    # data/document formats are recognised so they never pollute the
    # unknown-language (dialect inference) corpus
    ".json": ("json", 0.95),
    ".md": ("markdown", 0.95),
    ".txt": ("text", 0.9),
    ".csv": ("csv", 0.9),
    ".yaml": ("yaml", 0.9),
    ".yml": ("yaml", 0.9),
    ".xml": ("xml", 0.9),
    ".ebnf": ("ebnf", 0.9),
}

# Keyword fingerprints used when the extension is uninformative.
FINGERPRINTS = [
    ("cobol", [r"IDENTIFICATION\s+DIVISION", r"WORKING-STORAGE\s+SECTION", r"PROCEDURE\s+DIVISION"]),
    ("go", [r"\bpackage\s+\w+", r"\bfunc\s+\w+\s*\("]),
    ("java", [r"\bpublic\s+(static\s+)?(class|void|int|String)\b"]),
    ("javascript", [r"\bfunction\s*\w*\s*\(", r"=>\s*\{", r"\bconst\s+\w+\s*="]),
    ("python", [r"^\s*def\s+\w+\s*\(", r"^\s*import\s+\w+"]),
    ("shell", [r"^#!\s*/bin/(ba)?sh"]),
]


def detect(path: str, text: str = "") -> Tuple[Optional[str], float, str]:
    """Return (language_or_None, confidence, method)."""
    import os

    ext = os.path.splitext(path)[1].lower()
    if ext in EXTENSION_MAP:
        lang, conf = EXTENSION_MAP[ext]
        if lang is not None:
            return lang, conf, "extension"
    # fingerprint pass
    best: Tuple[Optional[str], float, str] = (None, 0.0, "none")
    for lang, pats in FINGERPRINTS:
        hits = sum(1 for p in pats if re.search(p, text, re.M | re.I))
        if hits:
            conf = min(0.95, 0.5 + 0.2 * hits)
            if conf > best[1]:
                best = (lang, conf, "fingerprint")
    return best


def is_unknown(lang: Optional[str], confidence: float) -> bool:
    return lang is None or confidence < 0.5
