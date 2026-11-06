"""Spec-driven codegen renderer tests."""

from aura.skills.codegen import (
    _render_atom,
    _render_effect,
    _render_expr,
    _render_guard,
    generate_python_from_bsg,
)


def test_guard_equality_and_compound():
    assert _render_guard("ALARM_HORN = ON AND HORN_SILENCE = 1") == \
        '(_eq(s.get("ALARM_HORN"), "ON") and _eq(s.get("HORN_SILENCE"), 1))'
    assert _render_guard("PRESSURE > 200") == '((s.get("PRESSURE") or 0) > 200)'
    assert _render_guard("NOT VENT-OPEN = 1 OR MODE = 2") == \
        '((not _eq(s.get("VENT-OPEN"), 1)) or _eq(s.get("MODE"), 2))'


def test_guard_unparseable_is_none():
    assert _render_guard("some prose that cannot parse") is None
    assert _render_atom("") is None
    assert _render_guard("") is None


def test_guard_in_list():
    r = _render_guard("MODE IN [1, 2]")
    assert r == "_eq_any(s.get(\"MODE\"), [1, 2])"


def test_effects():
    assert _render_effect("SET ALARM_HORN TO OFF") == 's["ALARM_HORN"] = 0'
    assert _render_effect("SET ALARM_HORN TO ON") == 's["ALARM_HORN"] = 1'
    assert _render_effect("VENT-OPEN = 1") == 's["VENT-OPEN"] = 1'
    assert _render_effect("PAY-STATUS = 'P'") == 's["PAY-STATUS"] = \'P\'' 
    assert _render_effect("TOTAL-AMT = TOTAL-AMT + REC_AMOUNT") == \
        's["TOTAL-AMT"] = ((s.get("TOTAL-AMT") or 0) + (s.get("REC_AMOUNT") or 0))'
    assert _render_effect("unrenderable prose") is None


def test_expr_rejects_comparisons():
    assert _render_expr("A > B") is None
    assert _render_expr("A + 2") == "((s.get(\"A\") or 0) + 2)"


def test_generate_python_from_bsg_executes():
    bsg = {"nodes": [
        {"id": "N1", "operation": "set horn", "preconditions": ["HORN_SILENCE = 1"],
         "postconditions": ["SET ALARM_HORN TO OFF"], "rule_ids": ["R1"],
         "confidence_state": "confirmed_both"},
        {"id": "N2", "operation": "blocked node", "blocked": True,
         "block_reason": "contradicted", "rule_ids": [], "preconditions": [],
         "postconditions": []},
    ]}
    rules = {"R1": {"statement": "horn clears on silence",
                    "contract": {"given": {"HORN_SILENCE": 1}, "expect": {"ALARM_HORN": 0}}}}
    out = generate_python_from_bsg("unit", bsg, rules)
    src = out["files"][0]["content"]
    assert "SKIPPED (blocked_on_human)" in src
    ns = {}
    exec(compile(src, "gen.py", "exec"), ns)
    assert ns["run"]({"HORN_SILENCE": 1})["ALARM_HORN"] == 0
    # precondition not met -> node does not fire, no exception
    assert ns["run"]({"HORN_SILENCE": 0}).get("ALARM_HORN") is None
    # wildcard expectations are never rendered as assignments
    rules2 = {"R1": {"statement": "x", "contract": {"given": {}, "expect": {"Y": "changed"}}}}
    out2 = generate_python_from_bsg("unit2", bsg, rules2)
    assert 's["Y"] = "changed"' not in out2["files"][0]["content"]
