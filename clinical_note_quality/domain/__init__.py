"""Domain models and exceptions for clinical note quality assessment."""

from .exceptions import (
    ClinicalNoteQualityError,
    FactualityServiceError,
    GradingServiceError,
    HeuristicServiceError,
    OpenAIAuthError,
    OpenAIResponseError,
    OpenAIServiceError,
    PDQIServiceError,
)
from .models import (
    FactualityResult,
    HeuristicResult,
    HybridResult,
    PDQIDimension,
    PDQIDimensionExplanation,
    PDQIScore,
)

__all__ = [
    # Exceptions
    "ClinicalNoteQualityError",
    "FactualityServiceError", 
    "GradingServiceError",
    "HeuristicServiceError",
    "OpenAIAuthError",
    "OpenAIResponseError", 
    "OpenAIServiceError",
    "PDQIServiceError",
    # Models
    "FactualityResult",
    "HeuristicResult",
    "HybridResult",
    "PDQIDimension",
    "PDQIDimensionExplanation",
    "PDQIScore",
] 