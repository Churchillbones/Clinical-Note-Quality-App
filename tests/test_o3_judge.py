import pytest
import json
from unittest.mock import patch, MagicMock
from openai import APIError, AuthenticationError, APIConnectionError, RateLimitError, APIStatusError
from openai.types.chat import ChatCompletionMessage, ChatCompletion
from openai.types.chat.chat_completion import Choice

from grading.o3_judge import O3Judge, score_with_o3
from grading.exceptions import OpenAIServiceError, OpenAIAuthError, OpenAIResponseError
from config import Config # Import Config to potentially access instruction prompts if needed for advanced tests

# Sample clinical note for testing
@pytest.fixture
def sample_clinical_note():
    return "Patient presents with cough and fever."

# Helper to create a mock ChatCompletion object
def create_mock_chat_completion(content: str, role: str = 'assistant', finish_reason: str = 'stop'):
    return ChatCompletion(
        id='fake_chat_id',
        choices=[
            Choice(
                finish_reason=finish_reason,
                index=0,
                message=ChatCompletionMessage(content=content, role=role)
            )
        ],
        created=1234567890,
        model=Config.AZURE_O3_DEPLOYMENT, # Use actual model from config
        object='chat.completion'
        # system_fingerprint and usage can be None by default
    )

VALID_SCORES_CONTENT = json.dumps({
    'up_to_date': 5, 'accurate': 4, 'thorough': 3, 'useful': 2,
    'organized': 5, 'concise': 4, 'consistent': 3, 'complete': 2, 'actionable': 5
})

# --- Tests for O3Judge class ---

@patch('grading.o3_judge.AzureOpenAI') # Patch where AzureOpenAI is looked up
def test_o3_judge_success(mock_azure_openai_constructor, sample_clinical_note):
    """Test O3Judge returns valid PDQI-9 scores on successful API call."""
    mock_chat_instance = MagicMock()
    mock_chat_instance.chat.completions.create.return_value = create_mock_chat_completion(VALID_SCORES_CONTENT)
    mock_azure_openai_constructor.return_value = mock_chat_instance

    judge = O3Judge() # This will now use the mocked AzureOpenAI client
    scores = judge.score_pdqi9(sample_clinical_note)
    
    required_keys = json.loads(VALID_SCORES_CONTENT).keys()
    assert all(key in scores for key in required_keys)
    for key, value in scores.items():
        assert isinstance(value, int)
        assert 1 <= value <= 5
    
    mock_chat_instance.chat.completions.create.assert_called_once()

# Test various OpenAI API errors
@pytest.mark.parametrize("openai_exception, custom_exception_type, error_message_snippet", [
    (AuthenticationError(message="Auth error", response=MagicMock(), body=None), OpenAIAuthError, "Authentication failed"),
    (APIConnectionError(message="Connection error", request=MagicMock()), OpenAIServiceError, "Could not connect"),
    (RateLimitError(message="Rate limit error", response=MagicMock(), body=None), OpenAIServiceError, "Rate limit exceeded"),
    (APIStatusError(message="API status error", response=MagicMock(status_code=500), body=None), OpenAIServiceError, "API error: 500"),
    (APIError(message="Generic API error", request=MagicMock()), OpenAIServiceError, "Azure OpenAI SDK error"),
])
@patch('grading.o3_judge.AzureOpenAI')
def test_o3_judge_openai_api_errors(mock_azure_openai_constructor, openai_exception, custom_exception_type, error_message_snippet, sample_clinical_note):
    """Test O3Judge raises custom exceptions for various OpenAI API errors."""
    mock_chat_instance = MagicMock()
    mock_chat_instance.chat.completions.create.side_effect = openai_exception
    mock_azure_openai_constructor.return_value = mock_chat_instance

    judge = O3Judge()
    with pytest.raises(custom_exception_type, match=error_message_snippet):
        judge.score_pdqi9(sample_clinical_note)

# Test malformed JSON responses
@pytest.mark.parametrize("malformed_content, error_message_snippet", [
    ("This is not JSON", "Invalid or malformed response"),
    (json.dumps({'up_to_date': 5}), "Missing keys"), # Missing other keys
    (json.dumps({'up_to_date': 'not-an-int', 'accurate': 4, 'thorough': 3, 'useful': 2,
                  'organized': 5, 'concise': 4, 'consistent': 3, 'complete': 2, 'actionable': 5}), 
     "Invalid score for up_to_date"),
    (json.dumps({'up_to_date': 6, 'accurate': 4, 'thorough': 3, 'useful': 2,
                  'organized': 5, 'concise': 4, 'consistent': 3, 'complete': 2, 'actionable': 5}), 
     "Invalid score for up_to_date"), # Score out of range
])
@patch('grading.o3_judge.AzureOpenAI')
def test_o3_judge_malformed_response(mock_azure_openai_constructor, malformed_content, error_message_snippet, sample_clinical_note):
    """Test O3Judge raises OpenAIResponseError for malformed or invalid JSON responses."""
    mock_chat_instance = MagicMock()
    mock_chat_instance.chat.completions.create.return_value = create_mock_chat_completion(malformed_content)
    mock_azure_openai_constructor.return_value = mock_chat_instance

    judge = O3Judge()
    with pytest.raises(OpenAIResponseError, match=error_message_snippet):
        judge.score_pdqi9(sample_clinical_note)

# --- Tests for score_with_o3 convenience function ---

@patch('grading.o3_judge.O3Judge.score_pdqi9') # Patch the method within the class
def test_score_with_o3_convenience_success(mock_score_pdqi9, sample_clinical_note):
    """Test the score_with_o3 convenience function calls O3Judge.score_pdqi9."""
    mock_score_pdqi9.return_value = json.loads(VALID_SCORES_CONTENT)
    
    result = score_with_o3(sample_clinical_note)
    
    assert result == json.loads(VALID_SCORES_CONTENT)
    mock_score_pdqi9.assert_called_once_with(sample_clinical_note)

@patch('grading.o3_judge.O3Judge.score_pdqi9')
def test_score_with_o3_convenience_exception_passthrough(mock_score_pdqi9, sample_clinical_note):
    """Test that exceptions from score_pdqi9 are passed through by score_with_o3."""
    mock_score_pdqi9.side_effect = OpenAIAuthError("Convenience Test Auth Error")
    
    with pytest.raises(OpenAIAuthError, match="Convenience Test Auth Error"):
        score_with_o3(sample_clinical_note)
    mock_score_pdqi9.assert_called_once_with(sample_clinical_note)