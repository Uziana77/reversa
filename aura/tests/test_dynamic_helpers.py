"""Dynamic-evidence and equivalence helper tests."""

from aura.agents.dynamic_evidence import DynamicEvidenceAgent
from aura.agents.equivalence import _loose_eq, _norm, EquivalenceValidatorAgent
from aura.skills.adapters import Harness


def test_fill_defaults_completes_partial_given():
    h = Harness(language="cobol", entry_file="x.cbl",
                input_fields={"A": "int", "B": "float", "S": "string",
                              "L": "list", "F": "bool"})
    out = DynamicEvidenceAgent._fill_defaults(h, {"A": 7})
    assert out == {"A": 7, "B": 0.0, "S": "", "L": [], "F": False}


def test_expect_holds_outputs_and_wildcards():
    eh = DynamicEvidenceAgent._expect_holds
    state = {"X": 5, "_outputs": ["hello world"]}
    assert eh({"X": 5}, state)
    assert eh({"X": "5"}, state)
    assert not eh({"X": 6}, state)
    assert eh({"_outputs": ["hello"]}, state)
    assert not eh({"_outputs": ["goodbye"]}, state)
    assert eh({"_no_outputs": ["goodbye"]}, state)
    assert not eh({"_no_outputs": ["hello"]}, state)
    assert not eh({"Y": 1}, state)  # key not observable


def test_equivalence_fill_defaults_and_loose_eq():
    h = Harness(language="go", entry_file="i.go",
                input_fields={"n": "int", "name": "string"})
    out = EquivalenceValidatorAgent._fill_defaults(h, {"n": 3})
    assert out == {"n": 3, "name": ""}
    assert _loose_eq(1, 1.0)
    assert _loose_eq("7", 7)
    assert not _loose_eq(1, 2)
    assert _norm(None) == 0
    assert _norm("x") == "x"
