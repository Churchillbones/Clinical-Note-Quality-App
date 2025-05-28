from typing import Dict, Any
from .o3_judge import score_with_o3
from .heuristics import analyze_heuristics, get_heuristic_composite
from .factuality import analyze_factuality
from config import Config
import logging

logger = logging.getLogger(__name__)

def calculate_overall_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 4.5:
        return "A"
    elif score >= 3.5:
        return "B"
    elif score >= 2.5:
        return "C"
    elif score >= 1.5:
        return "D"
    else:
        return "F"

def grade_note_hybrid(clinical_note: str, encounter_transcript: str = "") -> Dict[str, Any]:
    """
    Grade clinical note using hybrid approach:
    - PDQI-9 scores from O3 (70% weight)
    - Heuristic analysis (20% weight)  
    - Factuality check (10% weight)
    """
    logger.info("Starting hybrid grading pipeline")
    
    # Get PDQI-9 scores from O3
    pdqi_scores = score_with_o3(clinical_note)
    pdqi_average = sum(pdqi_scores.values()) / len(pdqi_scores)
    
    # Get heuristic analysis
    heuristics = analyze_heuristics(clinical_note)
    heuristic_score = get_heuristic_composite(heuristics)
    
    # Get factuality analysis (O3 based)
    factuality_analysis_result = analyze_factuality(clinical_note, encounter_transcript)
    # The consistency_score from O3 is already in the 1-5 range.
    factuality_score = factuality_analysis_result['consistency_score']
    
    # Calculate weighted hybrid score
    hybrid_score = (
        pdqi_average * Config.PDQI_WEIGHT +
        heuristic_score * Config.HEURISTIC_WEIGHT +
        factuality_score * Config.FACTUALITY_WEIGHT
    )
    
    # Ensure score is in valid range
    hybrid_score = max(1.0, min(5.0, hybrid_score))
    
    result = {
        'pdqi_scores': pdqi_scores,
        'pdqi_average': round(pdqi_average, 2),
        'heuristic_analysis': {
            'length_score': round(heuristics['length_score'], 2),
            'redundancy_score': round(heuristics['redundancy_score'], 2),
            'structure_score': round(heuristics['structure_score'], 2),
            'composite_score': round(heuristic_score, 2),
            'word_count': heuristics['word_count'],
            'character_count': heuristics['character_count']
        },
        'factuality_analysis': {
            # 'entailment_score' is no longer applicable with the new O3 approach for factuality.
            # We directly use 'consistency_score'.
            'consistency_score': round(factuality_analysis_result['consistency_score'], 2),
            'claims_checked': factuality_analysis_result['claims_checked'] # Now 0 or 1
        },
        'hybrid_score': round(hybrid_score, 2),
        'overall_grade': calculate_overall_grade(hybrid_score),
        'weights_used': {
            'pdqi_weight': Config.PDQI_WEIGHT,
            'heuristic_weight': Config.HEURISTIC_WEIGHT,
            'factuality_weight': Config.FACTUALITY_WEIGHT
        }
    }
    
    logger.info(f"Hybrid grading completed. Overall score: {hybrid_score:.2f}")
    return result 