import pytest
from unittest.mock import patch
from grading.hybrid import grade_note_hybrid, calculate_overall_grade
from config import Config # Import Config to use actual weights

# Sample clinical note for testing
@pytest.fixture
def sample_clinical_note():
    return "Patient presents with cough and fever."

# --- Test calculate_overall_grade ---
def test_calculate_overall_grade():
    """Test grade calculation from numeric scores."""
    assert calculate_overall_grade(5.0) == "A"
    assert calculate_overall_grade(4.5) == "A"
    assert calculate_overall_grade(4.49) == "B"
    assert calculate_overall_grade(3.5) == "B"
    assert calculate_overall_grade(3.49) == "C"
    assert calculate_overall_grade(2.5) == "C"
    assert calculate_overall_grade(2.49) == "D"
    assert calculate_overall_grade(1.5) == "D"
    assert calculate_overall_grade(1.49) == "F"
    assert calculate_overall_grade(0.0) == "F" # Test edge case

# --- Mocks for dependencies ---
MOCK_PDQI_SCORES = {
    'up_to_date': 4, 'accurate': 3, 'thorough': 4, 'useful': 3,
    'organized': 4, 'concise': 3, 'consistent': 4, 'complete': 3, 'actionable': 4
} # Average = 3.55...
MOCK_PDQI_AVERAGE = sum(MOCK_PDQI_SCORES.values()) / len(MOCK_PDQI_SCORES) # Approx 3.56

MOCK_HEURISTICS_RESULT = {
    'length_score': 4.0, 'redundancy_score': 3.0, 'structure_score': 4.5,
    'word_count': 200, 'character_count': 1200
}
MOCK_HEURISTIC_COMPOSITE = (MOCK_HEURISTICS_RESULT['length_score'] + 
                           MOCK_HEURISTICS_RESULT['redundancy_score'] + 
                           MOCK_HEURISTICS_RESULT['structure_score']) / 3 # Approx 3.83

MOCK_FACTUALITY_RESULT_WITH_TRANSCRIPT = {
    'consistency_score': 4.0, 
    'claims_checked': 1
}
MOCK_FACTUALITY_RESULT_NO_TRANSCRIPT = {
    'consistency_score': 3.0, # Neutral score
    'claims_checked': 0
}

@patch('grading.hybrid.analyze_factuality')
@patch('grading.hybrid.get_heuristic_composite') # Mock the composite directly for simplicity
@patch('grading.hybrid.analyze_heuristics') # Still need to mock analyze_heuristics as it's called
@patch('grading.hybrid.score_with_o3')
def test_grade_note_hybrid_no_transcript(
    mock_score_o3, mock_analyze_heuristics, mock_get_heuristic_composite, 
    mock_analyze_factuality, sample_clinical_note
):
    """Test complete hybrid grading pipeline without transcript."""
    mock_score_o3.return_value = MOCK_PDQI_SCORES
    mock_analyze_heuristics.return_value = MOCK_HEURISTICS_RESULT # analyze_heuristics is called
    mock_get_heuristic_composite.return_value = MOCK_HEURISTIC_COMPOSITE # get_heuristic_composite is called
    mock_analyze_factuality.return_value = MOCK_FACTUALITY_RESULT_NO_TRANSCRIPT

    result = grade_note_hybrid(sample_clinical_note, "") # No transcript
    
    required_keys = [
        'pdqi_scores', 'pdqi_average', 'heuristic_analysis',
        'factuality_analysis', 'hybrid_score', 'overall_grade', 'weights_used'
    ]
    assert all(key in result for key in required_keys)
    
    assert result['pdqi_scores'] == MOCK_PDQI_SCORES
    assert result['pdqi_average'] == round(MOCK_PDQI_AVERAGE, 2)
    
    assert result['heuristic_analysis']['length_score'] == MOCK_HEURISTICS_RESULT['length_score']
    assert result['heuristic_analysis']['composite_score'] == round(MOCK_HEURISTIC_COMPOSITE, 2)
    
    assert result['factuality_analysis']['consistency_score'] == MOCK_FACTUALITY_RESULT_NO_TRANSCRIPT['consistency_score']
    assert result['factuality_analysis']['claims_checked'] == 0
    
    expected_hybrid_score = (
        MOCK_PDQI_AVERAGE * Config.PDQI_WEIGHT +
        MOCK_HEURISTIC_COMPOSITE * Config.HEURISTIC_WEIGHT +
        MOCK_FACTUALITY_RESULT_NO_TRANSCRIPT['consistency_score'] * Config.FACTUALITY_WEIGHT
    )
    expected_hybrid_score = max(1.0, min(5.0, expected_hybrid_score)) # Apply clamping
    
    assert result['hybrid_score'] == round(expected_hybrid_score, 2)
    assert result['overall_grade'] == calculate_overall_grade(expected_hybrid_score)
    assert result['weights_used']['pdqi_weight'] == Config.PDQI_WEIGHT

    mock_score_o3.assert_called_once_with(sample_clinical_note)
    mock_analyze_heuristics.assert_called_once_with(sample_clinical_note)
    mock_get_heuristic_composite.assert_called_once_with(MOCK_HEURISTICS_RESULT)
    mock_analyze_factuality.assert_called_once_with(sample_clinical_note, "")


@patch('grading.hybrid.analyze_factuality')
@patch('grading.hybrid.get_heuristic_composite')
@patch('grading.hybrid.analyze_heuristics')
@patch('grading.hybrid.score_with_o3')
def test_grade_note_hybrid_with_transcript(
    mock_score_o3, mock_analyze_heuristics, mock_get_heuristic_composite,
    mock_analyze_factuality, sample_clinical_note
):
    """Test complete hybrid grading pipeline with transcript."""
    transcript = "Patient reported acute chest pain."
    mock_score_o3.return_value = MOCK_PDQI_SCORES
    mock_analyze_heuristics.return_value = MOCK_HEURISTICS_RESULT
    mock_get_heuristic_composite.return_value = MOCK_HEURISTIC_COMPOSITE
    mock_analyze_factuality.return_value = MOCK_FACTUALITY_RESULT_WITH_TRANSCRIPT

    result = grade_note_hybrid(sample_clinical_note, transcript)
        
    assert result['factuality_analysis']['consistency_score'] == MOCK_FACTUALITY_RESULT_WITH_TRANSCRIPT['consistency_score']
    assert result['factuality_analysis']['claims_checked'] == 1
    
    expected_hybrid_score = (
        MOCK_PDQI_AVERAGE * Config.PDQI_WEIGHT +
        MOCK_HEURISTIC_COMPOSITE * Config.HEURISTIC_WEIGHT +
        MOCK_FACTUALITY_RESULT_WITH_TRANSCRIPT['consistency_score'] * Config.FACTUALITY_WEIGHT
    )
    expected_hybrid_score = max(1.0, min(5.0, expected_hybrid_score))
    
    assert result['hybrid_score'] == round(expected_hybrid_score, 2)
    assert result['overall_grade'] == calculate_overall_grade(expected_hybrid_score)

    mock_analyze_factuality.assert_called_once_with(sample_clinical_note, transcript)