"""Observability infrastructure for structured logging, metrics, and tracing.

This module provides standardized logging configuration and request correlation
for the Clinical Note Quality application.
"""
from __future__ import annotations

import logging
import uuid
import time
import json
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field

try:
    import structlog
except ImportError:
    structlog = None

try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
except ImportError:
    Counter = None
    Histogram = None
    generate_latest = None
    CONTENT_TYPE_LATEST = None

logger = logging.getLogger(__name__)

# Context variable for correlation IDs
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def configure_structured_logging(*, json_logs: bool = False) -> None:
    """Configure structured logging for the application."""
    if not structlog:
        # Fallback to standard logging if structlog is not available
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        return
    
    # Configure structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="ISO"),
        add_correlation_id,
    ]
    
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=False),
        ])
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
        cache_logger_on_first_use=True,
    )


def add_correlation_id(logger: Any, name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add correlation ID to log events."""
    correlation_id = correlation_id_var.get()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def get_correlation_id() -> str:
    """Get or create a correlation ID for the current context."""
    correlation_id = correlation_id_var.get()
    if not correlation_id:
        correlation_id = str(uuid.uuid4())[:8]
        correlation_id_var.set(correlation_id)
    return correlation_id


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context."""
    correlation_id_var.set(correlation_id)


def get_logger(name: str) -> Any:
    """Get a structured logger instance."""
    if structlog:
        return structlog.get_logger(name)
    else:
        return logging.getLogger(name)


# Module-level function definitions that are always available
def record_grading_request(
    precision: str,
    model_provenance: str,
    status: str,
    duration: Optional[float] = None
) -> None:
    """Record metrics for a grading request."""
    pass  # Will be replaced below


def record_pdqi_score(dimension: str, score: float, model_provenance: str) -> None:
    """Record a PDQI dimension score."""
    pass  # Will be replaced below


def get_metrics() -> tuple[str, str]:
    """Get current metrics in Prometheus format."""
    return "# Metrics not configured\n", "text/plain"  # Will be replaced below


# Prometheus metrics (if available)
if Counter is not None and Histogram is not None and generate_latest is not None and CONTENT_TYPE_LATEST is not None:
    # Request metrics
    request_counter = Counter(
        "clinical_note_grading_requests_total",
        "Total number of grading requests",
        ["precision", "model_provenance", "status"]
    )
    
    request_duration = Histogram(
        "clinical_note_grading_duration_seconds",
        "Time spent grading clinical notes",
        ["precision", "model_provenance"]
    )
    
    # PDQI metrics
    pdqi_scores = Histogram(
        "clinical_note_pdqi_scores",
        "PDQI score distributions",
        ["dimension", "model_provenance"],
        buckets=(1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)
    )
    
    def record_grading_request(
        precision: str,
        model_provenance: str,
        status: str,
        duration: Optional[float] = None
    ) -> None:
        """Record metrics for a grading request."""
        request_counter.labels(
            precision=precision,
            model_provenance=model_provenance,
            status=status
        ).inc()
        
        if duration is not None:
            request_duration.labels(
                precision=precision,
                model_provenance=model_provenance
            ).observe(duration)
    
    def record_pdqi_score(dimension: str, score: float, model_provenance: str) -> None:
        """Record a PDQI dimension score."""
        pdqi_scores.labels(
            dimension=dimension,
            model_provenance=model_provenance
        ).observe(score)
    
    def get_metrics() -> tuple[str, str]:
        """Get current metrics in Prometheus format."""
        if generate_latest is None:
            return "# Prometheus metrics not available\n", "text/plain"
        
        metrics_data = generate_latest()
        # Decode bytes to string if needed
        if isinstance(metrics_data, bytes):
            metrics_data = metrics_data.decode('utf-8')
        # Ensure CONTENT_TYPE_LATEST is not None
        content_type = CONTENT_TYPE_LATEST or "text/plain; version=0.0.4; charset=utf-8"
        return metrics_data, content_type

else:
    # When Prometheus is not available, keep the stub implementations
    def record_grading_request(
        precision: str,
        model_provenance: str,
        status: str,
        duration: Optional[float] = None
    ) -> None:
        """Record metrics for a grading request (stub when Prometheus unavailable)."""
        pass
    
    def record_pdqi_score(dimension: str, score: float, model_provenance: str) -> None:
        """Record a PDQI dimension score (stub when Prometheus unavailable)."""
        pass
    
    def get_metrics() -> tuple[str, str]:
        """Get current metrics in Prometheus format (stub when Prometheus unavailable)."""
        return "# Prometheus metrics not available\n", "text/plain"


class RequestTracker:
    """Context manager for tracking request metrics and correlation."""
    
    def __init__(self, precision: str = "medium", model_provenance: str = "unknown"):
        self.precision = precision
        self.model_provenance = model_provenance
        self.start_time: Optional[float] = None
        self.correlation_id = get_correlation_id()
        
    def __enter__(self) -> str:
        """Start tracking a request."""
        import time
        self.start_time = time.time()
        set_correlation_id(self.correlation_id)
        
        logger = get_logger(__name__)
        logger.info(
            "Request started",
            precision=self.precision,
            model_provenance=self.model_provenance,
            correlation_id=self.correlation_id
        )
        return self.correlation_id
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Complete request tracking."""
        import time
        
        duration = time.time() - self.start_time if self.start_time else None
        status = "error" if exc_type else "success"
        
        logger = get_logger(__name__)
        logger.info(
            "Request completed",
            precision=self.precision,
            model_provenance=self.model_provenance,
            status=status,
            duration_seconds=duration,
            correlation_id=self.correlation_id,
            error_type=exc_type.__name__ if exc_type else None
        )
        
        record_grading_request(
            precision=self.precision,
            model_provenance=self.model_provenance,
            status=status,
            duration=duration
        ) 


@dataclass
class ReasoningStep:
    """Individual step in the reasoning process."""
    component: str  # "pdqi", "factuality", "heuristic"
    step_type: str  # "analysis", "scoring", "validation"
    description: str
    details: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "step_type": self.step_type, 
            "description": self.description,
            "details": self.details or {},
            "timestamp": self.timestamp
        }


@dataclass
class AssessmentReasoning:
    """Internal reasoning tracker for comprehensive assessment documentation."""
    correlation_id: str
    steps: List[ReasoningStep] = field(default_factory=list)
    model_reasoning: Dict[str, str] = field(default_factory=dict)  # Component -> reasoning text
    fallback_events: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)

    def add_step(self, component: str, step_type: str, description: str, details: Optional[Dict[str, Any]] = None):
        """Add a reasoning step for internal documentation."""
        step = ReasoningStep(component, step_type, description, details)
        self.steps.append(step)
        logger.info(f"Reasoning step: {component}.{step_type} - {description}")

    def add_model_reasoning(self, component: str, reasoning_text: str):
        """Capture model reasoning output for internal documentation."""
        self.model_reasoning[component] = reasoning_text
        logger.info(f"Model reasoning captured for {component}: {len(reasoning_text)} chars")

    def add_fallback_event(self, event_description: str):
        """Document fallback events (e.g., API failures)."""
        self.fallback_events.append(event_description)
        logger.warning(f"Fallback event: {event_description}")

    def add_performance_metric(self, metric_name: str, value: float):
        """Track performance metrics for internal analysis."""
        self.performance_metrics[metric_name] = value

    def get_chain_of_thought(self) -> str:
        """Generate comprehensive chain of thought for internal documentation."""
        parts = []
        
        # Add component reasoning if available
        for component, reasoning in self.model_reasoning.items():
            if reasoning.strip():
                parts.append(f"{component.upper()} Reasoning:\n{reasoning.strip()}")
        
        # Add step summary
        if self.steps:
            step_summary = []
            for step in self.steps:
                step_summary.append(f"• {step.component}.{step.step_type}: {step.description}")
            parts.append("Assessment Steps:\n" + "\n".join(step_summary))
        
        # Add fallback events if any
        if self.fallback_events:
            parts.append("Fallback Events:\n" + "\n".join(f"• {event}" for event in self.fallback_events))
        
        return "\n\n".join(parts)

    def get_internal_summary(self) -> Dict[str, Any]:
        """Generate complete internal summary for logging/debugging."""
        return {
            "correlation_id": self.correlation_id,
            "total_steps": len(self.steps),
            "components_with_reasoning": list(self.model_reasoning.keys()),
            "fallback_count": len(self.fallback_events),
            "performance_metrics": self.performance_metrics,
            "chain_of_thought": self.get_chain_of_thought()
        }

    def log_complete_assessment(self):
        """Log the complete assessment reasoning for internal documentation."""
        summary = self.get_internal_summary()
        logger.info(f"Assessment reasoning summary: {json.dumps(summary, indent=2)}")


# Global reasoning tracker
_current_reasoning: Optional[AssessmentReasoning] = None


@contextmanager
def assessment_reasoning(correlation_id: str):
    """Context manager for tracking assessment reasoning."""
    global _current_reasoning
    old_reasoning = _current_reasoning
    _current_reasoning = AssessmentReasoning(correlation_id)
    
    try:
        yield _current_reasoning
    finally:
        if _current_reasoning:
            _current_reasoning.log_complete_assessment()
        _current_reasoning = old_reasoning


def get_current_reasoning() -> Optional[AssessmentReasoning]:
    """Get current reasoning tracker if available."""
    return _current_reasoning 