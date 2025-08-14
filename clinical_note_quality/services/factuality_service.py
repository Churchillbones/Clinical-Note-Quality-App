"""Factuality assessment service (Milestone 6).

Phase-1 provides a thin wrapper around the existing synchronous O3-based
implementation.  Async agent-based analysis will migrate here in Phase-2.
"""
from __future__ import annotations

import logging
from typing import Any, List, Protocol, runtime_checkable

from openai import APIConnectionError, APIStatusError, AzureOpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessageParam

from clinical_note_quality.domain import FactualityResult
from clinical_note_quality import get_settings
from config import Config

from grading.factuality import _fallback_factuality_response  # type: ignore

logger = logging.getLogger(__name__)


@runtime_checkable
class FactualityService(Protocol):
    """Interface for assessing factual consistency."""

    def assess(self, note: str, transcript: str = "", *, precision: str = "medium") -> FactualityResult: ...


class O3FactualityService(FactualityService):
    """
    Assesses factual consistency using an O3 model.
    This service now contains the logic for calling the Azure OpenAI API,
    migrated from the deprecated `grading.factuality` module.
    """

    def assess(
        self,
        note: str,
        transcript: str = "",
        *,
        precision: str = "medium",
        flagged_sentences: list[str] | None = None,
    ) -> FactualityResult:
        if not Config.AZURE_OPENAI_ENDPOINT or not Config.AZURE_OPENAI_KEY:
            logger.warning("Azure OpenAI credentials not configured for factuality check.")
            return FactualityResult(
                consistency_score=3.0, summary="Azure OpenAI not configured"
            )

        try:
            client = AzureOpenAI(
                azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                api_key=Config.AZURE_OPENAI_KEY,
                api_version=Config.AZURE_O3_API_VERSION,
            )

            system_prompt = Config.FACTUALITY_INSTRUCTIONS
            user_content = f"Clinical Note:\n\n{note}\n\nEncounter Transcript:\n\n{transcript}"

            if flagged_sentences:
                system_prompt = Config.HYBRID_FACTUALITY_INSTRUCTIONS
                flagged_list = "\n".join(f"- {s}" for s in flagged_sentences)
                user_content += f"\n\nPlease pay special attention to the following sentences that were flagged by a preliminary analysis:\n{flagged_list}"

            messages: List[ChatCompletionMessageParam] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]

            # Simplified model selection from legacy file
            model_name = Config.AZURE_O3_DEPLOYMENT
            if precision == "high":
                model_name = Config.AZURE_O3_HIGH_DEPLOYMENT
            elif precision == "low":
                model_name = Config.AZURE_O3_LOW_DEPLOYMENT

            kwargs = {
                "model": model_name,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "max_completion_tokens": Config.MAX_COMPLETION_TOKENS,
            }

            response = client.chat.completions.create(**kwargs)
            raw_content = response.choices[0].message.content

            if raw_content is None:
                logger.error("Received None content from O3 factuality check.")
                raw = _fallback_factuality_response()
            else:
                import json
                try:
                    raw = json.loads(raw_content)
                except json.JSONDecodeError:
                    logger.error("Failed to parse O3 JSON response for factuality: %s", raw_content)
                    raw = _fallback_factuality_response()

        except (APIConnectionError, RateLimitError, APIStatusError) as e:
            logger.error(f"O3 factuality assessment failed due to API error: {e}", exc_info=True)
            raw = _fallback_factuality_response()

        return FactualityResult(
            consistency_score=float(raw.get("consistency_score", 0.0)),
            claims_checked=int(raw.get("claims_checked", 0)),
            summary=str(raw.get("summary", "")),
            claims=raw.get("claims", []),
            consistency_narrative=str(raw.get("consistency_narrative", "")),
            claims_narratives=raw.get("claims_narratives", []),
        )


# Factory --------------------------------------------------------------------

def get_factuality_service() -> FactualityService:
    """
    Return the configured factuality service.

    This factory function reads the `FACTUALITY_PROVIDER` setting and
    returns the corresponding factuality service instance. It defaults
    to the O3-based service for backward compatibility.
    """
    settings = get_settings()
    provider = settings.FACTUALITY_PROVIDER.lower()

    if provider == "embedding":
        from clinical_note_quality.services.embedding_service import EmbeddingFactualityService

        logger.info("Using EmbeddingFactualityService for factuality assessment.")
        return EmbeddingFactualityService()
    elif provider == "hybrid":
        from clinical_note_quality.services.hybrid_factuality_service import (
            HybridFactualityService,
        )

        logger.info("Using HybridFactualityService for factuality assessment.")
        return HybridFactualityService()
    elif provider == "o3":
        logger.info("Using O3FactualityService for factuality assessment.")
        return O3FactualityService()
    # Add 'gpt4o' provider option here in the future if needed.
    else:
        logger.warning(
            "Unknown FACTUALITY_PROVIDER '%s'. Defaulting to O3FactualityService.",
            settings.FACTUALITY_PROVIDER,
        )
        return O3FactualityService()