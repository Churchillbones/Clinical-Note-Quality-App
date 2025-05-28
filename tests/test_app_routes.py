import pytest
import json

def test_index_route(client):
    """Test the main index route returns HTML form."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Clinical Note' in response.data

def test_api_grade_missing_json(client):
    """Test API returns 400 for missing JSON."""
    response = client.post('/api/grade')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

def test_api_grade_missing_note(client):
    """Test API returns 400 for missing clinical_note."""
    response = client.post('/api/grade', 
                          json={'encounter_transcript': 'test'})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'clinical_note' in data['error']

def test_api_grade_note_too_long(client):
    """Test API returns 413 for notes over 20k characters."""
    long_note = 'x' * 20001
    response = client.post('/api/grade', 
                          json={'clinical_note': long_note})
    assert response.status_code == 413

def test_api_grade_success(client, mock_openai, sample_clinical_note):
    """Test successful API grading."""
    response = client.post('/api/grade', 
                          json={'clinical_note': sample_clinical_note})
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'pdqi_scores' in data
    assert 'hybrid_score' in data
    assert 'overall_grade' in data
    assert 'processing_time_seconds' in data

def test_form_grade_success(client, mock_openai, sample_clinical_note):
    """Test successful form-based grading."""
    response = client.post('/grade', 
                          data={'clinical_note': sample_clinical_note})
    assert response.status_code == 200
    assert b'Assessment Results' in response.data 