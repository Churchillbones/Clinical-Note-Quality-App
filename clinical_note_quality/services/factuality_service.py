"""Factuality assessment service (Milestone 6).

Phase-1 provides a thin wrapper around the existing synchronous O3-based
implementation.  Async agent-based analysis will migrate here in Phase-2.
"""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from clinical_note_quality.domain import FactualityResult
from clinical_note_quality import get_settings

from grading.factuality import analyze_factuality  # type: ignore

logger = logging.getLogger(__name__)


@runtime_checkable
class FactualityService(Protocol):
    """Interface for assessing factual consistency."""

    def assess(self, note: str, transcript: str = "", *, precision: str = "medium") -> FactualityResult: ...


class O3FactualityService(FactualityService):
    """Delegates to legacy `analyze_factuality` (sync)."""

    def assess(self, note: str, transcript: str = "", *, precision: str = "medium") -> FactualityResult:  # noqa: D401,E501
        raw = analyze_factuality(note, encounter_transcript=transcript, model_precision=precision)
        
        # Enhanced type-safe extraction with validation
        consistency_score = raw.get("consistency_score", 0)
        claims_checked = raw.get("claims_checked", 0)
        summary = raw.get("summary", "")
        claims = raw.get("claims", [])
        consistency_narrative = raw.get("consistency_narrative", "")
        claims_narratives = raw.get("claims_narratives", [])
        
        # Type validation and conversion following elite Python standards
        return FactualityResult(
            consistency_score=float(consistency_score) if isinstance(consistency_score, (int, float)) else 0.0,
            claims_checked=int(claims_checked) if isinstance(claims_checked, (int, float)) else 0,
            summary=str(summary) if summary is not None else "",
            claims=claims if isinstance(claims, list) else [],
            consistency_narrative=str(consistency_narrative) if consistency_narrative else "",
            claims_narratives=claims_narratives if isinstance(claims_narratives, list) else [],
        )


# Factory --------------------------------------------------------------------

def get_factuality_service() -> FactualityService:
    """Return default factuality service (agent path later)."""

    # Placeholder – inspect settings once async agent path exists
    return O3FactualityService() 