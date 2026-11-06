"""Metric primitives for AURA evaluation."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was",
    "when", "then", "than", "not", "its", "per", "any", "all", "into",
    "only", "else", "each", "over", "under", "equals", "equal",
}

_SENT_RE = re.compile(r"[.;\n]| (?:and|or|when|while|if) ")


# ---------------------------------------------------------------------------
# tokenisation
# ---------------------------------------------------------------------------


def tokens(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT_RE.split(text or "") if s.strip()]


def significant_identifiers(text: str) -> set:
    return {t for t in tokens(text) if len(t) >= 3 and t not in _STOP and not t.isdigit()}


# ---------------------------------------------------------------------------
# BLEU-4 (self-implemented: clipped n-gram precision + brevity penalty)
# ---------------------------------------------------------------------------


def _ngrams(toks: Sequence[str], n: int) -> Counter:
    return Counter(tuple(toks[i:i + n]) for i in range(len(toks) - n + 1))


def bleu4(candidate: str, reference: str, smooth: float = 1e-9) -> float:
    c = tokens(candidate)
    r = tokens(reference)
    if not c or not r:
        return 0.0
    log_prec = 0.0
    for n in range(1, 5):
        cn, rn = _ngrams(c, n), _ngrams(r, n)
        overlap = sum(min(v, rn[g]) for g, v in cn.items())
        total = max(sum(cn.values()), 1)
        p = (overlap + smooth) / (total + smooth)
        log_prec += math.log(p) / 4.0
    bp = 1.0 if len(c) >= len(r) else math.exp(1.0 - len(r) / max(len(c), 1))
    return bp * math.exp(log_prec)


# ---------------------------------------------------------------------------
# BERTScore-style soft alignment over LSA token embeddings
# ---------------------------------------------------------------------------


def _lsa_embeddings(docs: List[List[str]], k: int = 32):
    """TF vectors of each token, contextualised by truncated SVD of the
    term-document matrix (an LSA embedding analogous to contextual token
    embeddings used by BERTScore)."""
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        return None, None, None
    vocab = sorted({t for doc in docs for t in doc})
    if not vocab:
        return None, None, None
    idx = {t: i for i, t in enumerate(vocab)}
    M = np.zeros((len(vocab), len(docs)), dtype=float)
    for j, doc in enumerate(docs):
        for t, cnt in Counter(doc).items():
            M[idx[t], j] = float(cnt)
    # idf weighting
    df = (M > 0).sum(axis=1)
    idf = np.log((1.0 + len(docs)) / (1.0 + df)) + 1.0
    M = M * idf[:, None]
    try:
        u, s, _ = np.linalg.svd(M, full_matrices=False)
        k = min(k, u.shape[1])
        emb = u[:, :k] * (s[:k] ** 0.5 if k else 1.0)
    except np.linalg.LinAlgError:
        emb = M
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    emb = emb / norms
    return emb, {t: i for i, t in enumerate(vocab)}, np


def bertscore_proxy(candidate: str, reference: str) -> Dict[str, float]:
    """Precision/recall/F1: each token of one text takes its best cosine
    match in the other, over LSA embeddings — the soft alignment that
    makes paraphrases score higher than exact-word overlap alone."""
    c_docs = [tokens(s) for s in sentences(candidate)] or [tokens(candidate)]
    r_docs = [tokens(s) for s in sentences(reference)] or [tokens(reference)]
    c_docs = [d for d in c_docs if d]
    r_docs = [d for d in r_docs if d]
    if not c_docs or not r_docs:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    emb, idx, np = _lsa_embeddings(c_docs + r_docs)
    if emb is None:
        # pure-python fallback: exact-overlap similarity
        cs, rs = set(tokens(candidate)), set(tokens(reference))
        inter = len(cs & rs)
        p = inter / max(len(cs), 1)
        r = inter / max(len(rs), 1)
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        return {"precision": p, "recall": r, "f1": f1}
    c_vecs = [emb[idx[t]] for d in c_docs for t in d]
    r_vecs = [emb[idx[t]] for d in r_docs for t in d]
    sim = np.array([[float(a @ b) for b in r_vecs] for a in c_vecs])
    p = float(sim.max(axis=1).mean())
    r = float(sim.max(axis=0).mean())
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f1}


# ---------------------------------------------------------------------------
# glossary / identifier recall
# ---------------------------------------------------------------------------


def identifier_recall(gold_terms: Iterable[str], extracted_text: str) -> Dict[str, Any]:
    hay = tokens(extracted_text)
    hayset = set(hay)
    terms = [t.lower() for t in gold_terms]
    hit = [t for t in terms if t.replace("_", " ") in extracted_text.lower()
           or t.replace("-", "_") in extracted_text.lower()
           or t.replace("-", "") in hayset
           or all(part in hayset for part in t.replace("-", "_").split("_") if part)]
    return {"recall": round(len(hit) / max(len(terms), 1), 4),
            "hit": hit, "missed": [t for t in terms if t not in hit],
            "total": len(terms)}


# ---------------------------------------------------------------------------
# rule capture
# ---------------------------------------------------------------------------


def spans_overlap(a: Optional[dict], b: Optional[dict]) -> bool:
    if not a or not b:
        return False
    if (a.get("file") or "") != (b.get("file") or ""):
        return False
    a0, a1 = int(a.get("line_start", 0)), int(a.get("line_end", 0))
    b0, b1 = int(b.get("line_start", 0)), int(b.get("line_end", 0))
    return a0 <= b1 and b0 <= a1


def rule_captured(gold: dict, extracted: Sequence[dict]) -> Tuple[Optional[dict], str]:
    """A gold rule is 'captured' when some extracted rule's span overlaps
    the gold span AND both share at least one significant identifier
    (span overlap alone is not enough — the right line with the wrong
    semantics is not a capture)."""
    gold_ids = significant_identifiers(
        " ".join([gold.get("statement", ""),
                  " ".join(gold.get("postconditions", []) or [])]))
    gold_span = gold.get("source") or gold.get("anchor_span")
    for r in extracted:
        span = r.get("source")
        if not spans_overlap(span, gold_span):
            continue
        ext_ids = significant_identifiers(
            " ".join([r.get("statement", ""),
                      " ".join(r.get("postconditions", []) or [])]))
        shared = gold_ids & ext_ids
        if shared:
            return r, sorted(shared)[0]
    return None, ""
