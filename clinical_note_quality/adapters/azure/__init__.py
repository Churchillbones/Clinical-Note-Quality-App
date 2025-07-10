"""Azure OpenAI client adapters."""

from .client import LLMClientProtocol, get_azure_llm_client
from .async_client import AsyncLLMClientProtocol, get_async_azure_llm_client, close_async_azure_client

__all__ = [
    "LLMClientProtocol",
    "AsyncLLMClientProtocol", 
    "get_azure_llm_client",
    "get_async_azure_llm_client",
    "close_async_azure_client",
] 