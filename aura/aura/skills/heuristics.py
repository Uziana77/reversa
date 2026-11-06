"""Deterministic heuristics used by the offline LLM provider.

These are *skills* in the AURA vocabulary: pure functions, no state, same
output for the same input.  The offline provider's "reasoning" is exactly
these functions; swapping in a real LLM replaces them without touching any
agent code.

The central piece is rule synthesis: turning structural facts (conditions,
effects, calls, CRUD operations with source spans) into candidate business
rules with pre/post-conditions and given/expect contract pairs.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*")
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

# A tiny cross-language prior used by grammar inference (synopsis 6.5):
# common words that appear in many legacy dialects.
COMMON_PRIOR = ["IF", "THEN", "ELSE", "END", "PROC", "PERFORM", "MOVE", "WHILE", "DO", "SET", "GOTO", "WHEN", "EVALUATE"]

STOPWORDS = set(
    """a an and are as at be but by for from has have if in into is it its of on or
    that the this to was were will with when then else end do done not no true false
    return returns function def var let const new class self this null nil none""".split()
)


# ---------------------------------------------------------------------------
# Identifier / expression utilities
# ---------------------------------------------------------------------------

def extract_identifiers(text: str) -> List[str]:
    seen, out = set(), []
    for m in IDENT.finditer(text or ""):
        tok = m.group(0)
        low = tok.lower()
        if low in STOPWORDS or low in COMMON_PRIOR or len(tok) < 2:
            continue
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def extract_literals(text: str) -> List[str]:
    out = []
    for m in re.finditer(r"'[^']*'|\"[^\"]*\"", text or ""):
        out.append(m.group(0)[1:-1])
    for m in NUMBER.finditer(text or ""):
        out.append(m.group(0))
    return out


def prettify_condition(cond: str) -> str:
    c = (cond or "").strip()
    c = re.sub(r"\s+", " ", c)
    return c


def split_condition_effect(text: str) -> Tuple[str, str]:
    """Split 'IF <cond> THEN <effect>' style statements."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    m = re.match(r"(?is)^(?:IF|WHEN|WHILE)\s+(.+?)\s+(?:THEN|DO)\s+(.+)$", t)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"(?is)^WHEN\s+(.+?)\s*:\s*(.+)$", t)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", t


# ---------------------------------------------------------------------------
# Rule synthesis (Legacy Analyzer offline strategy)
# ---------------------------------------------------------------------------

def synthesize_rules(context: dict) -> List[dict]:
    """Turn an AST digest into candidate business rules.

    Input units look like::

        {"file": ..., "symbol": ..., "kind": ..., "line_start":n, "line_end":n,
         "conditions": [{"text": ..., "line": n, "effect": ...}],
         "assignments": [{"text": ..., "line": n}],
         "calls": [...], "crud": [...]}

    Every rule carries pre/post-conditions, a source span and a given/expect
    contract pair derived from the condition/effect operands, so the Dynamic
    Evidence Agent and the Equivalence Validator can execute it.
    """
    rules: List[dict] = []
    for unit in context.get("units", []):
        fname = unit.get("file", "?")
        symbol = unit.get("symbol", "module")
        for cond in unit.get("conditions", []):
            ctext = prettify_condition(cond.get("text", ""))
            effect = prettify_condition(cond.get("effect", ""))
            if not ctext:
                continue
            line = int(cond.get("line", unit.get("line_start", 1)))
            inputs = extract_identifiers(ctext)
            outputs = extract_identifiers(effect) if effect else []
            statement = f"In {symbol}, if {ctext}" + (f" then {effect}." if effect else " the guarded branch executes.")
            contract = build_contract(ctext, effect, inputs, outputs)
            kind = "explicit" if effect else "implicit"
            rules.append(
                {
                    "statement": statement,
                    "kind": kind,
                    "preconditions": [ctext],
                    "postconditions": [effect] if effect else [f"guarded branch of {symbol} executed"],
                    "inputs": inputs,
                    "outputs": outputs,
                    "source": {"file": fname, "line_start": line, "line_end": line},
                    "static_confidence": confidence_for(ctext, effect),
                    "extraction_method": "heuristic",
                    "contract": contract,
                }
            )
        for asg in unit.get("assignments", []):
            atext = prettify_condition(asg.get("text", ""))
            if not atext or len(extract_identifiers(atext)) < 1:
                continue
            line = int(asg.get("line", unit.get("line_start", 1)))
            lhs, _, rhs = atext.partition("=")
            if not rhs:
                lhs, _, rhs = atext.partition(" becomes ")
            lhs_id = (extract_identifiers(lhs) or ["value"])[0]
            rhs_ids = extract_identifiers(rhs)
            statement = f"In {symbol}, {lhs_id} is computed as {rhs.strip() or atext}."
            contract = build_contract(rhs.strip() or "true", f"{lhs_id} = {rhs.strip() or atext}", rhs_ids, [lhs_id])
            rules.append(
                {
                    "statement": statement,
                    "kind": "constraint",
                    "preconditions": [f"inputs available: {', '.join(rhs_ids) if rhs_ids else 'constant'}"],
                    "postconditions": [f"{lhs_id} = {rhs.strip() or atext}"],
                    "inputs": rhs_ids,
                    "outputs": [lhs_id],
                    "source": {"file": fname, "line_start": line, "line_end": line},
                    "static_confidence": min(0.9, 0.55 + 0.05 * min(len(rhs_ids), 4)),
                    "extraction_method": "heuristic",
                    "contract": contract,
                }
            )
    return rules


def confidence_for(cond: str, effect: str) -> float:
    score = 0.5
    if cond and effect:
        score += 0.25
    if NUMBER.search(cond or "") or NUMBER.search(effect or ""):
        score += 0.1
    if len(extract_identifiers(cond or "")) >= 2:
        score += 0.1
    return round(min(0.92, score), 2)


def build_contract(cond: str, effect: str, inputs: List[str], outputs: List[str]) -> dict:
    """Derive a given/expect pair from a condition/effect pair.

    Given: concrete values for the condition's identifiers (literals used in
    the condition when present, else synthetic defaults). Expect: the effect
    evaluated as a state assignment when possible, else the effect text.
    """
    given: Dict[str, Any] = {}
    for lit in extract_literals(cond):
        # bind literal to nearest compared identifier, else to first free input
        m = re.search(rf"([A-Za-z_][A-Za-z0-9_\-]*)\s*(?:=|==|>=|<=|>|<|IS|EQUALS)\s*{re.escape(lit)}", cond)
        key = m.group(1) if m else (inputs[0] if inputs else "input")
        val: Any = lit
        try:
            val = float(lit) if "." in lit else int(lit)
        except ValueError:
            val = lit
        given[key] = val
    for name in inputs:
        if name not in given:
            given[name] = 1  # synthetic default; boundary variants come later
    expect: Dict[str, Any] = {}
    m = re.match(r"([A-Za-z_][A-Za-z0-9_\-]*)\s*(?:=|becomes)\s*(.+)", effect or "")
    if m:
        lhs, rhs = m.group(1), m.group(2).strip()
        val = evaluate_simple(rhs, given)
        expect[lhs] = val
    else:
        for o in outputs:
            expect[o] = "changed"
    return {"given": given, "expect": expect}


def evaluate_simple(expr: str, env: dict) -> Any:
    """Evaluate a tiny arithmetic expression with identifier substitution.

    Only arithmetic over numbers is evaluated; anything else returns the
    expression text with identifiers substituted, so nothing is invented.
    """
    expr = (expr or "").strip()
    if not expr:
        return None
    substituted = expr
    for name, val in env.items():
        substituted = re.sub(rf"\b{re.escape(name)}\b", str(val), substituted)
    # pure arithmetic?
    if re.fullmatch(r"[-+*/(). 0-9]+", substituted or ""):
        try:
            return eval(substituted, {"__builtins__": {}}, {})  # noqa: S307 — arithmetic-only regex gate
        except Exception:
            return substituted
    # boolean comparisons over numbers
    if re.fullmatch(r"[-+*/(). 0-9<>=!&| ]+", substituted or ""):
        try:
            return bool(eval(substituted, {"__builtins__": {}}, {}))  # noqa: S307
        except Exception:
            return substituted
    return substituted


# ---------------------------------------------------------------------------
# Summarisation (offline strategy)
# ---------------------------------------------------------------------------

def summarize_function(context: dict) -> str:
    sym = context.get("symbol", "this unit")
    lang = context.get("language", "legacy")
    conds = [c.get("text", "") for c in context.get("conditions", [])][:4]
    effects = [c.get("effect", "") for c in context.get("conditions", []) if c.get("effect")][:4]
    asgs = [a.get("text", "") for a in context.get("assignments", [])][:3]
    calls = context.get("calls", [])[:5]
    crud = context.get("crud", [])[:5]
    parts = [f"{sym} ({lang})"]
    if conds:
        parts.append("applies conditions: " + "; ".join(conds))
    if effects:
        parts.append("computes: " + "; ".join(effects))
    if asgs:
        parts.append("maintains state: " + "; ".join(asgs))
    if calls:
        parts.append("calls: " + ", ".join(calls))
    if crud:
        parts.append("data access: " + ", ".join(f"{c.get('op', '?')} {c.get('store', '?')}" for c in crud))
    return ". ".join(parts) + "."


def summarize_system(context: dict) -> dict:
    files = context.get("files", [])
    rules_count = context.get("rules_count", 0)
    crud = context.get("crud", [])
    call_edges = context.get("call_edges", [])
    langs = sorted({f.get("language", "unknown") for f in files})
    overview = (
        f"Legacy system with {len(files)} source files in {', '.join(langs)}. "
        f"{rules_count} candidate business rules were extracted across "
        f"{context.get('unit_count', 0)} analysis units. "
        f"The call graph has {len(call_edges)} edges and the data-access table lists {len(crud)} operations."
    )
    return {"overview": overview}


# ---------------------------------------------------------------------------
# Grammar inference (offline strategy for the hypothesis pass)
# ---------------------------------------------------------------------------

def propose_grammar(context: dict) -> dict:
    """Propose syntax rules from the statistical skeleton produced by the
    Language Inference Agent's first (model-free) pass.

    Rules whose keywords do not occur in the corpus are rejected (pass 2),
    and rules are penalised when confirmed in only one file (pass 3).
    """
    skeleton = context.get("skeleton", {})
    candidates: List[str] = skeleton.get("candidate_keywords", [])
    delimiters: List[str] = skeleton.get("candidate_delimiters", [])
    corpus = context.get("corpus", {})
    file_tokens = corpus.get("file_tokens", {})  # file -> set/list of tokens
    prior = set(context.get("known_prior", COMMON_PRIOR))

    rules: List[dict] = []
    keywords: List[str] = []
    for kw in candidates:
        support = [f for f, toks in file_tokens.items() if kw in toks]
        if not support:
            continue  # reject: does not occur in the corpus
        keywords.append(kw)
        in_prior = kw.upper() in prior
        conf = min(0.95, 0.45 + 0.12 * len(support) + (0.1 if in_prior else 0.0))
        status = "accepted" if len(support) > 1 else "flagged"
        if len(support) == 1:
            conf *= 0.6  # penalised: not confirmed in more than one file
        rules.append(
            {
                "rule": f"{kw} is a keyword"
                + (" (cross-language prior)" if in_prior else " (inferred from frequency/co-occurrence)"),
                "kind": "keyword",
                "confidence": round(conf, 2),
                "cross_file_support": len(support),
                "status": status,
            }
        )
    for d in delimiters:
        support = [f for f, toks in file_tokens.items() if d in toks]
        if not support:
            continue
        rules.append(
            {
                "rule": f"{d} delimits a block",
                "kind": "delimiter",
                "confidence": round(min(0.95, 0.5 + 0.1 * len(support)), 2),
                "cross_file_support": len(support),
                "status": "accepted" if len(support) > 1 else "flagged",
            }
        )
    language_name = context.get("language_name") or skeleton.get("language_name") or "inferred-dialect"
    return {
        "language_name": language_name,
        "keywords": keywords,
        "block_delimiters": delimiters,
        "rules": rules,
    }
