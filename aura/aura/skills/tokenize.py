"""Statistical token analysis skill (grammar-inference pass 1, no model call)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

TOKEN_RE = re.compile(
    r"""
    (?P<ident>[A-Za-z_][A-Za-z0-9_\-]*) |
    (?P<number>\d+(?:\.\d+)?) |
    (?P<string>'[^']*'|\"[^\"]*\") |
    (?P<op><=|>=|<>|:=|==|!=|[-+*/<>=:,;()\[\].])
    """,
    re.X,
)

LINE_COMMENT_RE = re.compile(r"(?m)(\*|//|#|--) .*$")

# Prior knowledge offered to the LLM when hypothesising an unknown legacy
# dialect: keywords shared by many business-legacy languages.
COMMON_PRIOR = (
    "IF", "ELSE", "THEN", "END", "WHILE", "FOR", "DO", "PERFORM",
    "MOVE", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE",
    "CALL", "RETURN", "EXIT", "STOP", "GO", "GOTO", "SET",
    "DISPLAY", "PRINT", "WRITE", "READ", "OPEN", "CLOSE",
    "VALUE", "PIC", "OCCURS", "REDEFINES", "WORKING-STORAGE",
    "SELECT", "FROM", "WHERE", "ORDER", "BY", "GROUP",
    "AND", "OR", "NOT", "EQUAL", "GREATER", "LESS", "THAN",
    "PROCEDURE", "DATA", "IDENTIFICATION", "ENVIRONMENT", "DIVISION",
    "SELECT", "ASSIGN", "FILE", "RECORD", "FIELD", "CLASS",
)


def strip_comments(text: str, language: str = "") -> str:
    if language.startswith("cobol") or text.lstrip().upper().startswith("IDENTIFICATION"):
        # COBOL fixed format: '*' in column 7; free format '--'
        out = []
        for line in text.splitlines():
            if len(line) > 6 and line[6] == "*":
                out.append("")
            else:
                out.append(re.sub(r"--.*$", "", line))
        return "\n".join(out)
    return LINE_COMMENT_RE.sub("", text)


def tokenize(text: str) -> List[str]:
    toks = []
    for m in TOKEN_RE.finditer(text or ""):
        toks.append(m.group(0))
    return toks


def token_frequencies(texts: Iterable[str]) -> Counter:
    c: Counter = Counter()
    for t in texts:
        c.update(tokenize(t))
    return c


def ngram_cooccurrence(tokens: List[str], n: int = 3) -> Counter:
    c: Counter = Counter()
    for i in range(len(tokens) - n + 1):
        c[tuple(tokens[i : i + n])] += 1
    return c


def candidate_keywords(texts_by_file: Dict[str, str], *, max_candidates: int = 24) -> Tuple[List[str], List[str]]:
    """Pass 1 of grammar inference: find candidate keywords and block
    delimiters from token frequency and co-occurrence, with no model call.

    A candidate keyword is an uppercase-ish token that is frequent, occurs
    in more than one file where possible, and sits in stable n-gram
    neighbourhoods (low positional entropy).
    """
    freq: Counter = Counter()
    per_file: Dict[str, set] = {}
    bigram: Counter = Counter()
    for fname, text in texts_by_file.items():
        toks = tokenize(strip_comments(text))
        per_file[fname] = set(toks)
        freq.update(toks)
        bigram.update(zip(toks, toks[1:]))

    total = sum(freq.values()) or 1
    candidates: List[str] = []
    for tok, n in freq.most_common():
        if n < 3:
            continue
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", tok):
            # words that are mostly uppercase are keyword-ish; identifiers are mixed
            upper = sum(1 for ch in tok if ch.isupper())
            if upper / max(1, len(tok)) < 0.6 and not tok.isupper():
                continue
            candidates.append(tok)
        elif re.fullmatch(r"[-A-Z]{2,}", tok) and tok not in ("(", ")", ","):
            candidates.append(tok)
        if len(candidates) >= max_candidates:
            break

    # block delimiters: tokens with strong co-occurrence pairing
    pair_score: Dict[str, float] = defaultdict(float)
    for (a, b), n in bigram.items():
        if isinstance(a, str) and isinstance(b, str):
            if a.isalpha() and b.isalpha() and a.isupper() and b.isupper():
                pair_score[a] += n
                pair_score[b] += n

    # delimiters: frequent ALLCAPS tokens that appear at ends/starts of blocks
    delim_candidates = []
    for tok, n in freq.most_common(60):
        if tok.isalpha() and tok.isupper() and n >= 3:
            if tok.startswith("END") or tok in ("PROCEDURE", "DIVISION", "SECTION", "BEGIN"):
                delim_candidates.append(tok)
    return candidates, delim_candidates[:8]
