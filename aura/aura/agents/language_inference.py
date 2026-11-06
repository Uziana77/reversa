"""Agent 2 — Language Inference Agent.

Decides (Table 4): which token patterns to promote to rules, when
confidence is sufficient.  Skills: frequency analysis, n-gram
co-occurrence, LLM rule proposal, cross-file grep.  Implements the
three-pass grammar inference of synopsis 6.5 and writes the
GrammarHypothesis artefact.
"""

from __future__ import annotations

import json
import os
from typing import Any, List, Tuple

from ..skills import grammar_infer
from ..state import GrammarHypothesis
from .base import Agent


class LanguageInferenceAgent(Agent):
    name = "language_inference"
    goal = ("For every file whose language could not be identified, infer a "
            "working grammar in three passes: statistical (no model), LLM "
            "hypothesis, cross-file consistency. Accept the grammar only "
            "above the parse-success threshold; otherwise mark unparseable.")

    def canonical_actions(self, context: dict) -> List[dict]:
        return [
            {"action": "statistical_pass", "args": {}},
            {"action": "llm_hypothesis_pass", "args": {}},
            {"action": "cross_file_consistency_pass", "args": {}},
            {"action": "measure_parse_success", "args": {}},
        ]

    def work(self, context: dict, actions: List[dict]) -> Tuple[Any, float, List[dict]]:
        payloads = context["payloads"]
        repomap = payloads.get("RepoMap") or {}
        root = context["run"]["root"]
        unknown = repomap.get("unknown_language_files", [])
        hypotheses = []
        if unknown:
            texts = {}
            for rel in unknown:
                try:
                    with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
                        texts[rel] = fh.read(200_000)
                except OSError:
                    continue
            if texts:
                exts = {os.path.splitext(p)[1] for p in texts}
                lang_name = "inferred-dialect" + ("(" + ",".join(sorted(exts)) + ")" if exts else "")

                def propose(skeleton: dict) -> dict:
                    return self.provider.complete_json(
                        "grammar.hypothesize",
                        system=("You are the AURA Language Inference Agent. Given a statistical "
                                "token skeleton of an unknown legacy dialect, propose its "
                                "keywords, block delimiters and syntax rules."),
                        user="CONTEXT_JSON: " + json.dumps({
                            "skeleton": {k: v for k, v in skeleton.items() if k != "file_tokens"},
                            "corpus": {"file_tokens": skeleton.get("file_tokens", {})},
                            "language_name": lang_name,
                            "known_prior": grammar_infer.tok.COMMON_PRIOR,
                        }, default=str),
                        schema_hint={"language_name": "str", "keywords": ["str"],
                                     "block_delimiters": ["str"],
                                     "rules": [{"rule": "str", "kind": "keyword|delimiter|syntax",
                                                "confidence": 0.0}]},
                        fallback={"language_name": lang_name, "keywords": [],
                                  "block_delimiters": [], "rules": []},
                    ).data or {}

                hyp = grammar_infer.build_hypothesis(lang_name, texts, propose)
                hypotheses.append(hyp.to_dict())
        payload = {
            "hypotheses": hypotheses,
            "files_without_grammar": [f for f in unknown
                                      if not hypotheses or not hypotheses[0].get("accepted_for_downstream")],
            "threshold": grammar_infer.PARSE_ACCEPT_THRESHOLD,
        }
        conf = max((h.get("parse_success_rate", 0.0) for h in hypotheses), default=1.0)
        prov = [{"file": f, "line_start": 1, "line_end": 1} for f in unknown[:20]]
        return payload, conf, prov

    def schema_check(self, payload: Any) -> Tuple[bool, str]:
        if "hypotheses" not in payload:
            return False, "missing hypotheses"
        for h in payload["hypotheses"]:
            for key in ("language_name", "keywords", "rules", "parse_success_rate"):
                if key not in h:
                    return False, f"hypothesis missing {key}"
        return True, ""

    def provenance_check(self, payload: Any, provenance: Optional[List[dict]] = None) -> Tuple[bool, str]:
        if not payload.get("hypotheses") and not payload.get("files_without_grammar"):
            return True, ""   # nothing to infer: vacuously provenance-free
        return super().provenance_check(payload, provenance)
