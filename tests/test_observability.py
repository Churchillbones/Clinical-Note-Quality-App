"""Tests for observability functionality."""
import pytest
from unittest.mock import patch, Mock

from clinical_note_quality.observability import (
    configure_structured_logging,
    get_logger,
    get_correlation_id,
    set_correlation_id,
    RequestTracker,
    record_grading_request,
    record_pdqi_score,
    get_metrics,
)


def test_configure_structured_logging():
    """Test that structured logging can be configured without errors."""
    # Should not raise any exceptions
    configure_structured_logging()
    configure_structured_logging(json_logs=True)


def test_get_logger():
    """Test that logger can be obtained."""
    logger = get_logger("test")
    assert logger is not None
    
    # Should be able to call logging methods
    logger.info("Test message", key="value")


def test_correlation_id():
    """Test correlation ID functionality."""
    # Should generate a correlation ID
    correlation_id = get_correlation_id()
    assert isinstance(correlation_id, str)
    assert len(correlation_id) == 8
    
    # Should persist the same ID
    same_id = get_correlation_id()
    assert correlation_id == same_id
    
    # Should be able to set a custom ID
    set_correlation_id("custom123")
    assert get_correlation_id() == "custom123"


def test_request_tracker():
    """Test RequestTracker context manager."""
    with RequestTracker(precision="high", model_provenance="test") as correlation_id:
        assert isinstance(correlation_id, str)
        assert get_correlation_id() == correlation_id


def test_request_tracker_with_exception():
    """Test RequestTracker handles exceptions properly."""
    try:
        with RequestTracker(precision="high", model_provenance="test"):
            raise ValueError("Test exception")
    except ValueError:
        pass  # Expected


def test_metrics_functions():
    """Test that metrics functions can be called without errors."""
    # Should not raise exceptions even if prometheus is not available
    record_grading_request(
        precision="medium",
        model_provenance="test",
        status="success",
        duration=1.5
    )
    
    record_pdqi_score("accurate", 4.0, "test")
    
    metrics_data, content_type = get_metrics()
    assert isinstance(metrics_data, str)
    assert isinstance(content_type, str)


@patch('clinical_note_quality.observability.PROMETHEUS_AVAILABLE', True)
@patch('clinical_note_quality.observability.request_counter')
@patch('clinical_note_quality.observability.request_duration')
@patch('clinical_note_quality.observability.pdqi_scores')
def test_metrics_with_prometheus(mock_pdqi_scores, mock_duration, mock_counter):
    """Test metrics recording when Prometheus is available."""
    # Mock the metrics objects
    mock_counter_labels = Mock()
    mock_counter.labels.return_value = mock_counter_labels
    
    mock_duration_labels = Mock()
    mock_duration.labels.return_value = mock_duration_labels
    
    mock_pdqi_labels = Mock()
    mock_pdqi_scores.labels.return_value = mock_pdqi_labels
    
    # Test recording metrics
    record_grading_request("high", "nine_rings", "success", 2.5)
    
    # Verify counter was called
    mock_counter.labels.assert_called_with(
        precision="high",
        model_provenance="nine_rings",
        status="success"
    )
    mock_counter_labels.inc.assert_called_once()
    
    # Verify duration was recorded
    mock_duration.labels.assert_called_with(
        precision="high",
        model_provenance="nine_rings"
    )
    mock_duration_labels.observe.assert_called_with(2.5)
    
    # Test PDQI score recording
    record_pdqi_score("thorough", 3.5, "o3")
    
    mock_pdqi_scores.labels.assert_called_with(
        dimension="thorough",
        model_provenance="o3"
    )
    mock_pdqi_labels.observe.assert_called_with(3.5) 