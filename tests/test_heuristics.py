import pytest
from grading.heuristics import (
    calculate_length_score, 
    calculate_redundancy_score,
    calculate_structure_score,
    analyze_heuristics,
    get_heuristic_composite
)

def test_length_score_optimal():
    """Test length scoring for optimal word count."""
    text = " ".join(["word"] * 300)  # 300 words
    score = calculate_length_score(text)
    assert score == 5.0

def test_length_score_too_short():
    """Test length scoring for too short text."""
    text = "Short note"
    score = calculate_length_score(text)
    assert score == 1.0

def test_length_score_too_long():
    """Test length scoring for too long text."""
    text = " ".join(["word"] * 1500)  # 1500 words
    score = calculate_length_score(text)
    assert score == 1.0

def test_redundancy_score_low():
    """Test redundancy scoring for non-repetitive text."""
    text = "This is a unique sentence. Here is another different sentence."
    score = calculate_redundancy_score(text)
    assert score >= 4.0

def test_redundancy_score_high():
    """Test redundancy scoring for repetitive text."""
    text = "The patient has pain. The patient has pain. The patient has pain."
    score = calculate_redundancy_score(text)
    assert score <= 2.0

def test_structure_score_basic():
    """Test basic structure scoring."""
    text = "Chief Complaint: Pain\nHistory: Patient reports pain\nPlan: Treatment"
    score = calculate_structure_score(text)
    assert score >= 3.0

def test_analyze_heuristics_complete(sample_clinical_note):
    """Test complete heuristic analysis."""
    result = analyze_heuristics(sample_clinical_note)
    
    required_keys = ['length_score', 'redundancy_score', 'structure_score', 
                    'word_count', 'character_count']
    assert all(key in result for key in required_keys)
    
    assert isinstance(result['word_count'], int)
    assert isinstance(result['character_count'], int)

def test_heuristic_composite():
    """Test heuristic composite calculation."""
    heuristics = {
        'length_score': 4.0,
        'redundancy_score': 3.0,
        'structure_score': 5.0
    }
    composite = get_heuristic_composite(heuristics)
    assert composite == 4.0  # (4+3+5)/3 