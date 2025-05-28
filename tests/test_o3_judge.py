import pytest
from grading.o3_judge import O3Judge, score_with_o3

def test_o3_judge_success(mock_openai, sample_clinical_note):
    """Test O3 judge returns valid PDQI-9 scores."""
    judge = O3Judge()
    scores = judge.score_pdqi9(sample_clinical_note)
    
    # Check all required keys present
    required_keys = [
        'up_to_date', 'accurate', 'thorough', 'useful',
        'organized', 'concise', 'consistent', 'complete', 'actionable'
    ]
    assert all(key in scores for key in required_keys)
    
    # Check all scores in valid range
    for key, value in scores.items():
        assert isinstance(value, int)
        assert 1 <= value <= 5

def test_o3_judge_api_failure(monkeypatch, sample_clinical_note):
    """Test O3 judge handles API failures gracefully."""
    def mock_create_failure(*args, **kwargs):
        raise Exception("API Error")
    
    monkeypatch.setattr('openai.ChatCompletion.create', mock_create_failure)
    
    judge = O3Judge()
    scores = judge.score_pdqi9(sample_clinical_note)
    
    # Should return default scores
    assert all(score == 3 for score in scores.values())

def test_score_with_o3_convenience(mock_openai, sample_clinical_note):
    """Test convenience function works correctly."""
    scores = score_with_o3(sample_clinical_note)
    assert len(scores) == 9
    assert all(1 <= score <= 5 for score in scores.values()) 