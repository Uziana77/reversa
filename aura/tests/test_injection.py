"""Attack-injection hook and dataset preparation tests."""

import json
import os

from aura.agents.legacy_analyzer import LegacyAnalyzerAgent
from aura.config import RunConfig


def _unit_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "bench", "dialects", "reportscript")


def test_injected_rules_marked_and_anchored():
    unit = _unit_dir()
    attack = json.load(open(os.path.join(unit, "attacks", "injected_false_rules.json")))
    cfg = RunConfig.from_ablation("A0", provider="offline")
    cfg.extra["injected_rules"] = attack["rules"][:2]
    agent = LegacyAnalyzerAgent.__new__(LegacyAnalyzerAgent)
    out = agent._injected_rules({"config": cfg, "root": unit})
    assert [r["id"] for r in out] == ["INJ-001", "INJ-002"]
    for r in out:
        assert r["false_injection"] is True
        assert r["extraction_method"] == "injected"
        assert r["source"] and r["source"]["file"].startswith("corpus/")
        assert r["contract"]["given"]


def test_injection_without_config_is_empty():
    agent = LegacyAnalyzerAgent.__new__(LegacyAnalyzerAgent)
    assert agent._injected_rules({"config": None, "root": "."}) == []


def test_prepare_dataset_excludes_attack_material(tmp_path):
    import sys

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(os.path.dirname(here), "bench", "scripts"))
    import prepare_dataset

    unit = _unit_dir()
    manifest = prepare_dataset.build_work(unit, out_name="work_testprobe",
                                          attack_file="attacks/injected_false_rules.json")
    dst = os.path.join(unit, "work_testprobe")
    try:
        names = []
        for dirpath, _, files in os.walk(dst):
            names += files
        assert "_injected_rules.json" not in names
        assert "work_manifest.json" in names
        assert any(n.endswith(".rpt") for n in names)
        assert manifest.get("attack") == "attacks/injected_false_rules.json"
    finally:
        import shutil
        shutil.rmtree(dst, ignore_errors=True)


def test_resolve_anchor_finds_real_line():
    agent = LegacyAnalyzerAgent.__new__(LegacyAnalyzerAgent)
    unit = _unit_dir()
    span = agent._resolve_anchor(unit, "TOTAL-AMT")
    assert span and span["file"].startswith("corpus/")
    assert agent._resolve_anchor(unit, "no such anchor anywhere zzz") is None
