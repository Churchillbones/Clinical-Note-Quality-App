"""Heuristic analysis service (Milestone 6).

Provides rule-based quality metrics such as length appropriateness, redundancy,
and structure.  The implementation initially re-uses the existing functions in
`grading.heuristics` to avoid code duplication, but exposes results as typed
`HeuristicResult` domain objects.
"""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from clinical_note_quality.domain import HeuristicResult

from grading.heuristics import (  # Re-use validated logic for now
    calculate_length_score,
    calculate_redundancy_score,
    calculate_structure_score,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class HeuristicService(Protocol):
    """Public interface consumed by GradingService."""

    def analyze(self, note: str) -> HeuristicResult: ...


class DefaultHeuristicService(HeuristicService):
    """Stateless implementation using rule-based metrics."""

    def analyze(self, note: str) -> HeuristicResult:  # noqa: D401
        length_score = calculate_length_score(note)
        redundancy_score = calculate_redundancy_score(note)
        structure_score = calculate_structure_score(note)
        composite = (length_score + redundancy_score + structure_score) / 3
        result = HeuristicResult(
            length_score=round(length_score, 2),
            redundancy_score=round(redundancy_score, 2),
            structure_score=round(structure_score, 2),
            composite_score=round(composite, 2),
            word_count=len(note.split()),
            character_count=len(note),
        )
        logger.debug("Heuristic analysis result: %s", result)
        return result


# Factory --------------------------------------------------------------------

def get_heuristic_service() -> HeuristicService:
    """Return default heuristic service (no settings yet)."""

    return DefaultHeuristicService() 