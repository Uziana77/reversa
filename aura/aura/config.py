"""Run configuration for AURA pipeline runs.

Everything that varies between an experiment run lives here: the LLM
provider and model, ablation switches (A0-A3), modernization mode and
target language, and safety limits for sandboxed execution.
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Ablation configuration (synopsis Table 7)
# ---------------------------------------------------------------------------
#   A0  full AURA (reference)
#   A1  no Dynamic Evidence Agent — rules keep static confidence only
#   A2  no AST / call-graph / CRUD context — the LLM sees raw files
#   A3  no BSG gate — the Transformer consumes all extracted rules
ABLATION_CONFIGS = {
    "A0": {"enable_dynamic": True, "enable_static_context": True, "enable_bsg_gate": True},
    "A1": {"enable_dynamic": False, "enable_static_context": True, "enable_bsg_gate": True},
    "A2": {"enable_dynamic": True, "enable_static_context": False, "enable_bsg_gate": True},
    "A3": {"enable_dynamic": True, "enable_static_context": True, "enable_bsg_gate": False},
}

MODERNIZATION_MODES = ("in_place", "migration")


@dataclass
class RunConfig:
    """Full configuration of one pipeline run."""

    # --- identity -----------------------------------------------------------
    run_id: str = "run"
    seed: int = 0

    # --- LLM ----------------------------------------------------------------
    provider: str = "offline"          # "offline" | "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_llm_calls: int = 400           # hard cap per run (cost control)
    request_timeout: float = 120.0

    # --- ablation -----------------------------------------------------------
    enable_dynamic: bool = True
    enable_static_context: bool = True
    enable_bsg_gate: bool = True

    # --- modernization ------------------------------------------------------
    modernization_mode: str = "migration"   # "in_place" | "migration"
    migration_target: str = "python"        # "python" | "java" | "go"

    # --- safety limits ------------------------------------------------------
    sandbox_timeout_s: float = 10.0
    sandbox_memory_mb: int = 512
    sandbox_max_steps: int = 2_000_000      # interpreter step budget
    max_retries: int = 3                    # protocol rule 2 (self-check retries)

    # --- paths --------------------------------------------------------------
    workspace: str = ""                     # filled by the runner
    output_dir: str = ""

    extra: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    @classmethod
    def from_ablation(cls, code: str, **kwargs) -> "RunConfig":
        if code not in ABLATION_CONFIGS:
            raise ValueError(f"unknown ablation config {code!r}; expected one of {sorted(ABLATION_CONFIGS)}")
        cfg = cls(**kwargs)
        for k, v in ABLATION_CONFIGS[code].items():
            setattr(cfg, k, v)
        cfg.extra["ablation"] = code
        return cfg

    @property
    def ablation_code(self) -> str:
        return self.extra.get("ablation", "A0")

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        return d

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str) -> "RunConfig":
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


def load_api_key() -> Optional[str]:
    """Read the OpenAI API key from the environment or aura/.env.

    The key is used only in-memory for HTTP calls; it is never written to
    result artefacts, logs or version control (see .gitignore).
    """
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(here, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
    return None
