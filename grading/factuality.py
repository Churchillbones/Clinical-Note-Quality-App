from openai import AzureOpenAI, APIConnectionError, AuthenticationError, APIStatusError, RateLimitError, APIError
import json
import logging
from typing import Dict
from config import Config
from grading.exceptions import OpenAIServiceError, OpenAIAuthError, OpenAIResponseError

logger = logging.getLogger(__name__)

# Module-level client initialization is an option, but let's stick to function-level
# for now to maintain consistency with previous refactoring steps and avoid
# potential issues if this module is used in different contexts.

def assess_consistency_with_o3(clinical_note: str, encounter_transcript: str, model_precision: str = "medium") -> int:
    """Assess factual consistency between note and transcript using O3."""
    if not Config.AZURE_OPENAI_ENDPOINT or not Config.AZURE_OPENAI_KEY:
        # This case might be better handled by raising a specific configuration error
        # or by the calling function ensuring credentials exist before calling.
        # For now, retain warning and neutral score as per original logic for this specific check.
        logger.warning("Azure OpenAI credentials not configured for factuality check. Returning neutral score.")
        return 3 # Neutral score

    try:
        client = AzureOpenAI(
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_key=Config.AZURE_OPENAI_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION
        )

        messages = [
            {"role": "system", "content": Config.FACTUALITY_INSTRUCTIONS},
            {"role": "user", "content": f"Clinical Note:\n\n{clinical_note}\n\nEncounter Transcript:\n\n{encounter_transcript}"}
        ]
        # Select deployment based on model_precision
        if model_precision == "high":
            model_name = Config.AZURE_O3_HIGH_DEPLOYMENT
        elif model_precision == "low":
            model_name = Config.AZURE_O3_LOW_DEPLOYMENT
        else:
            model_name = Config.AZURE_O3_DEPLOYMENT
        kwargs = {"model": model_name, "messages": messages}
        # Add max_completion_tokens parameter
        kwargs["max_completion_tokens"] = 200
        
        response = client.chat.completions.create(**kwargs)
        
        content = response.choices[0].message.content.strip()
        
        # Log the raw response content for debugging
        logger.debug(f"Raw O3 factuality response content: '{content}'")
        if not content:
            logger.error("Received empty response content from Azure OpenAI factuality check.")
            raise OpenAIResponseError("Empty response from Azure OpenAI service for factuality check.")
        try:
            score_data = json.loads(content)
            consistency_score = score_data.get('consistency_score')
            
            if isinstance(consistency_score, int) and 1 <= consistency_score <= 5:
                logger.info(f"O3 factuality scoring completed successfully. Score: {consistency_score}.")
                return consistency_score
            else:
                logger.error(f"Invalid consistency score from O3: {consistency_score}. Content: {content}", exc_info=True)
                raise OpenAIResponseError("Invalid or malformed response from Azure OpenAI service for factuality check: Invalid score format or value.")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse O3 JSON response for factuality: {content}. Error: {e}", exc_info=True)
            raise OpenAIResponseError(f"Invalid or malformed response from Azure OpenAI service for factuality check: {e}")
        except OpenAIResponseError: # Re-raise if it's already the correct type
            raise
        except ValueError as e: # Catch validation errors raised above (should be less likely)
             logger.error(f"ValueError during factuality response processing: {content}. Error: {e}", exc_info=True)
             raise OpenAIResponseError(str(e))


    except AuthenticationError as e:
        logger.error(f"Azure OpenAI authentication failed during factuality check: {e}", exc_info=True)
        raise OpenAIAuthError("Authentication failed for factuality check. Please check Azure OpenAI credentials.")
    except APIConnectionError as e:
        logger.error(f"Could not connect to Azure OpenAI service during factuality check: {e}", exc_info=True)
        raise OpenAIServiceError("Could not connect to Azure OpenAI service for factuality check.")
    except RateLimitError as e:
        logger.error(f"Azure OpenAI rate limit exceeded during factuality check: {e}", exc_info=True)
        raise OpenAIServiceError("Rate limit exceeded for Azure OpenAI service during factuality check.")
    except APIStatusError as e:
        logger.error(f"Azure OpenAI API error during factuality check. Status: {e.status_code}, Message: {e.message}", exc_info=True)
        raise OpenAIServiceError(f"Azure OpenAI API error during factuality check: {e.status_code} {e.message}")
    except APIError as e: # Catch any other OpenAI SDK error
        logger.error(f"Azure OpenAI SDK error during factuality check: {e}", exc_info=True)
        raise OpenAIServiceError(f"Azure OpenAI SDK error during factuality check: {e}")
    except Exception as e:
        # Catch any other unexpected error not covered by OpenAI exceptions
        # or custom response errors.
        logger.error(f"Unexpected error during factuality assessment, returning neutral score: {e}", exc_info=True)
        return 3 # Return neutral score for non-OpenAI, non-response related failures

def analyze_factuality(clinical_note: str, encounter_transcript: str = "", model_precision: str = "medium") -> Dict[str, float]:
    """Analyze factual consistency between note and transcript using O3."""
    
    if not encounter_transcript.strip():
        # No transcript to check against, or transcript is only whitespace
        logger.info("No encounter transcript provided for factuality check.")
        return {
            'consistency_score': 3.0,  # Neutral score (scaled to 1-5)
            'claims_checked': 0
        }

    # Call O3 for consistency assessment
    o3_consistency_score = assess_consistency_with_o3(clinical_note, encounter_transcript, model_precision=model_precision)
    
    # The 'entailment_score' key was used previously. We'll keep a similar structure.
    # The new O3 prompt directly asks for a 'consistency_score' (1-5).
    return {
        'consistency_score': float(o3_consistency_score), # Already 1-5
        'claims_checked': 1 # Indicates one overall check was performed
    }