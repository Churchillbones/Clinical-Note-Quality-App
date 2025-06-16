"""PDQI evaluation service abstractions (Milestone 5).

The services layer depends on this module to obtain PDQI-9 scores using one of
several interchangeable strategies (O3, Nine-Rings, …).  Down-stream callers
work with pure `PDQIScore` domain objects – no knowledge of the underlying LLM
provider leaks beyond this boundary.
"""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from clinical_note_quality.adapters.azure import get_azure_llm_client
from clinical_note_quality.domain import PDQIScore, PDQIDimension
from clinical_note_quality import get_settings

# For backward-compat we reuse existing O3Judge implementation until a full
# rewrite happens in Phase 2.
from grading.o3_judge import score_with_o3  # type: ignore

logger = logging.getLogger(__name__)


@runtime_checkable
class PDQIService(Protocol):
    """Strategy interface used by `GradingService`."""

    def score(self, note: str, *, precision: str = "medium") -> PDQIScore: ...


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------


class O3Strategy(PDQIService):
    """Adapter that delegates to legacy `score_with_o3` helper."""

    def score(self, note: str, *, precision: str = "medium") -> PDQIScore:  # noqa: D401
        raw = score_with_o3(note, model_precision=precision)
        # Normalise values to floats for domain layer
        numeric_scores = {
            k: float(raw[k]) for k in PDQIDimension.numeric_keys() if k in raw
        }
        return PDQIScore(
            scores=numeric_scores,
            summary=raw.get("summary", ""),
            rationale=raw.get("rationale", ""),
        )


class NineRingsStrategy(PDQIService):
    """Placeholder – implemented in Phase 2."""

    def score(self, note: str, *, precision: str = "medium") -> PDQIScore:  # noqa: D401
        raise NotImplementedError("Nine-Rings strategy not yet implemented.")


# ---------------------------------------------------------------------------
# Strategy resolver / factory
# ---------------------------------------------------------------------------

def get_pdqi_service() -> PDQIService:
    """Return the PDQIService implementation configured in settings."""

    settings = get_settings()
    if getattr(settings, "USE_NINE_RINGS", False):
        logger.info("PDQIService: using Nine-Rings strategy")
        return NineRingsStrategy()

    logger.info("PDQIService: using default O3 strategy")
    return O3Strategy() 