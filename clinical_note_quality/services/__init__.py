"""Application services layer – orchestrates domain logic.""" 

from .pdqi_service import PDQIService, get_pdqi_service
from .heuristic_service import HeuristicService, get_heuristic_service
from .factuality_service import FactualityService, get_factuality_service
from .grading_service import GradingService, grade_note_hybrid

# Week 1: Semantic Gap Detection
from .semantic_gap_detector import SemanticGapDetector

# Week 2: Contradiction and Hallucination Detection
from .contradiction_detector import ContradictionDetector
from .hallucination_detector import HallucinationDetector

__all__ = [
    "PDQIService",
    "HeuristicService", 
    "FactualityService",
    "get_pdqi_service",
    "get_heuristic_service",
    "get_factuality_service",
    "GradingService",
    "grade_note_hybrid",  # Legacy compatibility
    # Week 1
    "SemanticGapDetector",
    # Week 2
    "ContradictionDetector", 
    "HallucinationDetector",
] 