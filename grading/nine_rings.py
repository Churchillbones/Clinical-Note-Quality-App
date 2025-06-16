import asyncio
from typing import Dict, Any
import warnings

from agents import NineRingsOrchestrator

warnings.warn(
    "'grading.nine_rings' is deprecated; use 'clinical_note_quality.services.pdqi_service' or new Nine Rings implementation instead.",
    DeprecationWarning,
    stacklevel=2,
)

warnings.warn(
    "'grading.<module>' is deprecated; use 'clinical_note_quality.services.<new>' instead.",
    DeprecationWarning,
    stacklevel=2,
)


async def _evaluate_async(clinical_note: str) -> Dict[str, Any]:
    orchestrator = NineRingsOrchestrator()
    return await orchestrator.evaluate(clinical_note)


def score_with_nine_rings(clinical_note: str) -> Dict[str, Any]:
    """Synchronously obtain PDQI-9 dict using the Nine Rings architecture."""
    return asyncio.run(_evaluate_async(clinical_note)) 