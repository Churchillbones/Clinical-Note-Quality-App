import openai
import json
import logging
from typing import Dict
from config import Config

logger = logging.getLogger(__name__)

def assess_consistency_with_o3(clinical_note: str, encounter_transcript: str) -> int:
    """Assess factual consistency between note and transcript using O3."""
    if not Config.AZURE_OPENAI_ENDPOINT or not Config.AZURE_OPENAI_KEY:
        logger.warning("Azure OpenAI credentials not configured. Skipping O3 factuality check.")
        return 3 # Neutral score

    try:
        messages = [
            {"role": "system", "content": Config.FACTUALITY_INSTRUCTIONS},
            {"role": "user", "content": f"Clinical Note:\n\n{clinical_note}\n\nEncounter Transcript:\n\n{encounter_transcript}"}
        ]
        
        # Initialize OpenAI client for this call specifically if not already configured globally
        # This ensures that if o3_judge.py configures it, we don't interfere, 
        # and if not, we configure it here.
        if not openai.api_base: # Check if already configured
            openai.api_type = "azure"
            openai.api_base = Config.AZURE_OPENAI_ENDPOINT
            openai.api_key = Config.AZURE_OPENAI_KEY
            openai.api_version = "2024-02-15-preview"

        response = openai.ChatCompletion.create(
            engine=Config.AZURE_O3_DEPLOYMENT,
            messages=messages,
            temperature=Config.TEMPERATURE, # Use temperature from config, typically 0.0 for deterministic
            max_tokens=200  # Expecting a small JSON response
        )
        
        content = response.choices[0].message.content.strip()
        
        try:
            score_data = json.loads(content)
            consistency_score = score_data.get('consistency_score')
            
            if isinstance(consistency_score, int) and 1 <= consistency_score <= 5:
                logger.info(f"O3 factuality scoring completed successfully. Score: {consistency_score}")
                return consistency_score
            else:
                logger.error(f"Invalid consistency score from O3: {consistency_score}. Content: {content}")
                raise ValueError(f"Invalid score format from O3 factuality check.")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse O3 JSON response for factuality: {content}. Error: {e}")
            raise ValueError(f"Invalid JSON from O3 factuality check: {e}")
            
    except Exception as e:
        logger.error(f"O3 API call for factuality failed: {e}")
        return 3 # Return neutral score on failure

def analyze_factuality(clinical_note: str, encounter_transcript: str = "") -> Dict[str, float]:
    """Analyze factual consistency between note and transcript using O3."""
    
    if not encounter_transcript.strip():
        # No transcript to check against, or transcript is only whitespace
        logger.info("No encounter transcript provided for factuality check.")
        return {
            'consistency_score': 3.0,  # Neutral score (scaled to 1-5)
            'claims_checked': 0
        }

    # Call O3 for consistency assessment
    o3_consistency_score = assess_consistency_with_o3(clinical_note, encounter_transcript)
    
    # The 'entailment_score' key was used previously. We'll keep a similar structure.
    # The new O3 prompt directly asks for a 'consistency_score' (1-5).
    return {
        'consistency_score': float(o3_consistency_score), # Already 1-5
        'claims_checked': 1 # Indicates one overall check was performed
    } 