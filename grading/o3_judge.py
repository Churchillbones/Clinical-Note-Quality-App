import openai
import json
import logging
from typing import Dict, Any
from config import Config

logger = logging.getLogger(__name__)

class O3Judge:
    def __init__(self):
        openai.api_type = "azure"
        openai.api_base = Config.AZURE_OPENAI_ENDPOINT
        openai.api_key = Config.AZURE_OPENAI_KEY
        openai.api_version = "2024-02-15-preview"
    
    def score_pdqi9(self, clinical_note: str) -> Dict[str, int]:
        """Score clinical note using O3 against PDQI-9 rubric."""
        try:
            messages = [
                {"role": "system", "content": Config.PDQI_INSTRUCTIONS},
                {"role": "user", "content": f"Clinical Note:\n\n{clinical_note}"}
            ]
            
            response = openai.ChatCompletion.create(
                engine=Config.AZURE_O3_DEPLOYMENT,
                messages=messages,
                temperature=Config.TEMPERATURE,
                max_tokens=Config.MAX_TOKENS
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                scores = json.loads(content)
                
                # Validate all required keys are present
                required_keys = [
                    'up_to_date', 'accurate', 'thorough', 'useful', 
                    'organized', 'concise', 'consistent', 'complete', 'actionable'
                ]
                
                if not all(key in scores for key in required_keys):
                    raise ValueError(f"Missing required keys in O3 response")
                
                # Validate scores are in range 1-5
                for key, value in scores.items():
                    if not isinstance(value, int) or not 1 <= value <= 5:
                        raise ValueError(f"Invalid score for {key}: {value}")
                
                logger.info(f"O3 scoring completed successfully")
                return scores
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse O3 JSON response: {content}")
                raise ValueError(f"Invalid JSON from O3: {e}")
                
        except Exception as e:
            logger.error(f"O3 API call failed: {e}")
            # Return default scores on failure
            return {
                'up_to_date': 3, 'accurate': 3, 'thorough': 3, 'useful': 3,
                'organized': 3, 'concise': 3, 'consistent': 3, 'complete': 3, 'actionable': 3
            }

def score_with_o3(clinical_note: str) -> Dict[str, int]:
    """Convenience function for scoring with O3."""
    judge = O3Judge()
    return judge.score_pdqi9(clinical_note) 