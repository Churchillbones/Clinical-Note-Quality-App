"""Exception classes for the clinical note quality assessment system."""

from __future__ import annotations


class ClinicalNoteQualityError(Exception):
    """Base exception for all clinical note quality errors."""


class OpenAIServiceError(ClinicalNoteQualityError):
    """Raised when OpenAI service encounters an error."""


class OpenAIAuthError(OpenAIServiceError):
    """Raised when OpenAI authentication fails."""


class OpenAIResponseError(OpenAIServiceError):
    """Raised when OpenAI returns an invalid or unexpected response."""


class GradingServiceError(ClinicalNoteQualityError):
    """Raised when the grading service encounters an error."""


class PDQIServiceError(GradingServiceError):
    """Raised when PDQI scoring fails."""


class HeuristicServiceError(GradingServiceError):
    """Raised when heuristic analysis fails."""


class FactualityServiceError(GradingServiceError):
    """Raised when factuality checking fails.""" 