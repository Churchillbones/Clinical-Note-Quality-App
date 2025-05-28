class OpenAIServiceError(Exception):
    """Base class for errors related to the OpenAI service."""
    pass

class OpenAIAuthError(OpenAIServiceError):
    """Raised for authentication issues with the OpenAI service."""
    pass

class OpenAIResponseError(OpenAIServiceError):
    """Raised for issues with the response from the OpenAI service."""
    pass
