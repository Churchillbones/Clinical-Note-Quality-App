"""Pydantic-based application settings (Milestone 3).

This module is a *drop-in* replacement for the legacy `config.Config` class.  It
reads environment variables (and optionally a `.env` file) and falls back to the
current defaults from `config.Config` so we can migrate incrementally without
breaking existing behaviour.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

# Elite Python imports with proper type safety
from pydantic import Field, AliasChoices

# Use pydantic-settings for BaseSettings (required for modern pydantic)
from pydantic_settings import BaseSettings, SettingsConfigDict

# Re-use the existing constant defaults to minimise duplicated literals.
from config import Config as _LegacyConfig


class Settings(BaseSettings):
    """Centralised configuration loaded from environment variables."""

    # ---------------------------------------------------------------------
    # Core
    # ---------------------------------------------------------------------
    SECRET_KEY: str = Field(default=_LegacyConfig.SECRET_KEY, validation_alias="SECRET_KEY")

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str | None = Field(
        default=_LegacyConfig.AZURE_OPENAI_ENDPOINT,
        validation_alias=AliasChoices("AZ_OPENAI_ENDPOINT", "AZURE_ENDPOINT"),
    )
    AZURE_OPENAI_KEY: str | None = Field(
        default=_LegacyConfig.AZURE_OPENAI_KEY,
        validation_alias=AliasChoices("AZ_OPENAI_KEY", "AZURE_API_KEY"),
    )

    # Model selection
    MODEL_NAME: str = Field(default=_LegacyConfig.MODEL_NAME, validation_alias="MODEL_NAME")
    API_VERSION: str = Field(default=_LegacyConfig.API_VERSION, validation_alias="API_VERSION")

    # Derived aliases (remains overridable)
    GPT4O_DEPLOYMENT: str = Field(
        default=_LegacyConfig.GPT4O_DEPLOYMENT, validation_alias="GPT4O_DEPLOYMENT"
    )
    AZURE_GPT4O_API_VERSION: str = Field(
        default=_LegacyConfig.AZURE_GPT4O_API_VERSION, validation_alias="AZURE_GPT4O_API_VERSION"
    )

    # O3
    AZURE_O3_DEPLOYMENT: str = Field(
        default=_LegacyConfig.AZURE_O3_DEPLOYMENT, validation_alias="AZ_O3_DEPLOYMENT"
    )
    AZURE_O3_API_VERSION: str = Field(
        default=_LegacyConfig.AZURE_O3_API_VERSION, validation_alias="AZ_O3_API_VERSION"
    )
    AZURE_OPENAI_API_VERSION: str = Field(
        default=_LegacyConfig.AZURE_OPENAI_API_VERSION, validation_alias="AZURE_OPENAI_API_VERSION"
    )

    # Embedding Configuration for Semantic Gap Detection
    EMBEDDING_ENDPOINT: str | None = Field(
        default=None, validation_alias="EMBEDDING_ENDPOINT"
    )
    EMBEDDING_DEPLOYMENT: str = Field(
        default="text-embedding-3-large", validation_alias="EMBEDDING_DEPLOYMENT"
    )
    EMBEDDING_API_VERSION: str = Field(
        default="2025-01-01-preview", validation_alias="EMBEDDING_API_VERSION"
    )

    MAX_COMPLETION_TOKENS: int = Field(
        default=_LegacyConfig.MAX_COMPLETION_TOKENS, validation_alias="MAX_COMPLETION_TOKENS"
    )

    MODEL_PRECISION: str = Field(
        default=_LegacyConfig.MODEL_PRECISION, validation_alias="MODEL_PRECISION"
    )
    AZURE_O3_HIGH_DEPLOYMENT: str = Field(
        default=_LegacyConfig.AZURE_O3_HIGH_DEPLOYMENT, validation_alias="AZ_O3_HIGH_DEPLOYMENT"
    )
    AZURE_O3_LOW_DEPLOYMENT: str = Field(
        default=_LegacyConfig.AZURE_O3_LOW_DEPLOYMENT, validation_alias="AZ_O3_LOW_DEPLOYMENT"
    )

    #   ---- Prompt strings -------------------------------------------------
    PDQI_INSTRUCTIONS: str = _LegacyConfig.PDQI_INSTRUCTIONS
    FACTUALITY_INSTRUCTIONS: str = _LegacyConfig.FACTUALITY_INSTRUCTIONS

    #   ---- Hybrid Weights -------------------------------------------------
    PDQI_WEIGHT: float = Field(default=_LegacyConfig.PDQI_WEIGHT, validation_alias="PDQI_WEIGHT")
    HEURISTIC_WEIGHT: float = Field(default=_LegacyConfig.HEURISTIC_WEIGHT, validation_alias="HEURISTIC_WEIGHT")
    FACTUALITY_WEIGHT: float = Field(
        default=_LegacyConfig.FACTUALITY_WEIGHT, validation_alias="FACTUALITY_WEIGHT"
    )

    AZURE_FACTUALITY_DEPLOYMENT: str | None = Field(
        default=_LegacyConfig.AZURE_FACTUALITY_DEPLOYMENT, validation_alias="AZ_FACTUALITY_DEPLOYMENT"
    )

    USE_NINE_RINGS: bool = Field(default=_LegacyConfig.USE_NINE_RINGS, validation_alias="USE_NINE_RINGS")

    # Chain of Thought / Reasoning Configuration
    ENABLE_REASONING_SUMMARY: bool = Field(
        default=getattr(_LegacyConfig, 'ENABLE_REASONING_SUMMARY', True), 
        validation_alias="ENABLE_REASONING_SUMMARY"
    )
    REASONING_SUMMARY_TYPE: str = Field(
        default=getattr(_LegacyConfig, 'REASONING_SUMMARY_TYPE', 'concise'), 
        validation_alias="REASONING_SUMMARY_TYPE"
    )

    # Preview API Configuration for Responses API
    AZURE_OPENAI_PREVIEW_API_VERSION: str = Field(
        default=getattr(_LegacyConfig, 'AZURE_OPENAI_PREVIEW_API_VERSION', '2025-03-01-preview'),
        validation_alias="AZURE_OPENAI_PREVIEW_API_VERSION"
    )
    USE_RESPONSES_API_FOR_REASONING: bool = Field(
        default=getattr(_LegacyConfig, 'USE_RESPONSES_API_FOR_REASONING', False),
        validation_alias="USE_RESPONSES_API_FOR_REASONING"
    )

    # ------------------------------------------------------------------
    # Pydantic settings config
    # ------------------------------------------------------------------

    # Pydantic v2 style configuration with proper SettingsConfigDict
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache()
def get_settings() -> "Settings":  # noqa: D401
    """Return a **cached** Settings instance (Singleton)."""

    return Settings()
