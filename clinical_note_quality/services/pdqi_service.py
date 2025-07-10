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
        
        # Elite Python: Extract enhanced narrative fields
        dimension_explanations = []
        if "dimension_explanations" in raw and isinstance(raw["dimension_explanations"], list):
            from clinical_note_quality.domain import PDQIDimensionExplanation
            for exp_data in raw["dimension_explanations"]:
                if isinstance(exp_data, dict):
                    dimension_explanations.append(PDQIDimensionExplanation(
                        dimension=exp_data.get("dimension", ""),
                        score=float(exp_data.get("score", 0)),
                        narrative=exp_data.get("narrative", ""),
                        evidence_excerpts=exp_data.get("evidence_excerpts", []),
                        improvement_suggestions=exp_data.get("improvement_suggestions", [])
                    ))
        
        return PDQIScore(
            scores=numeric_scores,
            summary=raw.get("summary", ""),
            rationale=raw.get("rationale", ""),
            model_provenance="o3",
            dimension_explanations=dimension_explanations,
            scoring_rationale=raw.get("scoring_rationale", "")
        )


class NineRingsStrategy(PDQIService):
    """Nine Rings strategy that evaluates each PDQI dimension separately using async agents."""

    def __init__(self) -> None:
        from agents.orchestrator import NineRingsOrchestrator
        self._orchestrator = NineRingsOrchestrator()

    def score(self, note: str, *, precision: str = "medium") -> PDQIScore:  # noqa: D401
        """Score using Nine Rings orchestrator with async evaluation."""
        import asyncio
        
        try:
            # Run the async orchestrator in the current event loop
            loop = asyncio.get_running_loop()
            # If we're already in an event loop, run in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._orchestrator.evaluate(note))
                raw_result = future.result()
        except RuntimeError:
            # No event loop running, we can use asyncio.run directly
            raw_result = asyncio.run(self._orchestrator.evaluate(note))
        
        # Convert to domain model format
        numeric_scores = {
            k: float(v) for k, v in raw_result.items() 
            if k in PDQIDimension.numeric_keys() and isinstance(v, (int, float))
        }
        
        return PDQIScore(
            scores=numeric_scores,
            summary=raw_result.get("summary", ""),
            rationale=raw_result.get("rationale", ""),
            model_provenance="nine_rings",
        )


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