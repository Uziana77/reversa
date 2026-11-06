"""The nine AURA agents (synopsis 6.1, Table 4)."""

from .base import Agent, SelfCheckError, spans_of  # noqa: F401
from .ast_analyzer import ASTAnalyzerAgent  # noqa: F401
from .bsg_generator import BSGGeneratorAgent  # noqa: F401
from .documentation import DocumentationGeneratorAgent  # noqa: F401
from .dynamic_evidence import DynamicEvidenceAgent  # noqa: F401
from .equivalence import EquivalenceValidatorAgent  # noqa: F401
from .language_inference import LanguageInferenceAgent  # noqa: F401
from .legacy_analyzer import LegacyAnalyzerAgent  # noqa: F401
from .navigator import CodebaseNavigatorAgent  # noqa: F401
from .transformer import ModernizationTransformerAgent  # noqa: F401

AGENT_REGISTRY = {
    "navigator": CodebaseNavigatorAgent,
    "language_inference": LanguageInferenceAgent,
    "ast_analyzer": ASTAnalyzerAgent,
    "legacy_analyzer": LegacyAnalyzerAgent,
    "dynamic_evidence": DynamicEvidenceAgent,
    "bsg_generator": BSGGeneratorAgent,
    "transformer": ModernizationTransformerAgent,
    "equivalence_validator": EquivalenceValidatorAgent,
    "documentation_generator": DocumentationGeneratorAgent,
}
