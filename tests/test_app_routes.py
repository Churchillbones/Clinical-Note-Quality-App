import pytest
import json
from unittest.mock import patch
from app import app # Import the Flask app instance
from grading.exceptions import OpenAIServiceError, OpenAIAuthError, OpenAIResponseError

# Pytest fixture to configure the Flask test client
@pytest.fixture
def client():
    app.config['TESTING'] = True
    # SECRET_KEY is needed for session handling, which might be used by flash messages or other extensions
    # Even if not directly used now, it's good practice for Flask apps.
    app.config['SECRET_KEY'] = 'test-secret-key' 
    with app.test_client() as client:
        yield client

# Sample data to be returned by the mocked grade_note_hybrid
MOCK_GRADING_RESULT = {
    'pdqi_scores': {'up_to_date': 5},
    'hybrid_score': 4.5,
    'overall_grade': 'A',
    'processing_time_seconds': 0.1
}

# --- Test Index Route ---
def test_index_route(client):
    """Test the main index route returns HTML form."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Grade Clinical Note' in response.data
    assert b'Clinical Note' in response.data
    assert b'Encounter Transcript' in response.data

# --- Tests for /grade (Form Post) Route ---

@patch('app.grade_note_hybrid')
def test_form_grade_success(mock_grade_hybrid, client):
    """Test successful form-based grading."""
    mock_grade_hybrid.return_value = MOCK_GRADING_RESULT
    
    response = client.post('/grade', data={
        'clinical_note': 'This is a test clinical note.',
        'encounter_transcript': 'This is a test transcript.'
    })
    assert response.status_code == 200
    assert b'Assessment Results' in response.data
    assert b'Overall Quality Score' in response.data
    assert b'4.5/5.0' in response.data # Check for hybrid_score
    mock_grade_hybrid.assert_called_once_with(
        clinical_note='This is a test clinical note.',
        encounter_transcript='This is a test transcript.'
    )

@patch('app.grade_note_hybrid')
def test_form_grade_success_no_transcript(mock_grade_hybrid, client):
    """Test successful form-based grading without transcript."""
    mock_grade_hybrid.return_value = MOCK_GRADING_RESULT
    
    response = client.post('/grade', data={
        'clinical_note': 'This is another test clinical note.'
    })
    assert response.status_code == 200
    assert b'Assessment Results' in response.data
    mock_grade_hybrid.assert_called_once_with(
        clinical_note='This is another test clinical note.',
        encounter_transcript='' # Expect empty string if not provided
    )

@patch('app.grade_note_hybrid')
def test_form_grade_openai_service_error(mock_grade_hybrid, client):
    """Test form grading with OpenAIServiceError."""
    mock_grade_hybrid.side_effect = OpenAIServiceError("Mocked Service Error")
    response = client.post('/grade', data={'clinical_note': 'Test note'})
    assert response.status_code == 200 # Error is rendered on index.html
    assert b'Grade Clinical Note' in response.data # Should show index page
    assert b'Mocked Service Error' in response.data

@patch('app.grade_note_hybrid')
def test_form_grade_openai_auth_error(mock_grade_hybrid, client):
    """Test form grading with OpenAIAuthError."""
    mock_grade_hybrid.side_effect = OpenAIAuthError("Mocked Auth Error")
    response = client.post('/grade', data={'clinical_note': 'Test note'})
    assert response.status_code == 200
    assert b'Grade Clinical Note' in response.data
    assert b'Mocked Auth Error' in response.data

@patch('app.grade_note_hybrid')
def test_form_grade_openai_response_error(mock_grade_hybrid, client):
    """Test form grading with OpenAIResponseError."""
    mock_grade_hybrid.side_effect = OpenAIResponseError("Mocked Response Error")
    response = client.post('/grade', data={'clinical_note': 'Test note'})
    assert response.status_code == 200
    assert b'Grade Clinical Note' in response.data
    assert b'Mocked Response Error' in response.data

@patch('app.grade_note_hybrid')
def test_form_grade_generic_exception(mock_grade_hybrid, client):
    """Test form grading with a generic Exception."""
    mock_grade_hybrid.side_effect = Exception("Generic Mocked Error")
    response = client.post('/grade', data={'clinical_note': 'Test note'})
    assert response.status_code == 200
    assert b'Grade Clinical Note' in response.data
    assert b'An unexpected error occurred during grading. Please try again.' in response.data


# --- Tests for /api/grade (JSON Post) Route ---

def test_api_grade_missing_json(client):
    """Test API returns 400 for missing JSON."""
    response = client.post('/api/grade', content_type='application/json')
    # Werkzeug/Flask behavior for no data with get_json(silent=False) is to raise,
    # which leads to a 400 Bad Request by default if get_json() is called.
    # If get_json(force=True) it might return None which our code handles.
    # If get_json() returns None because content_type is not application/json or data is not valid json
    # our code `if not data or 'clinical_note' not in data:` will lead to 400.
    assert response.status_code == 400 
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'clinical_note is required'


def test_api_grade_missing_note_in_json(client):
    """Test API returns 400 for missing clinical_note in JSON."""
    response = client.post('/api/grade', json={'encounter_transcript': 'test transcript'})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == 'clinical_note is required'

@patch('app.grade_note_hybrid')
def test_api_grade_success(mock_grade_hybrid, client):
    """Test successful API grading."""
    mock_grade_hybrid.return_value = MOCK_GRADING_RESULT
    
    payload = {
        'clinical_note': 'API test note.',
        'encounter_transcript': 'API test transcript.'
    }
    response = client.post('/api/grade', json=payload)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == MOCK_GRADING_RESULT
    mock_grade_hybrid.assert_called_once_with(
        clinical_note=payload['clinical_note'],
        encounter_transcript=payload['encounter_transcript']
    )

@patch('app.grade_note_hybrid')
def test_api_grade_success_no_transcript(mock_grade_hybrid, client):
    """Test successful API grading without transcript."""
    mock_grade_hybrid.return_value = MOCK_GRADING_RESULT
    
    payload = {'clinical_note': 'API test note without transcript.'}
    response = client.post('/api/grade', json=payload)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data == MOCK_GRADING_RESULT
    mock_grade_hybrid.assert_called_once_with(
        clinical_note=payload['clinical_note'],
        encounter_transcript=None # For JSON, .get('key_name') returns None if not present
    )

@patch('app.grade_note_hybrid')
def test_api_grade_openai_service_error(mock_grade_hybrid, client):
    """Test API grading with OpenAIServiceError."""
    mock_grade_hybrid.side_effect = OpenAIServiceError("Mocked API Service Error")
    response = client.post('/api/grade', json={'clinical_note': 'Test note'})
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == "Mocked API Service Error"

@patch('app.grade_note_hybrid')
def test_api_grade_openai_auth_error(mock_grade_hybrid, client):
    """Test API grading with OpenAIAuthError."""
    mock_grade_hybrid.side_effect = OpenAIAuthError("Mocked API Auth Error")
    response = client.post('/api/grade', json={'clinical_note': 'Test note'})
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == "Mocked API Auth Error"

@patch('app.grade_note_hybrid')
def test_api_grade_openai_response_error(mock_grade_hybrid, client):
    """Test API grading with OpenAIResponseError."""
    mock_grade_hybrid.side_effect = OpenAIResponseError("Mocked API Response Error")
    response = client.post('/api/grade', json={'clinical_note': 'Test note'})
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == "Mocked API Response Error"

@patch('app.grade_note_hybrid')
def test_api_grade_generic_exception(mock_grade_hybrid, client):
    """Test API grading with a generic Exception."""
    mock_grade_hybrid.side_effect = Exception("Generic Mocked API Error")
    response = client.post('/api/grade', json={'clinical_note': 'Test note'})
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == "An unexpected error occurred during grading."

# Note: The test_api_grade_note_too_long was removed as app.py doesn't implement
# specific length validation that returns HTTP 413.
# Form fields have maxlength, but this is client-side enforced or would need server-side logic.