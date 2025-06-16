"""Azure OpenAI client wrapper.

This adapter hides the concrete Azure SDK behind a minimal `LLMClientProtocol`
interface so that services layer can depend on an abstraction, easing testing
and future vendor swaps.
"""
from __future__ import annotations

import logging
import random
import time
from functools import lru_cache
from typing import Any, Dict, List, Protocol, runtime_checkable

from openai import AzureOpenAI, APIError, APIConnectionError, RateLimitError, APIStatusError  # type: ignore

from clinical_note_quality import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Public interface the services layer relies on."""

    def chat_complete(self, *, messages: List[Dict[str, str]], model: str, **kwargs: Any) -> str: ...  # noqa: E501


class _AzureLLMClient(LLMClientProtocol):
    """Concrete implementation backed by the Azure OpenAI SDK."""

    _MAX_RETRIES = 3
    _BACKOFF_BASE = 1.2

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat_complete(self, *, messages: List[Dict[str, str]], model: str, **kwargs: Any) -> str:  # noqa: D401,E501
        """Return *content* string from chat completion with basic exponential back-off."""

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            **kwargs,
        }
        retry = 0
        while True:
            try:
                response = self._client.chat.completions.create(**payload)  # type: ignore[arg-type]
                return response.choices[0].message.content.strip()
            except (RateLimitError, APIConnectionError) as exc:
                if retry >= self._MAX_RETRIES:
                    raise
                delay = (self._BACKOFF_BASE ** retry) + random.uniform(0, 0.3)
                logger.warning("AzureLLMClient transient error (%s); retrying in %.2fs", exc.__class__.__name__, delay)
                time.sleep(delay)
                retry += 1
            except (APIStatusError, APIError) as exc:
                logger.error("AzureLLMClient permanent API error: %s", exc, exc_info=True)
                raise


# ----------------------------------------------------------------------
# Factory / Singleton helpers
# ----------------------------------------------------------------------

@lru_cache()
def get_azure_llm_client() -> LLMClientProtocol:
    """Return a *singleton* instance of the Azure LLM client."""

    return _AzureLLMClient() 