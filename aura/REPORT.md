# AURA — Agent-based Understanding and Recovery of Applications

Research report and reproduction guide. Everything in this document is
produced by the artefacts in this repository; every number can be
regenerated with the commands in §10.

---

## 1. Research problem

Legacy software carries its business logic implicitly — in control flow,
data transformations and side effects — while documentation, if it
exists, drifts out of sync. This research (synopsis, sections 1–3) asks
whether a **multi-agent LLM framework grounded in program analysis and
execution evidence** recovers that logic more completely and more
traceably than non-agentic LLM baselines, and whether an explicit
**evidence safety gate** keeps confidently-wrong claims out of generated
artefacts.

Research questions (synopsis §5):

| RQ | Question | Primary evidence |
| --- | --- | --- |
| RQ1 | Does rule-level grounding (spans, traceability) improve over baselines? | traceability density, valid-span rate, capture rate |
| RQ2 | What does the BSG confidence model reveal about claim trust? | confidence distribution, open gaps |
| RQ3 | Is recovered knowledge complete and behaviour-preserving? | identifier recall, unit coverage, BLEU/BERTScore, BER |
| RQ4 | Cost, and does the safety gate stop false rules? | LLM ledger, injected-false-rule block rate, blocked-node code leak |

## 2. The AURA framework

Nine agents cooperate over one shared pipeline state
(`aura/state.py`, `aura/pipeline.py`), each owning exactly one artefact
(protocol Table 3) and self-checking schema/provenance before commit
(control rules 1–2, retries ≤ 3 then escalate):

| Agent | Artefact | Role |
| --- | --- | --- |
| Codebase Navigator | RepoMap | file walk, language detection, dependency edges |
| Language Inference | GrammarHypothesis | statistical + LLM hypothesis for unknown dialects |
| AST Analyzer | ASTMap | units, conditions, assignments, call graph, CRUD |
| Legacy Analyzer | RuleInventory | candidate business rules with spans + contracts |
| Dynamic Evidence | EvidenceReport | executes contracts in sandboxes → confirmed / contradicted / unresolved |
| BSG Generator | BSG | Behavioural Specification Graph, six confidence states |
| Modernization Transformer | ModernizedCode | spec-driven generation with REVIEW/TODO/SKIPPED markers |
| Equivalence Validator | EquivalenceReport | contract + differential tests → BER, testable share |
| Documentation Generator | Documentation | rendered docs, audit trail, BSG graph |

**Confidence fusion** (`state.fuse_confidence`): `confirmed_both`,
`confirmed_static`, `confirmed_dynamic`, `inferred`, `contradicted`,
`gap`; contradicted rules become `blocked_on_human` nodes and the
Transformer never generates from them — this is the **evidence safety
gate** (synopsis §6.1). When execution contradicts a claim, the system
produces a counterexample and escalates instead of guessing.

**Execution adapters** (`aura/skills/adapters/`): real toolchains first
(`go run`, `javac`/`java`, `node`), bundled deterministic subset
interpreters as fallbacks — `cobolite` (COBOL), `dsl_interp`
(reportscript/interlock dialects), `gosim` (Go subset), `javasim` (Java
subset). The fallbacks are cross-validated against the real toolchains in
CI (`bench/scripts/validate_ground_truth.py` under golang-go + Temurin +
Node), so dynamic evidence always has a safe execution path, and rules
without one are labelled `unresolved`, never `contradicted`.

## 3. Benchmark

Six legacy units under `bench/`, every one **correct by construction**
(authored code + ground truth together) **and mechanically verified**:
every rule contract and golden test is executed against the real code by
`bench/scripts/validate_ground_truth.py` — **242/242 checks pass**.

| Unit | Language | Gold rules | False rules | Golden tests | Checks |
| --- | --- | --- | --- | --- | --- |
| interlock | ILG dialect (grammar-first) | 32 | 10 | 14 | 56 |
| reportscript | RPT dialect (grammar-first) | 17 | 10 | 10 | 37 |
| cobol_payroll | COBOL | 20 | 10 | 11 | 41 |
| go_inventory | Go | 18 | 10 | 9 | 37 |
| java_billing | Java | 17 | 10 | 10 | 37 |
| react_orders | JavaScript (React) | 15 | 10 | 9 | 34 |

Each unit carries `meta.json` (per-file harnesses), `reference/`
(rules.json with anchors + given/expect contracts, docs.md,
glossary.json), `tests/golden.json`, and `attacks/injected_false_rules.json`
— deliberately wrong rules for the safety-gate experiment. Contract
semantics are locked (`_outputs` / `_no_outputs` containment keys;
variants are differential-only and non-circular). `bench/scripts/
prepare_dataset.py` materialises pristine `work/` copies; attack material
enters only through `RunConfig.extra["injected_rules"]`, never as files
the pipeline could read.

## 4. Metrics (synopsis Table 6)

Implemented self-contained in `aura/eval/`:

* **rule capture** — a gold rule counts as captured when an extracted
  rule's span overlaps the gold anchor span **and** both share ≥ 1
  significant identifier (right line + wrong semantics is not a capture);
* **statement quality** — BLEU-4 (self-implemented) and a BERTScore-style
  soft alignment over LSA token embeddings (numpy SVD);
* **documentation quality** — the same two scores against the
  ground-truth `docs.md`, plus glossary identifier recall;
* **completeness** — glossary recall, unit coverage;
* **traceability** — traceability density (rules with source spans) and
  valid-span rate (spans pointing at real lines);
* **confidence distribution** — BSG states per run;
* **equivalence** — BER (passing/testable rules) and testable share;
  "equivalence" means no counterexample was found on generated inputs —
  evidence, not formal proof;
* **safety gate** — injected false rules labelled contradicted (block
  rate), and the invariant "no generated code may come from a blocked
  node" (blocked-node code leak);
* **cost** — LLM calls / tokens from the per-run ledger.

## 5. Experiments

* **A0** full AURA (reference) · **A1** no Dynamic Evidence ·
  **A2** no AST/static context (raw files to the LLM) · **A3** no BSG
  gate (all extracted rules consumed).
* **S1** safety-gate stress: A0 + 10 injected false rules per unit.
* **B1** single-prompt LLM per file, no agentic context · **B2**
  function-level summarisation, one call per function · **B3**
  documentation written by software engineers (the hand-authored
  reference docs).

All eight configurations × six units run with the same harnesses and
scoring. Offline runs use the deterministic heuristic provider
(`aura/llm/offline.py`) — a *stand-in* that lets every stage run
end-to-end without a model; the identical matrix runs against OpenAI
(`gpt-4o-mini`, temperature 0, hard call caps) for the real evaluation.

## 6. Offline results (`results/summary.md`, provider=offline)

Means over the six units:

| exp | capture | docs BERT-F1 | docs glossary | traceability | valid spans | BER | testable | gate block | blocked-node leak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A0 | 0.465 | 0.803 | 0.724 | 1.00 | 1.00 | 0.224 | 0.527 | – | 0 |
| A1 | 0.465 | 0.795 | 0.724 | 1.00 | 1.00 | 0.253 | 1.00 | – | 0 |
| A2 | 0.000 | 0.743 | 0.617 | 0.00 | 0.00 | 0.000 | 0.00 | – | 0 |
| A3 | 0.465 | 0.804 | 0.724 | 1.00 | 1.00 | 0.224 | 0.527 | – | **all blocked nodes** |
| S1 | 0.465 | 0.864 | 0.864 | 1.00 | 1.00 | 0.224 | 0.273 | **1.00** | 0 |
| B1 | – | 0.432 | 0.006 | – | – | – | – | – | – |
| B2 | – | 0.248 | 0.011 | – | – | – | – | – | – |
| B3 | – | 1.000 | 0.943 | – | – | – | – | – | – |

What the offline matrix already demonstrates:

1. **The safety gate works.** S1: all 10 injected false rules per unit
   (60/60) are labelled `contradicted` and blocked — block rate 1.0,
   zero survivors — and no generated code comes from a blocked node.
   The A0/A3 contrast on the invariant is total: A0 leaks 0 of 53
   blocked nodes into generated code; A3 (gate off) leaks all of them.
2. **Structural context matters.** A2 (no AST context) collapses to zero
   extraction/traceability (Wilcoxon A0 vs A2 on capture: p = 0.043,
   rank-biserial = 1.0, n = 6).
3. **Agentic grounding beats non-agentic baselines on documentation
   quality** even with the heuristic stand-in: docs BERTScore-F1 A0 0.80
   vs B1 0.43 vs B2 0.25 (Wilcoxon A0 vs B1/B2 on docs BLEU-4: p = 0.068,
   rank-biserial = 1.0); the human-engineer baseline (B3) sets the
   ceiling at 1.0 by construction.
4. **BER moves with the machinery** (0.22 mean; 0.43–0.67 where the
   dialect interpreters and rendered effects align) but shows no A0/A3
   difference offline, because the heuristic inventories are small and
   the false nodes rarely fire on other rules' variants. The OpenAI
   matrix is the measurement designed to resolve that contrast.

Per-unit A0 capture/BER: interlock 0.72/0.43, reportscript 0.12/0.67,
cobol_payroll 0.00/0.25, go_inventory 0.22/0.00, java_billing 1.00/0.00,
react_orders 0.73/0.00. (Full tables: `results/summary.md`;
per-run scores: `results/<exp>/<unit>/score.json`.)

## 7. OpenAI evaluation protocol

The sandbox used for development blocks `api.openai.com`; the real-model
matrix therefore runs either on a workstation or in CI:

```bash
export OPENAI_API_KEY=sk-...          # never stored in the repo
./experiments/run_openai.sh           # validate + test + matrix + aggregate
```

or push the branch and let `.github/workflows/aura-eval.yml` run the
whole thing on `ubuntu-latest` with golang-go, Temurin 21 and Node 20
installed (which also cross-validates gosim/javasim against the real
compilers). Set the `OPENAI_API_KEY` repository secret and dispatch the
workflow; results upload as the `aura-results` artefact
(`results-openai/summary.md`). Expected cost: **USD 1–3** for the full
48-run matrix at `gpt-4o-mini`, temperature 0, with hard per-run LLM-call
caps.

## 8. Threats to validity and limitations

* **Offline numbers are a stand-in.** The heuristic provider is
  deterministic and non-inventive by design; it under-extracts rules
  (capture 0.47 mean) and cannot write prose, so absolute BLEU/BERT
  scores offline are lower bounds. Conclusions about *model* quality
  come from the OpenAI matrix.
* **Small n.** Six units; Wilcoxon results are reported with effect
  sizes (rank-biserial) as prescribed, not p-values alone.
* **BER is evidence, not proof.** Differential testing over synthesised
  and boundary inputs; untestable and blocked rules are excluded and the
  testable share is always reported next to BER.
* **Human rubric** (synopsis Table 6, RQ4) needs three practitioners on
  blinded outputs; `results/` contains everything a rater needs, but no
  human study was run inside the sandbox.
* **Subset interpreters.** cobolite/gosim/javasim cover the benchmark
  constructs, not whole languages; CI cross-validation against real
  toolchains is part of the protocol.

## 9. Repository map

```
aura/
  aura/            framework: state/protocol, llm providers, skills
                   (tokenize, grammar_infer, inputgen, codegen,
                   adapters: cobolite, dsl_interp, gosim, javasim,
                   python/go/java/node adapters, sandbox)
    agents/        the nine agents
    eval/          metrics + run scoring
  bench/           6-unit benchmark (dialects/ + projects/),
                   scripts/{validate_ground_truth,prepare_dataset}.py
  experiments/     run_matrix.py, baselines.py, aggregate.py, run_openai.sh
  results/         offline matrix + summary.{json,md}
  tests/           pytest suite (metrics, codegen, engines, injection)
  docs/sources/    extracted reference texts
  REPORT.md        this file
```

## 10. Reproduction

```bash
pip install -r requirements.txt          # tree-sitter==0.20.4 pin is required
python bench/scripts/validate_ground_truth.py   # 242 checks
python -m pytest tests -q                       # 27 tests
python -m aura selftest                          # 9 agents end-to-end
python experiments/run_matrix.py --provider offline --out results
python experiments/aggregate.py --results results
# real model: export OPENAI_API_KEY=... && ./experiments/run_openai.sh
```
