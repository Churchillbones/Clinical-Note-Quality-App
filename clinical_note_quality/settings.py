"""Pydantic-based application settings (Milestone 3).

This module is a *drop-in* replacement for the legacy `config.Config` class.  It
reads environment variables (and optionally a `.env` file) and falls back to the
current defaults from `config.Config` so we can migrate incrementally without
breaking existing behaviour.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

# Pydantic v2 split BaseSettings into separate package
try:
    from pydantic_settings import BaseSettings
except ModuleNotFoundError:  # pragma: no cover – fallback for v1
    from pydantic import BaseSettings  # type: ignore

from pydantic import Field, AliasChoices, ConfigDict

# Re-use the existing constant defaults to minimise duplicated literals.
from config import Config as _LegacyConfig


class Settings(BaseSettings):
    """Centralised configuration loaded from environment variables."""

    # ---------------------------------------------------------------------
    # Core
    # ---------------------------------------------------------------------
    SECRET_KEY: str = Field(_LegacyConfig.SECRET_KEY, validation_alias="SECRET_KEY")

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str | None = Field(
        _LegacyConfig.AZURE_OPENAI_ENDPOINT,
        validation_alias=AliasChoices("AZ_OPENAI_ENDPOINT", "AZURE_ENDPOINT"),
    )
    AZURE_OPENAI_KEY: str | None = Field(
        _LegacyConfig.AZURE_OPENAI_KEY,
        validation_alias=AliasChoices("AZ_OPENAI_KEY", "AZURE_API_KEY"),
    )

    # Model selection
    MODEL_NAME: str = Field(_LegacyConfig.MODEL_NAME, validation_alias="MODEL_NAME")
    API_VERSION: str = Field(_LegacyConfig.API_VERSION, validation_alias="API_VERSION")

    # Derived aliases (remains overridable)
    GPT4O_DEPLOYMENT: str = Field(
        _LegacyConfig.GPT4O_DEPLOYMENT, validation_alias="GPT4O_DEPLOYMENT"
    )
    AZURE_GPT4O_API_VERSION: str = Field(
        _LegacyConfig.AZURE_GPT4O_API_VERSION, validation_alias="AZURE_GPT4O_API_VERSION"
    )

    # O3
    AZURE_O3_DEPLOYMENT: str = Field(
        _LegacyConfig.AZURE_O3_DEPLOYMENT, validation_alias="AZ_O3_DEPLOYMENT"
    )
    AZURE_O3_API_VERSION: str = Field(
        _LegacyConfig.AZURE_O3_API_VERSION, validation_alias="AZ_O3_API_VERSION"
    )
    AZURE_OPENAI_API_VERSION: str = Field(
        _LegacyConfig.AZURE_OPENAI_API_VERSION, validation_alias="AZURE_OPENAI_API_VERSION"
    )

    MAX_COMPLETION_TOKENS: int = Field(
        _LegacyConfig.MAX_COMPLETION_TOKENS, validation_alias="MAX_COMPLETION_TOKENS"
    )

    MODEL_PRECISION: str = Field(
        _LegacyConfig.MODEL_PRECISION, validation_alias="MODEL_PRECISION"
    )
    AZURE_O3_HIGH_DEPLOYMENT: str = Field(
        _LegacyConfig.AZURE_O3_HIGH_DEPLOYMENT, validation_alias="AZ_O3_HIGH_DEPLOYMENT"
    )
    AZURE_O3_LOW_DEPLOYMENT: str = Field(
        _LegacyConfig.AZURE_O3_LOW_DEPLOYMENT, validation_alias="AZ_O3_LOW_DEPLOYMENT"
    )

    #   ---- Prompt strings -------------------------------------------------
    PDQI_INSTRUCTIONS: str = _LegacyConfig.PDQI_INSTRUCTIONS
    FACTUALITY_INSTRUCTIONS: str = _LegacyConfig.FACTUALITY_INSTRUCTIONS

    #   ---- Hybrid Weights -------------------------------------------------
    PDQI_WEIGHT: float = Field(_LegacyConfig.PDQI_WEIGHT, validation_alias="PDQI_WEIGHT")
    HEURISTIC_WEIGHT: float = Field(_LegacyConfig.HEURISTIC_WEIGHT, validation_alias="HEURISTIC_WEIGHT")
    FACTUALITY_WEIGHT: float = Field(
        _LegacyConfig.FACTUALITY_WEIGHT, validation_alias="FACTUALITY_WEIGHT"
    )

    AZURE_FACTUALITY_DEPLOYMENT: str | None = Field(
        _LegacyConfig.AZURE_FACTUALITY_DEPLOYMENT, validation_alias="AZ_FACTUALITY_DEPLOYMENT"
    )

    USE_NINE_RINGS: bool = Field(_LegacyConfig.USE_NINE_RINGS, validation_alias="USE_NINE_RINGS")

    # ------------------------------------------------------------------
    # Pydantic settings config
    # ------------------------------------------------------------------

    # Pydantic v2 style configuration
    model_config = ConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache()
def get_settings() -> "Settings":  # noqa: D401
    """Return a **cached** Settings instance (Singleton)."""

    return Settings()
