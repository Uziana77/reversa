"""AURA evaluation metrics (synopsis section 6.6).

Self-implemented, dependency-light metrics used to score pipeline runs
against benchmark ground truth:

* rule capture (span overlap + shared significant identifier),
* statement quality: BLEU-4 and a BERTScore-style soft-alignment proxy
  built on LSA token embeddings (numpy),
* glossary identifier recall, unit coverage, traceability density,
  valid-span rate, confidence distribution, gap list,
* behavioural equivalence rate (BER) + testable share from the
  Equivalence report,
* safety-gate counters for injected-false-rule runs,
* cost accounting from the LLM ledger.
"""

from .metrics import (  # noqa: F401
    bleu4,
    bertscore_proxy,
    identifier_recall,
    significant_identifiers,
    spans_overlap,
    rule_captured,
)
from .scoring import score_run, score_matrix  # noqa: F401
