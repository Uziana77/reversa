# AURA Benchmark (AURA-Bench)

Evaluation benchmark for the AURA framework, prepared per synopsis §6.6
with **one small change**: repository languages are extended from
`{Python, Java}` to `{COBOL, Go, Java, React/JavaScript}` (stakeholder
request), plus the two hand-built legacy-dialect corpora.

## Units

| Unit | Language | Domain | Kind | Rules (gold) | Source |
|------|----------|--------|------|--------------|--------|
| `dialects/interlock` | ILG (invented) | industrial interlock safety | legacy-dialect corpus | ≥15 | hand-built, grammar-first |
| `dialects/reportscript` | RPT (invented) | batch report scripting | legacy-dialect corpus | ≥15 | hand-built, grammar-first |
| `projects/cobol_payroll` | COBOL | payroll processing | legacy-style system | ≥15 | hand-built |
| `projects/go_inventory` | Go | warehouse inventory | legacy-style system | ≥15 | hand-built |
| `projects/java_billing` | Java | telecom billing | legacy-style system | ≥15 | hand-built |
| `projects/react_orders` | JavaScript/React | order-entry UI logic | legacy-style system | ≥15 | hand-built |

## Ground truth (correct by construction)

For every unit the ground truth is authored **before** the code:

1. `grammar.ebnf` — the exact grammar (dialect corpora only);
2. `reference/rules.json` — the business rules with pre/post-conditions and
   given/expect contract pairs;
3. `reference/docs.md` — hierarchical reference documentation
   (function/unit, module, system) — the text-similarity reference;
4. `reference/glossary.json` — identifier → meaning terms (completeness);
5. `tests/golden.json` — golden behaviour cases (input → expected state).

Every contract pair is *mechanically verified* against the code by
`scripts/validate_ground_truth.py` (it executes each `given` through the
unit's harness and asserts the `expect` fields), so "correct by
construction" is enforced, not assumed.

## Realistic undocumented conditions

`scripts/prepare_dataset.py` reproduces the synopsis §6.6 procedure: it
extracts the reference material and then produces a **stripped working
copy** (`work/`) with all comments and documentation removed. The AURA
pipeline runs only on `work/` — never on `src/`.

## Safety-gate attacks

`attacks/injected_false_rules.json` (dialect corpora) contains ~10
deliberately false rules per corpus, injected into the RuleInventory by the
experiment runner. The safety-gate check reports (a) how many are labelled
`contradicted`, and (b) whether any generated code derives from a blocked
node (it must not).

## Harness

`meta.json` declares each unit's black-box execution surface (its "test
suite" API, per the AgentModernize protocol): entry file/symbol, typed
input fields, and the state fields readable after execution. Expected
outputs for equivalence checking are always produced by **executing the
original code**, never by an LLM.
