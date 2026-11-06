"""Experiment runners for the AURA evaluation (synopsis 6.8-6.9).

Matrix (per benchmark unit, 6 units):

* A0-A3 — ablation configurations of the full pipeline
  (see ``aura.config.ABLATION_CONFIGS``);
* S1    — safety-gate experiment: A0 plus ~10 deliberately false rules
  injected into the RuleInventory (attack material per unit);
* B1    — baseline: one single LLM prompt per source file, no agentic
  context (synopsis 6.8);
* B2    — baseline: function-level summarisation model, one call per
  function/chunk, no repo context;
* B3    — baseline: documentation written by software engineers — the
  benchmark's hand-authored ``reference/docs.md``.

Every run writes ``results/<exp>/<unit>/`` (run artefacts + ``score.json``);
``aggregate.py`` folds everything into ``results/summary.{json,md}``.
"""
