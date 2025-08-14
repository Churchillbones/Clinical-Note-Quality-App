from __future__ import annotations

import logging

from clinical_note_quality.domain import FactualityResult
from clinical_note_quality.services.embedding_service import EmbeddingFactualityService
from clinical_note_quality.services.factuality_service import (
    FactualityService,
    O3FactualityService,
)

logger = logging.getLogger(__name__)


class HybridFactualityService(FactualityService):
    """
    Orchestrates a two-step factuality assessment.

    1.  First, it uses the `EmbeddingFactualityService` to perform a fast
        semantic search and identify sentences in the note that may not be
        supported by the transcript.
    2.  Second, it passes these flagged sentences to the `O3FactualityService`
        for a more detailed, nuanced review, guided by the initial findings.
    """

    def __init__(self) -> None:
        self._embedding_service = EmbeddingFactualityService()
        self._o3_service = O3FactualityService()

    def assess(
        self, note: str, transcript: str = "", *, precision: str = "medium"
    ) -> FactualityResult:
        logger.info("Starting hybrid factuality assessment...")

        # Step 1: Get initial analysis from the embedding service
        logger.info("Step 1: Running embedding-based analysis.")
        embedding_result = self._embedding_service.assess(
            note, transcript, precision=precision
        )

        unsupported_sentences = embedding_result.claims_narratives
        logger.info(
            "Embedding analysis flagged %d sentences as potentially unsupported.",
            len(unsupported_sentences),
        )

        if not unsupported_sentences:
            logger.info(
                "No unsupported sentences found by embedding service. "
                "Returning embedding result directly."
            )
            # If everything is supported, we can save an O3 call.
            # We can return the embedding result directly as it's already very positive.
            return embedding_result

        # Step 2: Get a focused review from the O3 service
        logger.info("Step 2: Running focused O3 analysis.")
        final_result = self._o3_service.assess(
            note,
            transcript,
            precision=precision,
            flagged_sentences=unsupported_sentences,
        )

        logger.info("Hybrid factuality assessment complete.")
        return final_result
