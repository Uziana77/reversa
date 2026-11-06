"""Metric primitive tests (synopsis 6.6)."""

from aura.eval.metrics import (
    bertscore_proxy,
    bleu4,
    identifier_recall,
    rule_captured,
    significant_identifiers,
    spans_overlap,
)


def test_bleu4_perfect_match():
    assert bleu4("total equals base plus tax", "total equals base plus tax") > 0.99


def test_bleu4_penalises_mismatch():
    a = bleu4("the quick brown fox jumps", "the quick brown fox jumps")
    b = bleu4("the quick brown fox jumps", "completely unrelated words here now")
    assert a > b


def test_bleu4_empty():
    assert bleu4("", "x") == 0.0
    assert bleu4("x", "") == 0.0


def test_bertscore_proxy_shape():
    r = bertscore_proxy("gross pay equals base plus overtime",
                        "gross is base plus overtime pay")
    assert set(r) == {"precision", "recall", "f1"}
    assert 0.0 <= r["f1"] <= 1.0
    # paraphrase scores higher than unrelated text
    unrelated = bertscore_proxy("gross pay equals base plus overtime",
                                "shipping zone flat twenty five hundred")
    assert r["f1"] > unrelated["f1"]


def test_identifier_recall():
    res = identifier_recall(["BASE-PAY", "OT-PAY", "tax_bracket"],
                            "Base-Pay is computed; OT-PAY too. Nothing else.")
    assert res["recall"] == round(2 / 3, 4)
    assert "tax_bracket" in res["missed"]


def test_significant_identifiers_filters_stopwords():
    ids = significant_identifiers("The gross pay equals the base plus the tax")
    assert "gross" in ids and "pay" in ids
    assert "the" not in ids and "equals" not in ids


def test_spans_overlap():
    a = {"file": "x.cbl", "line_start": 10, "line_end": 12}
    b = {"file": "x.cbl", "line_start": 12, "line_end": 20}
    c = {"file": "y.cbl", "line_start": 10, "line_end": 12}
    assert spans_overlap(a, b)
    assert not spans_overlap(a, c)
    assert not spans_overlap(a, None)


def test_rule_captured_needs_identifier_and_span():
    gold = {"id": "G1", "statement": "tax is gross times rate over one hundred",
            "source": {"file": "a.cbl", "line_start": 5, "line_end": 5}}
    good = [{"id": "E1", "statement": "tax equals gross * rate / 100",
             "source": {"file": "a.cbl", "line_start": 5, "line_end": 5}}]
    wrong_line = [{"id": "E2", "statement": "tax equals gross * rate / 100",
                   "source": {"file": "a.cbl", "line_start": 90, "line_end": 90}}]
    wrong_words = [{"id": "E3", "statement": "nothing related at all here",
                    "source": {"file": "a.cbl", "line_start": 5, "line_end": 5}}]
    hit, shared = rule_captured(gold, good)
    assert hit and shared
    assert rule_captured(gold, wrong_line)[0] is None
    assert rule_captured(gold, wrong_words)[0] is None
