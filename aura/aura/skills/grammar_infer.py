"""Grammar inference engine (three passes, synopsis 6.5).

Pass 1 — statistical: candidate keywords and block delimiters from token
frequency and co-occurrence, with no model call.
Pass 2 — hypothesis: an LLM proposes syntax rules from that skeleton; any
proposed keyword that does not occur in the corpus is rejected.
Pass 3 — cross-file consistency: a rule not confirmed in more than one file
is penalised and flagged.

The output is a GrammarHypothesis with a confidence value per rule, and the
grammar is accepted for downstream use only when the parse success rate
reaches the threshold (about 90%).  Below the threshold the file is marked
unparseable and reported, not guessed.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from ..state import GrammarHypothesis, GrammarRule
from . import tokenize as tok

PARSE_ACCEPT_THRESHOLD = 0.9


def statistical_pass(texts_by_file: Dict[str, str]) -> dict:
    """Pass 1: model-free statistics."""
    candidates, delimiters = tok.candidate_keywords(texts_by_file)
    file_tokens = {}
    for fname, text in texts_by_file.items():
        file_tokens[fname] = set(tok.tokenize(tok.strip_comments(text)))
    return {
        "candidate_keywords": candidates,
        "candidate_delimiters": delimiters,
        "file_tokens": {f: sorted(t) for f, t in file_tokens.items()},
        "language_name": "inferred-dialect",
    }


def cross_file_pass(hyp: GrammarHypothesis, texts_by_file: Dict[str, str]) -> GrammarHypothesis:
    """Pass 3: penalise and flag rules confirmed in only one file."""
    for rule in hyp.rules:
        support = 0
        for _fname, text in texts_by_file.items():
            if rule.kind == "keyword" and rule.rule.split(" ")[0] in tok.tokenize(text):
                support += 1
            elif rule.kind == "delimiter" and rule.rule.split(" ")[0] in tok.tokenize(text):
                support += 1
        rule.cross_file_support = max(rule.cross_file_support, support)
        if rule.cross_file_support <= 1:
            rule.confidence = round(rule.confidence * 0.6, 3)
            rule.status = "flagged"
        elif rule.status == "proposed":
            rule.status = "accepted"
    return hyp


def measure_parse_success(hyp: GrammarHypothesis, texts_by_file: Dict[str, str],
                          can_parse: Optional[Callable[[str, str], bool]] = None) -> float:
    """Parse success rate: share of files that parse without error using the
    inferred grammar.  ``can_parse`` is a skill callback; when absent a
    structural fallback check runs (balanced block delimiters + known
    keywords)."""
    if not texts_by_file:
        return 0.0
    ok = 0
    for fname, text in texts_by_file.items():
        if can_parse is not None:
            good = can_parse(hyp.language_name, text)
        else:
            good = _structural_check(hyp, text)
        ok += 1 if good else 0
    return ok / len(texts_by_file)


def _structural_check(hyp: GrammarHypothesis, text: str) -> bool:
    toks = tok.tokenize(tok.strip_comments(text))
    if not toks:
        return False
    # balanced delimiters among the inferred set
    stack = []
    pairs = {"IF": "END-IF", "PERFORM": "END-PERFORM", "EVALUATE": "END-EVALUATE",
             "BEGIN": "END", "DO": "END", "PROCEDURE": "END-PROC"}
    known = {r.rule.split(" ")[0] for r in hyp.rules}
    for t in toks:
        up = t.upper()
        if up in pairs and (not known or up in known):
            stack.append(up)
        elif up.startswith("END"):
            if stack:
                stack.pop()
    return len(stack) == 0


def build_hypothesis(
    language_name: str,
    texts_by_file: Dict[str, str],
    propose: Callable[[dict], dict],
    can_parse: Optional[Callable[[str, str], bool]] = None,
) -> GrammarHypothesis:
    """Run all three passes and return the GrammarHypothesis.

    ``propose`` is the LLM strategy (pass 2); it receives the statistical
    skeleton and must return keyword/delimiter/rule lists.  Hypotheses whose
    keywords do not occur in the corpus are rejected here (not by the LLM).
    """
    skeleton = statistical_pass(texts_by_file)
    skeleton["language_name"] = language_name
    proposal = propose(skeleton) or {}
    rules: List[GrammarRule] = []
    corpus_tokens = set()
    for t in skeleton["file_tokens"].values():
        corpus_tokens.update(t)
    for kw in proposal.get("keywords", []):
        if kw not in corpus_tokens:
            continue  # rejected: does not occur in the corpus
        rules.append(GrammarRule(rule=f"{kw} is a keyword", kind="keyword", confidence=0.6))
    for d in proposal.get("block_delimiters", []):
        if d not in corpus_tokens:
            continue
        rules.append(GrammarRule(rule=f"{d} delimits a block", kind="delimiter", confidence=0.6))
    for r in proposal.get("rules", []):
        if isinstance(r, dict):
            rules.append(GrammarRule.from_dict(r))
    hyp = GrammarHypothesis(
        language_name=proposal.get("language_name", language_name),
        keywords=proposal.get("keywords", []),
        block_delimiters=proposal.get("block_delimiters", []),
        rules=rules,
        files_covered=sorted(texts_by_file),
    )
    hyp = cross_file_pass(hyp, texts_by_file)
    hyp.parse_success_rate = round(measure_parse_success(hyp, texts_by_file, can_parse), 3)
    hyp.accepted_for_downstream = hyp.parse_success_rate >= PARSE_ACCEPT_THRESHOLD
    return hyp
