import pytest
import json
from unittest.mock import patch, MagicMock
from openai import APIError, AuthenticationError, APIConnectionError, RateLimitError, APIStatusError
from openai.types.chat import ChatCompletionMessage, ChatCompletion
from openai.types.chat.chat_completion import Choice

from grading.factuality import analyze_factuality, assess_consistency_with_o3
from grading.exceptions import OpenAIServiceError, OpenAIAuthError, OpenAIResponseError
from config import Config

# Sample clinical note for testing (can be shared via conftest.py if used elsewhere)
@pytest.fixture
def sample_clinical_note():
    return "Patient presents with cough and fever."

# Helper to create a mock ChatCompletion object (similar to test_o3_judge.py)
def create_mock_chat_completion(content: str, role: str = 'assistant', finish_reason: str = 'stop'):
    return ChatCompletion(
        id='fake_chat_id_factuality',
        choices=[
            Choice(
                finish_reason=finish_reason,
                index=0,
                message=ChatCompletionMessage(content=content, role=role)
            )
        ],
        created=1234567890,
        model=Config.AZURE_O3_DEPLOYMENT,
        object='chat.completion'
    )

# --- Tests for assess_consistency_with_o3 ---

@patch('grading.factuality.AzureOpenAI')
def test_assess_consistency_success(mock_azure_openai_constructor, sample_clinical_note):
    """Test assess_consistency_with_o3 returns score on successful API call."""
    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.return_value = create_mock_chat_completion('{"consistency_score": 4}')
    mock_azure_openai_constructor.return_value = mock_client_instance

    score = assess_consistency_with_o3(sample_clinical_note, "Some transcript")
    assert score == 4
    mock_client_instance.chat.completions.create.assert_called_once()

@pytest.mark.parametrize("openai_exception, custom_exception_type, error_message_snippet", [
    (AuthenticationError(message="Auth error", response=MagicMock(), body=None), OpenAIAuthError, "Authentication failed"),
    (APIConnectionError(message="Connection error", request=MagicMock()), OpenAIServiceError, "Could not connect"),
    (RateLimitError(message="Rate limit error", response=MagicMock(), body=None), OpenAIServiceError, "Rate limit exceeded"),
    (APIStatusError(message="API status error", response=MagicMock(status_code=401), body=None), OpenAIServiceError, "API error: 401"),
    (APIError(message="Generic API error", request=MagicMock()), OpenAIServiceError, "Azure OpenAI SDK error"),
])
@patch('grading.factuality.AzureOpenAI')
def test_assess_consistency_openai_api_errors(mock_constructor, openai_exception, custom_exception_type, error_message_snippet, sample_clinical_note):
    """Test assess_consistency_with_o3 raises custom exceptions for OpenAI API errors."""
    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.side_effect = openai_exception
    mock_constructor.return_value = mock_client_instance

    with pytest.raises(custom_exception_type, match=error_message_snippet):
        assess_consistency_with_o3(sample_clinical_note, "Some transcript")

@pytest.mark.parametrize("malformed_content, error_message_snippet", [
    ("Not JSON", "Invalid or malformed response"),
    (json.dumps({"wrong_key": 5}), "Invalid score format or value"), # Missing 'consistency_score'
    (json.dumps({"consistency_score": "high"}), "Invalid score format or value"), # Invalid type
    (json.dumps({"consistency_score": 0}), "Invalid score format or value"), # Score out of range (too low)
    (json.dumps({"consistency_score": 6}), "Invalid score format or value"), # Score out of range (too high)
])
@patch('grading.factuality.AzureOpenAI')
def test_assess_consistency_malformed_response(mock_constructor, malformed_content, error_message_snippet, sample_clinical_note):
    """Test assess_consistency_with_o3 raises OpenAIResponseError for malformed/invalid responses."""
    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create.return_value = create_mock_chat_completion(malformed_content)
    mock_constructor.return_value = mock_client_instance

    with pytest.raises(OpenAIResponseError, match=error_message_snippet):
        assess_consistency_with_o3(sample_clinical_note, "Some transcript")

@patch('grading.factuality.AzureOpenAI')
def test_assess_consistency_generic_exception_returns_neutral(mock_constructor, sample_clinical_note):
    """Test assess_consistency_with_o3 returns neutral score for non-OpenAI, non-Response errors."""
    mock_client_instance = MagicMock()
    # Simulate an unexpected error, e.g. a bug in internal logic after API call but before return
    mock_client_instance.chat.completions.create.side_effect = Exception("Some other unexpected error")
    mock_constructor.return_value = mock_client_instance
    
    score = assess_consistency_with_o3(sample_clinical_note, "A transcript")
    assert score == 3


@patch('grading.factuality.Config.AZURE_OPENAI_ENDPOINT', None)
@patch('grading.factuality.Config.AZURE_OPENAI_KEY', None)
def test_assess_consistency_no_creds(sample_clinical_note):
    """Test assess_consistency_with_o3 returns neutral score if Azure credentials are not configured."""
    # No need to mock AzureOpenAI client here, as it shouldn't be called if creds are missing.
    score = assess_consistency_with_o3(sample_clinical_note, "Some transcript")
    assert score == 3
    # Optionally, check for logged warning if caplog fixture is used.

# --- Tests for analyze_factuality ---

def test_analyze_factuality_no_transcript(sample_clinical_note):
    """Test analyze_factuality returns neutral for no transcript."""
    result = analyze_factuality(sample_clinical_note, "")
    assert result['consistency_score'] == 3.0
    assert result['claims_checked'] == 0

def test_analyze_factuality_whitespace_transcript(sample_clinical_note):
    """Test analyze_factuality returns neutral for whitespace-only transcript."""
    result = analyze_factuality(sample_clinical_note, "   \n  ")
    assert result['consistency_score'] == 3.0
    assert result['claims_checked'] == 0

@patch('grading.factuality.assess_consistency_with_o3')
def test_analyze_factuality_with_transcript_success(mock_assess_consistency, sample_clinical_note):
    """Test analyze_factuality with transcript and successful assessment."""
    mock_assess_consistency.return_value = 4 # Mock the underlying O3 assessment score
    
    transcript = "Patient reported chest pain and shortness of breath"
    result = analyze_factuality(sample_clinical_note, transcript)
    
    assert result['consistency_score'] == 4.0
    assert result['claims_checked'] == 1
    mock_assess_consistency.assert_called_once_with(sample_clinical_note, transcript)

@patch('grading.factuality.assess_consistency_with_o3')
def test_analyze_factuality_propagates_openai_exception(mock_assess_consistency, sample_clinical_note):
    """Test analyze_factuality propagates OpenAI exceptions from assess_consistency_with_o3."""
    mock_assess_consistency.side_effect = OpenAIAuthError("Factuality Auth Error")
    
    transcript = "Patient reported chest pain"
    with pytest.raises(OpenAIAuthError, match="Factuality Auth Error"):
        analyze_factuality(sample_clinical_note, transcript)
    mock_assess_consistency.assert_called_once_with(sample_clinical_note, transcript)

@patch('grading.factuality.assess_consistency_with_o3')
def test_analyze_factuality_handles_neutral_score_on_generic_exception(mock_assess_consistency, sample_clinical_note):
    """Test analyze_factuality handles neutral score if assess_consistency returns 3 due to generic error."""
    # This simulates the case where assess_consistency_with_o3 itself handles a generic error and returns 3
    mock_assess_consistency.return_value = 3 
    
    transcript = "Patient reported chest pain"
    result = analyze_factuality(sample_clinical_note, transcript)
    
    assert result['consistency_score'] == 3.0
    assert result['claims_checked'] == 1
    mock_assess_consistency.assert_called_once_with(sample_clinical_note, transcript)