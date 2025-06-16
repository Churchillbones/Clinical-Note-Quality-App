"""Azure-specific adapter implementations (LLM client, etc.)."""

from .client import LLMClientProtocol, get_azure_llm_client

__all__ = [
    "LLMClientProtocol",
    "get_azure_llm_client",
] 