"""Bundled execution-engine semantics tests (gosim, javasim, cobolite)."""

from aura.skills.adapters.gosim import run_go
from aura.skills.adapters.javasim import run_java


GO_PROG = """
package main

func calc(a int, b int) (int, string) {
    q := a / b
    r := a % b
    var label string
    if q > 2 {
        label = "BIG"
    } else {
        label = "SMALL"
    }
    return q + r, label
}
"""

JAVA_PROG = """
public class Calc {
    public int a;
    public int b;
    public int quotient;
    public String label;

    public void compute() {
        quotient = a / b;
        label = "SMALL";
        if (quotient > 2) {
            label = "BIG";
        }
        if (a == 9 && b == 4) {
            label = "NINE";
        }
    }
}
"""


def test_gosim_int_division_truncates():
    r = run_go(GO_PROG, {"a": 9, "b": 4}, "calc")
    # 9/4 = 2 remainder 1 -> q + r = 3, q > 2 is false -> SMALL
    assert r["state"] == {"ret0": 3, "ret1": "SMALL"}


def test_gosim_branches():
    r = run_go(GO_PROG, {"a": 20, "b": 4}, "calc")
    # 20/4 = 5, r = 0 -> 5, BIG
    assert r["state"] == {"ret0": 5, "ret1": "BIG"}


def test_gosim_divide_by_zero_faults():
    import pytest
    from aura.skills.adapters.gosim import GoRuntimeError
    with pytest.raises(GoRuntimeError):
        run_go(GO_PROG, {"a": 1, "b": 0}, "calc")


def test_javasim_field_driven():
    r = run_java(JAVA_PROG, {"a": 9, "b": 4}, entry="compute")
    assert r["state"]["quotient"] == 2
    assert r["state"]["label"] == "NINE"


def test_javasim_branch():
    r = run_java(JAVA_PROG, {"a": 20, "b": 4}, entry="compute")
    assert r["state"]["quotient"] == 5
    assert r["state"]["label"] == "BIG"
    r2 = run_java(JAVA_PROG, {"a": 4, "b": 4}, entry="compute")
    assert r2["state"]["label"] == "SMALL"


def test_cobolite_round_down_and_evaluate_thru():
    from aura.skills.adapters.cobolite import run_cobol
    prog = """
IDENTIFICATION DIVISION.
PROGRAM-ID. T.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 X PIC 9(4)V9(2) VALUE 0.
01 Y PIC 9(4)V9(2) VALUE 0.
PROCEDURE DIVISION.
MAIN.
    COMPUTE X = 10 / 3
    EVALUATE Y
        WHEN 0 THRU 100
            MOVE 5 TO X
        WHEN OTHER
            MOVE 7 TO X
    END-EVALUATE
    STOP RUN.
"""
    r = run_cobol(prog, {})
    assert float(r["state"]["X"]) == 5.0  # Y=0 falls in first bracket
    assert float(r["state"]["Y"]) == 0.0
