import pytest
from unittest.mock import patch, Mock
from grading.factuality import analyze_factuality, assess_consistency_with_o3
import openai # Import openai to allow monkeypatching its members

@pytest.fixture
def mock_o3_factuality_success(monkeypatch):
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '{"consistency_score": 4}'
    
    mock_create = Mock(return_value=mock_response)
    monkeypatch.setattr(openai.ChatCompletion, 'create', mock_create) # Patching the create method directly
    return mock_create

@pytest.fixture
def mock_o3_factuality_failure_api(monkeypatch):
    mock_create = Mock(side_effect=Exception("O3 API Error"))
    monkeypatch.setattr(openai.ChatCompletion, 'create', mock_create)
    return mock_create

@pytest.fixture
def mock_o3_factuality_failure_json(monkeypatch):
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = 'Invalid JSON'
    mock_create = Mock(return_value=mock_response)
    monkeypatch.setattr(openai.ChatCompletion, 'create', mock_create)
    return mock_create

@pytest.fixture
def mock_o3_factuality_failure_score_format(monkeypatch):
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '{"consistency_score": "high"}' # Invalid score type
    mock_create = Mock(return_value=mock_response)
    monkeypatch.setattr(openai.ChatCompletion, 'create', mock_create)
    return mock_create


def test_analyze_factuality_no_transcript():
    """Test factuality analysis returns neutral for no transcript."""
    result = analyze_factuality("Patient has diabetes", "")
    assert result['consistency_score'] == 3.0
    assert result['claims_checked'] == 0

def test_analyze_factuality_whitespace_transcript():
    """Test factuality analysis returns neutral for whitespace-only transcript."""
    result = analyze_factuality("Patient has diabetes", "   \n  ")
    assert result['consistency_score'] == 3.0
    assert result['claims_checked'] == 0

def test_analyze_factuality_with_transcript_success(mock_o3_factuality_success, sample_clinical_note):
    """Test factuality analysis with transcript and successful O3 call."""
    transcript = "Patient reported chest pain and shortness of breath"
    result = analyze_factuality(sample_clinical_note, transcript)
    
    assert result['consistency_score'] == 4.0
    assert result['claims_checked'] == 1
    mock_o3_factuality_success.assert_called_once()

def test_analyze_factuality_o3_api_failure(mock_o3_factuality_failure_api, sample_clinical_note):
    """Test factuality analysis handles O3 API call failure."""
    transcript = "Patient reported chest pain"
    result = analyze_factuality(sample_clinical_note, transcript)
    
    assert result['consistency_score'] == 3.0 # Should return neutral score
    assert result['claims_checked'] == 1
    mock_o3_factuality_failure_api.assert_called_once()

def test_analyze_factuality_o3_json_failure(mock_o3_factuality_failure_json, sample_clinical_note):
    """Test factuality analysis handles O3 invalid JSON response."""
    transcript = "Patient reported chest pain"
    # This will raise ValueError inside assess_consistency_with_o3, which is caught, and returns 3
    result = analyze_factuality(sample_clinical_note, transcript)
    assert result['consistency_score'] == 3.0 # Should return neutral score
    assert result['claims_checked'] == 1
    mock_o3_factuality_failure_json.assert_called_once()

def test_analyze_factuality_o3_score_format_failure(mock_o3_factuality_failure_score_format, sample_clinical_note):
    """Test factuality analysis handles O3 invalid score format in JSON."""
    transcript = "Patient reported chest pain"
    # This will raise ValueError inside assess_consistency_with_o3, which is caught, and returns 3
    result = analyze_factuality(sample_clinical_note, transcript)
    assert result['consistency_score'] == 3.0 # Should return neutral score
    assert result['claims_checked'] == 1
    mock_o3_factuality_failure_score_format.assert_called_once()

# Direct tests for assess_consistency_with_o3 (optional, as analyze_factuality covers it)
# but good for granular testing if this function becomes more complex.

@patch('grading.factuality.Config') # Mock Config to simulate no credentials
def test_assess_consistency_no_creds(MockConfig, sample_clinical_note):
    MockConfig.AZURE_OPENAI_ENDPOINT = None
    MockConfig.AZURE_OPENAI_KEY = None
    score = assess_consistency_with_o3(sample_clinical_note, "some transcript")
    assert score == 3 # Neutral score if creds are missing 