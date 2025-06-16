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
        return FactualityResult(
            consistency_score=float(raw.get("consistency_score", 0)),
            claims_checked=int(raw.get("claims_checked", 0)),
            summary=raw.get("summary", ""),
            claims=raw.get("claims", []),
        )


# Factory --------------------------------------------------------------------

def get_factuality_service() -> FactualityService:
    """Return default factuality service (agent path later)."""

    # Placeholder – inspect settings once async agent path exists
    return O3FactualityService() 