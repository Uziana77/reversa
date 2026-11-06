"""Shared pipeline state, artefact schemas and the agent communication protocol.

Everything the nine AURA agents exchange is a typed JSON artefact with the
envelope defined in the synopsis (Section 6.3).  The :class:`SharedState`
class is the single shared pipeline state; it enforces the five control
rules of the protocol (read/write permissions, append-only versioning,
status handling and downstream consumption of the highest *ok* version).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

ARTEFACT_TYPES = (
    "RepoMap",
    "GrammarHypothesis",
    "ASTMap",
    "RuleInventory",
    "EvidenceReport",
    "BSG",
    "ModernizedCode",
    "EquivalenceReport",
    "Documentation",
)

STATUSES = ("ok", "needs_revision", "blocked_on_human")

# Six BSG confidence states (synopsis 6.1 / 6.3).
CONFIDENCE_STATES = (
    "confirmed_both",
    "confirmed_static",
    "confirmed_dynamic",
    "inferred",
    "contradicted",
    "gap",
)

# Labels produced by the Dynamic Evidence Agent.
DYNAMIC_LABELS = ("confirmed", "contradicted", "unresolved")

# Edge label taxonomy of the Behavioural Specification Graph
# (AgentModernize definition; AURA adopts it unchanged).
BSG_EDGE_LABELS = ("sequence", "conditional", "parallel", "error")

AGENT_NAMES = (
    "navigator",
    "language_inference",
    "ast_analyzer",
    "legacy_analyzer",
    "dynamic_evidence",
    "bsg_generator",
    "transformer",
    "equivalence_validator",
    "documentation_generator",
)

# Table 3: hand-offs.  ``writes`` maps agent -> artefact it owns;
# ``reads`` lists artefacts the agent may read (control rule 1).
HANDOFFS: Dict[str, Dict[str, Any]] = {
    "navigator": {
        "writes": "RepoMap",
        "reads": [],
        "receives_from": [],
    },
    "language_inference": {
        "writes": "GrammarHypothesis",
        "reads": ["RepoMap"],
        "receives_from": ["navigator"],
    },
    "ast_analyzer": {
        "writes": "ASTMap",
        "reads": ["RepoMap", "GrammarHypothesis"],
        "receives_from": ["navigator", "language_inference"],
    },
    "legacy_analyzer": {
        "writes": "RuleInventory",
        "reads": ["ASTMap", "RepoMap"],
        "receives_from": ["ast_analyzer"],
    },
    "dynamic_evidence": {
        "writes": "EvidenceReport",
        "reads": ["RuleInventory", "ASTMap", "RepoMap"],
        "receives_from": ["legacy_analyzer"],
    },
    "bsg_generator": {
        "writes": "BSG",
        "reads": ["RuleInventory", "EvidenceReport", "ASTMap"],
        "receives_from": ["dynamic_evidence"],
    },
    "transformer": {
        "writes": "ModernizedCode",
        "reads": ["BSG", "RuleInventory", "ASTMap", "RepoMap"],
        "receives_from": ["bsg_generator"],
    },
    "equivalence_validator": {
        "writes": "EquivalenceReport",
        "reads": ["BSG", "ModernizedCode", "EvidenceReport", "RuleInventory"],
        "receives_from": ["transformer"],
    },
    "documentation_generator": {
        # Control rule 5: the only agent that reads every artefact.
        "writes": "Documentation",
        "reads": list(ARTEFACT_TYPES),
        "receives_from": ["equivalence_validator"],
    },
}

# ---------------------------------------------------------------------------
# Core schema dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SourceSpan:
    file: str
    line_start: int
    line_end: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SourceSpan":
        return cls(file=d["file"], line_start=int(d["line_start"]), line_end=int(d["line_end"]))


@dataclass
class BusinessRule:
    """One candidate business rule in the RuleInventory."""

    id: str
    statement: str
    kind: str = "explicit"            # explicit | implicit | constraint
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    source: Optional[SourceSpan] = None
    static_confidence: float = 0.5
    extraction_method: str = "llm"    # llm | heuristic | mixed
    # Dynamic-evidence outcome (None until the Dynamic Evidence Agent runs).
    dynamic_label: Optional[str] = None     # confirmed | contradicted | unresolved
    dynamic_reason: str = ""
    dynamic_trace: str = ""
    # Contract pair used later for equivalence checking (given/expect).
    contract: Optional[dict] = None
    false_injection: bool = False     # safety-gate experiment marker

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.to_dict() if self.source else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BusinessRule":
        src = d.get("source")
        d = dict(d)
        d["source"] = SourceSpan.from_dict(src) if src else None
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class GrammarRule:
    rule: str                       # human-readable syntax rule
    kind: str = "syntax"            # keyword | delimiter | block | syntax
    confidence: float = 0.5
    cross_file_support: int = 0     # files in which the rule was confirmed
    status: str = "proposed"        # accepted | penalized | flagged | proposed

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "GrammarRule":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class GrammarHypothesis:
    language_name: str
    keywords: List[str] = field(default_factory=list)
    block_delimiters: List[str] = field(default_factory=list)
    rules: List[GrammarRule] = field(default_factory=list)
    parse_success_rate: float = 0.0
    accepted_for_downstream: bool = False
    files_covered: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rules"] = [r.to_dict() for r in self.rules]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "GrammarHypothesis":
        d = dict(d)
        d["rules"] = [GrammarRule.from_dict(r) for r in d.get("rules", [])]
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class BSGrule:
    pass  # (placeholder kept out; BSG nodes carry rule ids)


@dataclass
class BSGNode:
    id: str
    operation: str
    rule_ids: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    invariants: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    error_behavior: str = ""
    confidence_state: str = "inferred"
    confidence: float = 0.5
    blocked: bool = False
    block_reason: str = ""
    source: Optional[SourceSpan] = None
    provenance: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.to_dict() if self.source else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BSGNode":
        src = d.get("source")
        d = dict(d)
        d["source"] = SourceSpan.from_dict(src) if src else None
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class BSGEdge:
    frm: str
    to: str
    label: str = "sequence"     # sequence | conditional | parallel | error

    def to_dict(self) -> dict:
        d = asdict(self)
        d["from"] = d.pop("frm")
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BSGEdge":
        return cls(frm=d["from"], to=d["to"], label=d.get("label", "sequence"))


@dataclass
class Artefact:
    """Envelope for every artefact written to the shared state (6.3)."""

    producer: str
    artefact: str
    version: int
    payload: Any
    provenance: List[dict] = field(default_factory=list)
    confidence: float = 1.0
    status: str = "ok"
    notes: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "producer": self.producer,
            "artefact": self.artefact,
            "version": self.version,
            "payload": self.payload,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Artefact":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


# ---------------------------------------------------------------------------
# Shared state with protocol enforcement
# ---------------------------------------------------------------------------


class ProtocolViolation(RuntimeError):
    """Raised when an agent breaks one of the five control rules."""


class SharedState:
    """The single shared pipeline state.

    All communication goes through :meth:`read` / :meth:`write`; free-form
    agent-to-agent messages do not exist.  Writes are append-only and
    versioned; readers receive the highest version whose status is ``ok``
    (control rule 4).
    """

    def __init__(self, run_config: Any = None) -> None:
        self._artefacts: Dict[str, List[Artefact]] = {t: [] for t in ARTEFACT_TYPES}
        self._current_agent: Optional[str] = None
        self.run_config = run_config
        self.session_log: List[dict] = []
        self.blocked_items: List[dict] = []
        self.escalations: List[dict] = []

    # -- session / audit ----------------------------------------------------
    def log(self, agent: str, event: str, detail: Any = None) -> None:
        entry = {"ts": time.time(), "agent": agent, "event": event, "detail": detail}
        self.session_log.append(entry)

    def set_agent(self, agent: Optional[str]) -> None:
        self._current_agent = agent

    # -- write (control rules 1 & 2) ---------------------------------------
    def write(
        self,
        producer: str,
        payload: Any,
        *,
        confidence: float = 1.0,
        status: str = "ok",
        notes: str = "",
        provenance: Optional[List[dict]] = None,
        artefact: Optional[str] = None,
    ) -> Artefact:
        if producer not in HANDOFFS:
            raise ProtocolViolation(f"unknown producer {producer!r}")
        owned = HANDOFFS[producer]["writes"]
        artefact = artefact or owned
        if artefact != owned:
            raise ProtocolViolation(
                f"control rule 1: agent {producer!r} may only write {owned!r}, not {artefact!r}"
            )
        if status not in STATUSES:
            raise ProtocolViolation(f"invalid status {status!r}")
        version = len(self._artefacts[artefact]) + 1
        art = Artefact(
            producer=producer,
            artefact=artefact,
            version=version,
            payload=payload,
            provenance=provenance or [],
            confidence=max(0.0, min(1.0, float(confidence))),
            status=status,
            notes=notes,
        )
        self._artefacts[artefact].append(art)
        self.log(producer, "write", {"artefact": artefact, "version": version, "status": status})
        return art

    # -- read (control rules 1 & 4) ----------------------------------------
    def read(self, consumer: str, artefact: str, *, allow_non_ok: bool = False) -> Optional[Artefact]:
        if consumer not in HANDOFFS:
            raise ProtocolViolation(f"unknown consumer {consumer!r}")
        if artefact not in HANDOFFS[consumer]["reads"]:
            raise ProtocolViolation(
                f"control rule 1: agent {consumer!r} may not read {artefact!r}"
            )
        versions = self._artefacts.get(artefact, [])
        if not versions:
            return None
        if allow_non_ok:
            return versions[-1]
        # Control rule 4: highest version whose status is ok.
        for art in reversed(versions):
            if art.status == "ok":
                return art
        return None

    def read_all(self, artefact: str) -> List[Artefact]:
        return list(self._artefacts.get(artefact, []))

    # -- escalation (control rule 2/3) --------------------------------------
    def escalate(self, item_id: str, reason: str, producer: str) -> None:
        rec = {"item": item_id, "reason": reason, "producer": producer, "ts": time.time()}
        self.escalations.append(rec)
        self.blocked_items.append(rec)
        self.log(producer, "escalate", rec)

    # -- serialisation -------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "artefacts": {t: [a.to_dict() for a in arts] for t, arts in self._artefacts.items()},
            "session_log": self.session_log,
            "escalations": self.escalations,
        }

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str, run_config: Any = None) -> "SharedState":
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        st = cls(run_config)
        for t, arts in data.get("artefacts", {}).items():
            st._artefacts[t] = [Artefact.from_dict(a) for a in arts]
        st.session_log = data.get("session_log", [])
        st.escalations = data.get("escalations", [])
        return st


# ---------------------------------------------------------------------------
# Confidence fusion (synopsis 6.3, rule-based, threshold 0.7)
# ---------------------------------------------------------------------------

STATIC_CONFIDENCE_THRESHOLD = 0.7


def fuse_confidence(static_confidence: float, dynamic_label: Optional[str]) -> str:
    """Return the BSG confidence state for one rule.

    confirmed_both    : static >= 0.7 and execution confirms
    confirmed_static  : static >= 0.7 and execution unresolved
    confirmed_dynamic : static <  0.7 and execution confirms
    inferred          : static <  0.7 and execution unresolved
    contradicted      : execution contradicts (regardless of static score)
    gap               : a code path with no covering rule (set by the caller)
    """
    high = static_confidence >= STATIC_CONFIDENCE_THRESHOLD
    if dynamic_label == "contradicted":
        return "contradicted"
    if dynamic_label == "confirmed":
        return "confirmed_both" if high else "confirmed_dynamic"
    return "confirmed_static" if high else "inferred"


def payload_hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]
