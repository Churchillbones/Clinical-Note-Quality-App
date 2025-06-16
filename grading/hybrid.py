from typing import Dict, Any
from .o3_judge import score_with_o3
from .heuristics import analyze_heuristics, get_heuristic_composite
from .factuality import analyze_factuality, analyze_factuality_with_agent
import asyncio
from config import Config
import logging
import warnings

warnings.warn(
    "'grading.hybrid' is deprecated; use 'clinical_note_quality.services.grading_service' instead.",
    DeprecationWarning,
    stacklevel=2,
)

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

def grade_note_hybrid(clinical_note: str, encounter_transcript: str = "", model_precision: str = "medium") -> Dict[str, Any]:
    """
    Grade clinical note using hybrid approach:
    - PDQI-9 scores from O3 (70% weight)
    - Heuristic analysis (20% weight)  
    - Factuality check (10% weight)
    """
    logger.info("Starting hybrid grading pipeline")
    
    if encounter_transcript is None:
        encounter_transcript = ""
    
    # Strategy: Use Nine Rings architecture if explicitly enabled via env var; otherwise default to O3
    use_nine_rings = bool(Config.__dict__.get("USE_NINE_RINGS") or False)
    if use_nine_rings:
        try:
            from .nine_rings import score_with_nine_rings  # Local import to avoid circular deps
            pdqi_scores = score_with_nine_rings(clinical_note)
        except Exception as e:
            logger.error(f"NineRings evaluation failed, falling back to O3: {e}")
            pdqi_scores = score_with_o3(clinical_note)
    else:
        pdqi_scores = score_with_o3(clinical_note)
    # Cast any numeric strings like "4" or "4.0" to float for consistency
    for key, val in list(pdqi_scores.items()):
        if key != 'summary' and isinstance(val, str):
            try:
                pdqi_scores[key] = float(val)
            except ValueError:
                pass  # leave as-is if not convertible
    # Only sum numeric values (exclude 'summary' and any non-numeric entries)
    pdqi_numeric_scores = [v for k, v in pdqi_scores.items() if isinstance(v, (int, float))]
    pdqi_average = sum(pdqi_numeric_scores) / len(pdqi_numeric_scores) if pdqi_numeric_scores else 0
    
    # Auto-generate a concise narrative summary if missing or empty
    def _generate_pdqi_summary(scores_dict):
        numeric_items = {k: v for k, v in scores_dict.items() if k not in {"summary", "rationale"} and isinstance(v, (int, float))}
        if not numeric_items:
            return ""
        strengths = [k for k, v in numeric_items.items() if v >= 4]
        weaknesses = [k for k, v in numeric_items.items() if v <= 2]
        parts = []
        if strengths:
            parts.append("Strong in " + ", ".join(strengths).replace('_', ' '))
        if weaknesses:
            parts.append("Needs improvement in " + ", ".join(weaknesses).replace('_', ' '))
        return "; ".join(parts).capitalize() + "."

    if not isinstance(pdqi_scores.get('summary'), str) or not pdqi_scores.get('summary').strip():
        pdqi_scores['summary'] = _generate_pdqi_summary(pdqi_scores)
    
    # Get heuristic analysis
    heuristics = analyze_heuristics(clinical_note)
    heuristic_score = get_heuristic_composite(heuristics)
    
    # --- Factuality: Use agent-based if transcript and GPT-4o config, else fallback ---
    factuality_analysis_result = None
    if encounter_transcript.strip() and hasattr(Config, 'AZURE_OPENAI_KEY') and hasattr(Config, 'AZURE_OPENAI_ENDPOINT') and hasattr(Config, 'AZURE_GPT4O_API_VERSION') and hasattr(Config, 'GPT4O_DEPLOYMENT'):
        try:
            factuality_analysis_result = asyncio.run(
                analyze_factuality_with_agent(
                    clinical_note,
                    encounter_transcript,
                    api_key=Config.AZURE_OPENAI_KEY,
                    azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                    api_version=Config.AZURE_GPT4O_API_VERSION,
                    model_name=Config.GPT4O_DEPLOYMENT
                )
            )
        except Exception as e:
            logger.error(f"Agent-based factuality failed, falling back to O3: {e}")
            factuality_analysis_result = analyze_factuality(clinical_note, encounter_transcript)
    else:
        factuality_analysis_result = analyze_factuality(clinical_note, encounter_transcript)
    factuality_score = factuality_analysis_result['consistency_score']
    
    # --- Build chain of thought for debugging/review purposes ---
    chain_of_thought_parts = []
    if isinstance(pdqi_scores.get('rationale'), str) and pdqi_scores.get('rationale').strip():
        chain_of_thought_parts.append("PDQI Rationale:\n" + pdqi_scores['rationale'].strip())
    # Include the raw PDQI summary as well if present
    if isinstance(pdqi_scores.get('summary'), str) and pdqi_scores.get('summary').strip():
        chain_of_thought_parts.append("PDQI Summary:\n" + pdqi_scores['summary'].strip())

    # Add claim-level explanations from factuality agent if available
    factual_claims = factuality_analysis_result.get('claims', [])
    if factual_claims:
        coherent_claims = [
            f"• {claim.get('claim')} => {claim.get('support')} - {claim.get('explanation')}" for claim in factual_claims
        ]
        chain_of_thought_parts.append("Factuality Claim Analysis:\n" + "\n".join(coherent_claims))

    chain_of_thought = "\n\n".join(chain_of_thought_parts)

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
            'consistency_score': round(factuality_analysis_result['consistency_score'], 2),
            'claims_checked': factuality_analysis_result['claims_checked'],
            'summary': factuality_analysis_result.get('summary', ''),
            'claims': factuality_analysis_result.get('claims', [])
        },
        'hybrid_score': round(hybrid_score, 2),
        'overall_grade': calculate_overall_grade(hybrid_score),
        'weights_used': {
            'pdqi_weight': Config.PDQI_WEIGHT,
            'heuristic_weight': Config.HEURISTIC_WEIGHT,
            'factuality_weight': Config.FACTUALITY_WEIGHT
        },
        'chain_of_thought': chain_of_thought
    }
    
    logger.info(f"Hybrid grading completed. Overall score: {hybrid_score:.2f}")
    return result