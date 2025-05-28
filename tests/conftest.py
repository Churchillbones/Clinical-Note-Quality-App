import pytest
from app import app
from unittest.mock import Mock

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_openai(monkeypatch):
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''
    {
        "up_to_date": 4,
        "accurate": 4,
        "thorough": 3,
        "useful": 4,
        "organized": 3,
        "concise": 3,
        "consistent": 4,
        "complete": 3,
        "actionable": 4
    }
    '''
    
    mock_create = Mock(return_value=mock_response)
    monkeypatch.setattr('openai.ChatCompletion.create', mock_create)
    return mock_create

@pytest.fixture
def sample_clinical_note():
    return """
    Patient: John Doe, 45-year-old male
    Chief Complaint: Chest pain
    
    History of Present Illness:
    Patient presents with acute onset chest pain that started 2 hours ago.
    Pain is described as crushing, substernal, radiating to left arm.
    Associated with shortness of breath and diaphoresis.
    
    Assessment and Plan:
    1. Acute coronary syndrome - obtain EKG, cardiac enzymes
    2. Start aspirin, nitroglycerin
    3. Cardiology consultation
    4. Monitor in CCU
    """ 