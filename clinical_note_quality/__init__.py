"""Clinical Note Quality – Core package.

This package will progressively encapsulate the domain, services, adapters, and HTTP
layers of the application per the Phase-1 refactor roadmap.

During Phase-1 we expose a no-op default `get_settings()` helper that eventually
returns a `pydantic` settings instance (implemented in milestone 3). For now it
simply imports and returns the existing legacy `Config` for backward-compatibility.
"""
from typing import Union

# -------------------------------------------------------------------------
# Settings transition layer.  External callers should import `get_settings`
# and *not* rely on legacy `config.Config`.  We continue to return the
# legacy object type when pydantic is unavailable, but prefer the new
# `Settings` singleton going forward.
# -------------------------------------------------------------------------

try:
    from .settings import Settings, get_settings as _new_get_settings

    get_settings = _new_get_settings  # type: ignore  # noqa: F401
    SettingsType = Settings
except ModuleNotFoundError:  # pragma: no cover
    # Fallback in environments without the new dependency yet installed.
    from config import Config as _LegacyConfig  # type: ignore

    def get_settings() -> _LegacyConfig:  # type: ignore
        return _LegacyConfig

    SettingsType = _LegacyConfig  # type: ignore

__all__ = [
    "get_settings",
    "SettingsType",
] 