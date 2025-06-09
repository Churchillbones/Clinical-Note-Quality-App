from openai import AzureOpenAI, APIConnectionError, AuthenticationError, APIStatusError, RateLimitError, APIError
import json
import logging
from typing import Dict, Any
from config import Config
from grading.exceptions import OpenAIServiceError, OpenAIAuthError, OpenAIResponseError

logger = logging.getLogger(__name__)

class O3Judge:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_key=Config.AZURE_OPENAI_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION
        )

    def score_pdqi9(self, clinical_note: str, model_precision: str = "medium") -> Dict[str, int]:
        """Score clinical note using O3 against PDQI-9 rubric."""
        try:
            messages = [
                {"role": "system", "content": Config.PDQI_INSTRUCTIONS},
                {"role": "user", "content": f"Clinical Note:\n\n{clinical_note}"}
            ]
            # Select deployment based on model_precision
            if model_precision == "high":
                model_name = Config.AZURE_O3_HIGH_DEPLOYMENT
            elif model_precision == "low":
                model_name = Config.AZURE_O3_LOW_DEPLOYMENT
            else:
                model_name = Config.AZURE_O3_DEPLOYMENT
            kwargs = {"model": model_name, "messages": messages}
            # Add max_completion_tokens parameter only if it's defined
            if hasattr(Config, 'MAX_COMPLETION_TOKENS') and Config.MAX_COMPLETION_TOKENS:
                kwargs["max_completion_tokens"] = Config.MAX_COMPLETION_TOKENS

            response = self.client.chat.completions.create(**kwargs)

            content = response.choices[0].message.content.strip()

            # Parse JSON response
            scores = json.loads(content)

            required_keys = [
                'up_to_date', 'accurate', 'thorough', 'useful', 
                'organized', 'concise', 'consistent', 'complete', 'actionable'
            ]

            if not all(key in scores for key in required_keys):
                logger.error(f"Missing required keys in O3 response: {content}", exc_info=True)
                raise OpenAIResponseError("Invalid or malformed response from Azure OpenAI service: Missing keys.")

            for key, value in scores.items():
                # Only check keys that are supposed to be there, ignore extra keys if any
                if key in required_keys and (not isinstance(value, int) or not 1 <= value <= 5):
                    logger.error(f"Invalid score for {key}: {value} in O3 response: {content}", exc_info=True)
                    raise OpenAIResponseError(f"Invalid or malformed response from Azure OpenAI service: Invalid score for {key}.")

            logger.info("O3 PDQI-9 scoring completed successfully.")
            return scores

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse O3 JSON response: {content}. Error: {e}", exc_info=True)
            raise OpenAIResponseError(f"Invalid or malformed response from Azure OpenAI service: {e}")
        except OpenAIResponseError: # Re-raise if it's already the correct type from checks above
            raise
        except ValueError as e: # Catch validation errors raised above (should be less likely now)
            logger.error(f"ValueError during O3 response processing: {content}. Error: {e}", exc_info=True)
            raise OpenAIResponseError(str(e))

        except AuthenticationError as e:
            logger.error(f"Azure OpenAI authentication failed: {e}", exc_info=True)
            raise OpenAIAuthError("Authentication failed. Please check your Azure OpenAI credentials.")
        except APIConnectionError as e:
            logger.error(f"Could not connect to Azure OpenAI service: {e}", exc_info=True)
            raise OpenAIServiceError("Could not connect to Azure OpenAI service.")
        except RateLimitError as e:
            logger.error(f"Azure OpenAI rate limit exceeded: {e}", exc_info=True)
            raise OpenAIServiceError("Rate limit exceeded for Azure OpenAI service.")
        except APIStatusError as e: # Catch other API errors
            logger.error(f"Azure OpenAI API error. Status: {e.status_code}, Message: {e.message}", exc_info=True)
            raise OpenAIServiceError(f"Azure OpenAI API error: {e.status_code} {e.message}")
        except APIError as e: # Catch any other OpenAI SDK error
            logger.error(f"Azure OpenAI SDK error: {e}", exc_info=True)
            raise OpenAIServiceError(f"Azure OpenAI SDK error: {e}")
        # Removed the generic except Exception that returned default scores

def score_with_o3(clinical_note: str, model_precision: str = "medium") -> Dict[str, int]:
    """Convenience function for scoring with O3."""
    judge = O3Judge()
    return judge.score_pdqi9(clinical_note, model_precision=model_precision)