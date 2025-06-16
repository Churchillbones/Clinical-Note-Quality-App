"""Composite grading service (Milestone 7).

Produces a `HybridResult` by orchestrating PDQI, heuristic, and factuality
services while applying weighted aggregation rules defined in settings.
"""
from __future__ import annotations

import logging
from typing import Optional

from clinical_note_quality.domain import HybridResult
from clinical_note_quality import get_settings
from clinical_note_quality.services import (
    get_pdqi_service,
    get_heuristic_service,
    get_factuality_service,
)

logger = logging.getLogger(__name__)


def _numeric_grade(score: float) -> str:
    if score >= 4.5:
        return "A"
    if score >= 3.5:
        return "B"
    if score >= 2.5:
        return "C"
    if score >= 1.5:
        return "D"
    return "F"


class GradingService:  # noqa: D101 – obvious
    def __init__(
        self,
        *,
        settings=None,
        pdqi_service=None,
        heuristic_service=None,
        factuality_service=None,
    ) -> None:
        self.settings = settings or get_settings()
        self.pdqi_service = pdqi_service or get_pdqi_service()
        self.heuristic_service = heuristic_service or get_heuristic_service()
        self.factuality_service = factuality_service or get_factuality_service()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def grade(
        self,
        note: str,
        transcript: str = "",
        precision: str = "medium",
    ) -> HybridResult:  # noqa: D401,E501
        logger.info("GradingService: starting grade pipeline")

        pdqi = self.pdqi_service.score(note, precision=precision)
        heuristics = self.heuristic_service.analyze(note)
        factuality = self.factuality_service.assess(note, transcript, precision=precision)

        hybrid_score = (
            pdqi.average * self.settings.PDQI_WEIGHT
            + heuristics.composite_score * self.settings.HEURISTIC_WEIGHT
            + factuality.consistency_score * self.settings.FACTUALITY_WEIGHT
        )
        hybrid_score = max(1.0, min(5.0, round(hybrid_score, 2)))

        chain_parts = []
        if pdqi.rationale:
            chain_parts.append("PDQI Rationale:\n" + pdqi.rationale.strip())
        if pdqi.summary:
            chain_parts.append("PDQI Summary:\n" + pdqi.summary.strip())
        if factuality.summary:
            chain_parts.append("Factuality Summary:\n" + factuality.summary.strip())
        chain_of_thought = "\n\n".join(chain_parts)

        result = HybridResult(
            pdqi=pdqi,
            heuristic=heuristics,
            factuality=factuality,
            hybrid_score=hybrid_score,
            overall_grade=_numeric_grade(hybrid_score),
            weights_used={
                "pdqi_weight": self.settings.PDQI_WEIGHT,
                "heuristic_weight": self.settings.HEURISTIC_WEIGHT,
                "factuality_weight": self.settings.FACTUALITY_WEIGHT,
            },
            chain_of_thought=chain_of_thought,
        )
        logger.info("GradingService: completed. Score %.2f", hybrid_score)
        return result 