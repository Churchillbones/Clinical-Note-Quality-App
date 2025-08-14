from __future__ import annotations

import asyncio
import logging
from typing import Any

import nltk
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from clinical_note_quality.adapters.azure.async_client import AsyncAzureLLMClient
from clinical_note_quality.domain import FactualityResult
from clinical_note_quality.services.factuality_service import FactualityService

logger = logging.getLogger(__name__)

# Download the sentence tokenizer model if not already present
try:
    nltk.data.find("tokenizers/punkt")
except nltk.downloader.DownloadError:
    nltk.download("punkt")


class EmbeddingFactualityService(FactualityService):
    """
    Assesses factual consistency using sentence embeddings.

    This service breaks the note and transcript into sentences,
    generates embeddings for each using a text-embedding model, and then
    compares them using cosine similarity to find statements in the note
    that are not supported by the transcript.
    """

    # This threshold determines whether a note sentence is considered "supported"
    # by a transcript sentence. It was chosen based on the research cited in the
    # project documentation. It could be made configurable in the future.
    SIMILARITY_THRESHOLD = 0.75

    def __init__(self, llm_client: AsyncAzureLLMClient | None = None) -> None:
        # Allow injecting a client for testing, otherwise create a new one.
        self._llm_client = llm_client or AsyncAzureLLMClient()

    def assess(self, note: str, transcript: str = "", *, precision: str = "medium") -> FactualityResult:
        if not transcript.strip():
            return FactualityResult(
                consistency_score=3.0,  # Neutral score
                claims_checked=0,
                summary="No transcript provided for embedding-based factuality analysis.",
                claims=[],
                claims_narratives=[],
            )

        try:
            # 1. Split texts into sentences
            note_sentences = nltk.sent_tokenize(note)
            transcript_sentences = nltk.sent_tokenize(transcript)

            if not note_sentences:
                return FactualityResult(
                    consistency_score=5.0,  # A note with no claims is perfectly consistent
                    claims_checked=0,
                    summary="Note was empty, no claims to check.",
                    claims=[],
                    claims_narratives=[],
                )

            if not transcript_sentences:
                return FactualityResult(
                    consistency_score=1.0, # No transcript to support any claim
                    claims_checked=len(note_sentences),
                    summary="Transcript was empty, all claims are unsupported.",
                    claims=[{"claim": s, "support": "Not Supported", "explanation": "Transcript is empty."} for s in note_sentences],
                    claims_narratives=[f"Unsupported: '{s}'" for s in note_sentences]
                )

            # 2. Get embeddings for all sentences
            # We run the async get_embeddings function in a new event loop.
            all_sentences = note_sentences + transcript_sentences

            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    # If we're already in an event loop, we can't use asyncio.run.
                    # This is a simplified approach; a more robust solution might
                    # involve a thread pool executor if this were a common case.
                    # For this app's current structure, this should be rare.
                    task = loop.create_task(self._llm_client.get_embeddings(texts=all_sentences))
                    embeddings = asyncio.run_coroutine_threadsafe(task, loop).result()
                else:
                    embeddings = asyncio.run(self._llm_client.get_embeddings(texts=all_sentences))
            except RuntimeError: # No running event loop
                embeddings = asyncio.run(self._llm_client.get_embeddings(texts=all_sentences))


            note_embeddings = np.array(embeddings[: len(note_sentences)])
            transcript_embeddings = np.array(embeddings[len(note_sentences) :])

            # 3. Calculate cosine similarity
            similarity_matrix = cosine_similarity(note_embeddings, transcript_embeddings)

            # 4. Identify unsupported sentences
            unsupported_sentences = []
            supported_count = 0
            for i, note_sent in enumerate(note_sentences):
                max_similarity = np.max(similarity_matrix[i]) if similarity_matrix.shape[1] > 0 else 0
                if max_similarity >= self.SIMILARITY_THRESHOLD:
                    supported_count += 1
                else:
                    unsupported_sentences.append(note_sent)

            # 5. Calculate consistency score (0-1) and map to 1-5 scale
            total_sentences = len(note_sentences)
            support_ratio = supported_count / total_sentences if total_sentences > 0 else 1.0
            consistency_score = 1.0 + (support_ratio * 4.0)

            # 6. Format the result
            summary = f"{supported_count} of {total_sentences} sentences in the note were found to be supported by the transcript."
            claims = [
                {
                    "claim": sent,
                    "support": "Not Supported",
                    "explanation": f"This statement could not be semantically matched to any part of the transcript (max similarity < {self.SIMILARITY_THRESHOLD}).",
                }
                for sent in unsupported_sentences
            ]

            return FactualityResult(
                consistency_score=float(f"{consistency_score:.2f}"),
                claims_checked=total_sentences,
                summary=summary,
                claims=claims,
                claims_narratives=[f"Unsupported: '{s}'" for s in unsupported_sentences],
            )

        except Exception as e:
            logger.error(f"Error during embedding-based factuality assessment: {e}", exc_info=True)
            return FactualityResult(
                consistency_score=3.0,  # Neutral score on error
                claims_checked=0,
                summary=f"An unexpected error occurred during analysis: {e}",
                claims=[],
                claims_narratives=[],
            )
