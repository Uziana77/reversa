"""Agent 6 — BSG Generator.

Decides (Table 4): confidence state per node, when to block.  Skills:
fusion rules, graph build.  Fuses the static claims (RuleInventory) and the
dynamic outcomes (EvidenceReport) into a Behavioural Specification Graph
whose nodes carry one of six confidence states.  Confidence fusion is
rule-based, not learned (synopsis 6.3); the exact table is implemented in
:func:`aura.state.fuse_confidence`.

A contradicted rule sets its BSG node to ``blocked_on_human`` (control
rule 3) — downstream generation skips it and never guesses.
"""

from __future__ import annotations

from typing import Any, List, Tuple

from ..state import (BSGEdge, BSGNode, SourceSpan, fuse_confidence,
                     STATIC_CONFIDENCE_THRESHOLD)
from .base import Agent, spans_of


class BSGGeneratorAgent(Agent):
    name = "bsg_generator"
    goal = ("Fuse static claims and dynamic outcomes into a Behavioural "
            "Specification Graph — the trust boundary of the system. Every "
            "rule node carries one of six confidence states; contradicted "
            "rules block generation for their node and escalate as "
            "blocked_on_human while unaffected nodes continue.")

    def canonical_actions(self, context: dict) -> List[dict]:
        return [
            {"action": "fuse_confidence", "args": {"threshold": STATIC_CONFIDENCE_THRESHOLD}},
            {"action": "build_rule_nodes", "args": {}},
            {"action": "detect_gaps", "args": {}},
            {"action": "build_edges", "args": {}},
            {"action": "block_contradicted_nodes", "args": {}},
        ]

    def work(self, context: dict, actions: List[dict]) -> Tuple[Any, float, List[dict]]:
        payloads = context["payloads"]
        rules = (payloads.get("RuleInventory") or {}).get("rules", [])
        findings = {f["rule_id"]: f for f in (payloads.get("EvidenceReport") or {}).get("findings", [])}
        astmap = payloads.get("ASTMap") or {}

        nodes: List[dict] = []
        blocked: List[dict] = []
        for rule in rules:
            finding = findings.get(rule["id"])
            label = finding["label"] if finding else None
            state_name = fuse_confidence(rule.get("static_confidence", 0.5), label)
            node = BSGNode(
                id=f"N-{rule['id']}",
                operation=_operation_of(rule),
                rule_ids=[rule["id"]],
                preconditions=list(rule.get("preconditions", [])),
                postconditions=list(rule.get("postconditions", [])),
                invariants=[],
                inputs=list(rule.get("inputs", [])),
                outputs=list(rule.get("outputs", [])),
                error_behavior="fault" if label == "contradicted" else "",
                confidence_state=state_name,
                confidence=rule.get("static_confidence", 0.5),
                blocked=False,
                source=SourceSpan.from_dict(rule["source"]) if rule.get("source") else None,
                provenance=[rule["source"]] if rule.get("source") else [],
            )
            if state_name == "contradicted":
                node.blocked = True
                node.block_reason = (finding or {}).get("reason", "contradicted by execution")
                blocked.append({"node": node.id, "reason": node.block_reason,
                                "counterexample": (finding or {}).get("cases", [])[:2]})
            nodes.append(node.to_dict())

        # gap nodes: code paths in the AST map with no covering rule
        covered_files = {(rule.get("source") or {}).get("file") for rule in rules}
        gap_nodes = []
        for u in astmap.get("units", []):
            if u["file"] not in covered_files:
                gid = f"N-GAP-{len(gap_nodes) + 1:03d}"
                gap_nodes.append({
                    "id": gid,
                    "operation": f"uncovered code path: {u['symbol']}",
                    "rule_ids": [],
                    "preconditions": [], "postconditions": [], "invariants": [],
                    "inputs": [], "outputs": [], "error_behavior": "",
                    "confidence_state": "gap", "confidence": 0.0,
                    "blocked": True,
                    "block_reason": "gap: code path exists with no covering rule",
                    "source": {"file": u["file"], "line_start": u["line_start"],
                               "line_end": u["line_end"]},
                    "provenance": [],
                })
        nodes.extend(gap_nodes)

        edges = self._edges(nodes)
        dist: dict = {}
        for n in nodes:
            dist[n["confidence_state"]] = dist.get(n["confidence_state"], 0) + 1
        payload = {
            "nodes": nodes,
            "edges": edges,
            "confidence_distribution": dist,
            "blocked_nodes": blocked,
            "gap_nodes": [g["id"] for g in gap_nodes],
            "rule_nodes": len(nodes) - len(gap_nodes),
        }
        ok_share = (dist.get("confirmed_both", 0) + dist.get("confirmed_static", 0)
                    + dist.get("confirmed_dynamic", 0)) / max(1, len(nodes))
        return payload, ok_share, spans_of(payload)

    # ------------------------------------------------------------------
    @staticmethod
    def _edges(nodes: List[dict]) -> List[dict]:
        """Control-flow edges: sequence along source order, conditional when a
        node's precondition guards another node's file region, error from a
        contradicted node to its consumer chain."""
        edges = []
        ordered = sorted(nodes, key=lambda n: ((n.get("source") or {}).get("file", ""),
                                               (n.get("source") or {}).get("line_start", 0)))
        for a, b in zip(ordered, ordered[1:]):
            if (a.get("source") or {}).get("file") == (b.get("source") or {}).get("file"):
                label = "conditional" if b.get("preconditions") else "sequence"
                edges.append({"from": a["id"], "to": b["id"], "label": label})
            else:
                edges.append({"from": a["id"], "to": b["id"], "label": "sequence"})
        for n in nodes:
            if n.get("blocked") and n.get("confidence_state") == "contradicted":
                edges.append({"from": n["id"], "to": "END", "label": "error"})
        return edges

    def schema_check(self, payload: Any) -> Tuple[bool, str]:
        for key in ("nodes", "edges", "confidence_distribution", "blocked_nodes"):
            if key not in payload:
                return False, f"missing {key}"
        for n in payload["nodes"]:
            if n.get("confidence_state") not in ("confirmed_both", "confirmed_static",
                                                 "confirmed_dynamic", "inferred",
                                                 "contradicted", "gap"):
                return False, f"invalid confidence state {n.get('confidence_state')!r}"
            if n.get("blocked") and not n.get("block_reason"):
                return False, f"blocked node {n.get('id')} lacks a reason"
        return True, ""


def _operation_of(rule: dict) -> str:
    stmt = rule.get("statement", "")
    return stmt.split(".")[0][:80] or rule.get("id", "operation")
