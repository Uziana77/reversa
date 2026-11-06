"""AURA skills — deterministic, reusable, stateless capabilities.

A skill has no goal of its own, does no planning, keeps no state and
returns the same output for the same input (synopsis 6.4).  Everything in
this package is unit-testable in isolation.
"""

from . import (  # noqa: F401
    callgraph,
    codegen,
    crud,
    filewalk,
    grammar_infer,
    heuristics,
    inputgen,
    langdetect,
    provenance,
    render,
    sandbox,
    tokenize,
)
