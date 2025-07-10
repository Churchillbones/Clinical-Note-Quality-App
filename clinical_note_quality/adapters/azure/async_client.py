"""Async Azure OpenAI client wrapper.

This adapter provides async/await support for Azure OpenAI calls with connection
pooling, exponential backoff, and proper asyncio integration.
"""
from __future__ import annotations

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Protocol, runtime_checkable

from openai import AsyncAzureOpenAI, APIError, APIConnectionError, RateLimitError, APIStatusError
from openai.types.chat import ChatCompletionMessageParam

from clinical_note_quality import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class AsyncLLMClientProtocol(Protocol):
    """Async interface for LLM clients."""

    async def chat_complete(self, *, messages: List[ChatCompletionMessageParam], model: str, **kwargs: Any) -> str:
        """Return content string from async chat completion."""
        ...

    async def close(self) -> None:
        """Clean up async resources."""
        ...


class AsyncAzureLLMClient(AsyncLLMClientProtocol):
    """Async implementation backed by AsyncAzureOpenAI with connection pooling."""

    _MAX_RETRIES = 3
    _BACKOFF_BASE = 1.2
    _TIMEOUT = 60.0

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.AZURE_OPENAI_KEY or not settings.AZURE_OPENAI_ENDPOINT:
            raise ValueError("Azure OpenAI credentials not configured")
        self._client = AsyncAzureOpenAI(
            api_key=settings.AZURE_OPENAI_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            timeout=self._TIMEOUT,
            max_retries=0,  # We handle retries manually
        )

    async def chat_complete(self, *, messages: List[ChatCompletionMessageParam], model: str, **kwargs: Any) -> str:
        """Return content string from async chat completion with exponential backoff."""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            **kwargs,
        }
        
        retry = 0
        while True:
            try:
                response = await self._client.chat.completions.create(**payload)
                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("Received None content from OpenAI API")
                return content.strip()
            except (RateLimitError, APIConnectionError) as exc:
                if retry >= self._MAX_RETRIES:
                    raise
                delay = (self._BACKOFF_BASE ** retry) + random.uniform(0, 0.3)
                logger.warning(
                    "AsyncAzureLLMClient transient error (%s); retrying in %.2fs",
                    exc.__class__.__name__,
                    delay
                )
                await asyncio.sleep(delay)
                retry += 1
            except (APIStatusError, APIError) as exc:
                logger.error("AsyncAzureLLMClient permanent API error: %s", exc, exc_info=True)
                raise

    async def close(self) -> None:
        """Clean up async client resources."""
        await self._client.close()


# Sync wrapper for backwards compatibility
class SyncAzureLLMClientWrapper:
    """Synchronous wrapper around AsyncAzureLLMClient for backwards compatibility."""

    def __init__(self, async_client: AsyncAzureLLMClient) -> None:
        self._async_client = async_client

    def chat_complete(self, *, messages: List[ChatCompletionMessageParam], model: str, **kwargs: Any) -> str:
        """Sync wrapper that runs async chat_complete in event loop."""
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an event loop, we need to run in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._async_client.chat_complete(messages=messages, model=model, **kwargs)
                )
                return future.result()
        except RuntimeError:
            # No event loop running, we can use asyncio.run directly
            return asyncio.run(
                self._async_client.chat_complete(messages=messages, model=model, **kwargs)
            )


# Factory functions
_async_client_instance: AsyncAzureLLMClient | None = None


@asynccontextmanager
async def get_async_azure_llm_client() -> AsyncIterator[AsyncAzureLLMClient]:
    """Get async Azure LLM client with proper resource management."""
    global _async_client_instance
    
    if _async_client_instance is None:
        _async_client_instance = AsyncAzureLLMClient()
    
    try:
        yield _async_client_instance
    finally:
        # Don't close here - let the application manage the lifecycle
        pass


async def close_async_azure_client() -> None:
    """Clean up the global async client instance."""
    global _async_client_instance
    if _async_client_instance:
        await _async_client_instance.close()
        _async_client_instance = None 