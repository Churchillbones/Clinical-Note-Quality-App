import pytest
from grading.hybrid import grade_note_hybrid, calculate_overall_grade

def test_calculate_overall_grade():
    """Test grade calculation from numeric scores."""
    assert calculate_overall_grade(4.7) == "A"
    assert calculate_overall_grade(3.8) == "B"
    assert calculate_overall_grade(2.7) == "C"
    assert calculate_overall_grade(1.8) == "D"
    assert calculate_overall_grade(1.2) == "F"

def test_grade_note_hybrid_complete(mock_openai, sample_clinical_note):
    """Test complete hybrid grading pipeline."""
    result = grade_note_hybrid(sample_clinical_note, "")
    
    # Check all required sections present
    required_keys = [
        'pdqi_scores', 'pdqi_average', 'heuristic_analysis',
        'factuality_analysis', 'hybrid_score', 'overall_grade', 'weights_used'
    ]
    assert all(key in result for key in required_keys)
    
    # Check score ranges
    assert 1.0 <= result['hybrid_score'] <= 5.0
    assert result['overall_grade'] in ['A', 'B', 'C', 'D', 'F']
    
    # Check PDQI scores
    assert len(result['pdqi_scores']) == 9
    assert all(1 <= score <= 5 for score in result['pdqi_scores'].values())

def test_grade_note_hybrid_with_transcript(mock_openai, sample_clinical_note):
    """Test hybrid grading with encounter transcript."""
    transcript = "Patient reported acute chest pain with radiation to left arm"
    result = grade_note_hybrid(sample_clinical_note, transcript)
    
    assert result['factuality_analysis']['claims_checked'] >= 0
    assert 1.0 <= result['hybrid_score'] <= 5.0 