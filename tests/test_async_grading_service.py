"""Tests for async grading service functionality."""
import asyncio
import pytest
from unittest.mock import Mock, patch

from clinical_note_quality.services.grading_service import GradingService
from clinical_note_quality.domain import PDQIScore, HeuristicResult, FactualityResult, HybridResult


@pytest.fixture
def mock_services():
    """Mock all the individual services."""
    pdqi_service = Mock()
    pdqi_service.score.return_value = PDQIScore(
        scores={
            "up_to_date": 4.0,
            "accurate": 4.0,
            "thorough": 3.0,
            "useful": 4.0,
            "organized": 3.0,
            "concise": 3.0,
            "consistent": 4.0,
            "complete": 3.0,
            "actionable": 4.0,
        },
        summary="Test summary",
        rationale="Test rationale",
        model_provenance="test",
    )
    
    heuristic_service = Mock()
    heuristic_service.analyze.return_value = HeuristicResult(
        length_score=3.5,
        redundancy_score=4.0,
        structure_score=3.8,
        composite_score=3.77,
        word_count=150,
        character_count=750,
    )
    
    factuality_service = Mock()
    factuality_service.assess.return_value = FactualityResult(
        consistency_score=4.2,
        claims_checked=3,
        summary="Factuality test summary",
        claims=[],
    )
    
    return pdqi_service, heuristic_service, factuality_service


@pytest.fixture
def grading_service(mock_services):
    """Create grading service with mocked dependencies."""
    pdqi_service, heuristic_service, factuality_service = mock_services
    
    with patch('clinical_note_quality.services.grading_service.get_settings') as mock_settings:
        mock_settings.return_value.PDQI_WEIGHT = 0.5
        mock_settings.return_value.HEURISTIC_WEIGHT = 0.3
        mock_settings.return_value.FACTUALITY_WEIGHT = 0.2
        
        service = GradingService(
            pdqi_service=pdqi_service,
            heuristic_service=heuristic_service,
            factuality_service=factuality_service,
        )
        return service


@pytest.mark.asyncio
async def test_grade_async_basic_functionality(grading_service):
    """Test that async grading returns a valid HybridResult."""
    note = "This is a test clinical note."
    transcript = "Test transcript"
    
    result = await grading_service.grade_async(note, transcript, precision="medium")
    
    assert isinstance(result, HybridResult)
    assert result.hybrid_score > 0
    assert result.overall_grade in ["A", "B", "C", "D", "F"]
    assert "pdqi_weight" in result.weights_used
    assert "heuristic_weight" in result.weights_used
    assert "factuality_weight" in result.weights_used


@pytest.mark.asyncio
async def test_grade_async_calls_all_services(grading_service, mock_services):
    """Test that async grading calls all three subsystem services."""
    pdqi_service, heuristic_service, factuality_service = mock_services
    note = "Test note"
    transcript = "Test transcript"
    
    await grading_service.grade_async(note, transcript, precision="high")
    
    # Verify all services were called
    pdqi_service.score.assert_called_once()
    heuristic_service.analyze.assert_called_once_with(note)
    factuality_service.assess.assert_called_once()


@pytest.mark.asyncio
async def test_grade_async_concurrency():
    """Test that async version provides concurrent execution."""
    # This is a basic test - we can't easily test actual concurrency without more complex setup
    # but we can at least verify the async method completes
    
    with patch('clinical_note_quality.services.grading_service.get_settings') as mock_settings:
        mock_settings.return_value.PDQI_WEIGHT = 0.5
        mock_settings.return_value.HEURISTIC_WEIGHT = 0.3
        mock_settings.return_value.FACTUALITY_WEIGHT = 0.2
        
        with patch('clinical_note_quality.services.get_pdqi_service') as mock_pdqi:
            with patch('clinical_note_quality.services.get_heuristic_service') as mock_heur:
                with patch('clinical_note_quality.services.get_factuality_service') as mock_fact:
                    
                    # Setup mocks
                    mock_pdqi.return_value.score.return_value = PDQIScore(
                        scores={dim: 3.0 for dim in [
                            "up_to_date", "accurate", "thorough", "useful", 
                            "organized", "concise", "consistent", "complete", "actionable"
                        ]},
                        model_provenance="test"
                    )
                    mock_heur.return_value.analyze.return_value = HeuristicResult(
                        length_score=3.0, redundancy_score=3.0, structure_score=3.0,
                        composite_score=3.0, word_count=100, character_count=500
                    )
                    mock_fact.return_value.assess.return_value = FactualityResult(
                        consistency_score=3.0, claims_checked=1
                    )
                    
                    service = GradingService()
                    result = await service.grade_async("Test note")
                    
                    assert isinstance(result, HybridResult)


def test_sync_and_async_consistency(grading_service):
    """Test that sync and async versions produce similar results."""
    note = "Test clinical note"
    transcript = "Test transcript"
    
    # Get sync result
    sync_result = grading_service.grade(note, transcript)
    
    # Get async result
    async_result = asyncio.run(grading_service.grade_async(note, transcript))
    
    # Results should be very similar (allowing for small floating point differences)
    assert abs(sync_result.hybrid_score - async_result.hybrid_score) < 0.01
    assert sync_result.overall_grade == async_result.overall_grade
    assert sync_result.pdqi.model_provenance == async_result.pdqi.model_provenance 