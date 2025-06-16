import warnings
warnings.warn(
    "'grading.o3_judge' is deprecated; use 'clinical_note_quality.services.pdqi_service' instead.",
    DeprecationWarning,
    stacklevel=2,
)
from openai import AzureOpenAI, APIConnectionError, AuthenticationError, APIStatusError, RateLimitError, APIError
try:
    from jsonschema import validate, ValidationError
except ModuleNotFoundError:
    validate = None
    ValidationError = Exception
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
            api_version=Config.AZURE_O3_API_VERSION  # Use O3 API version
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
            kwargs = {"model": model_name, "messages": messages,
                      "response_format": {"type": "json_object"}}
            # Add max_completion_tokens parameter only if it's defined
            if hasattr(Config, 'MAX_COMPLETION_TOKENS') and Config.MAX_COMPLETION_TOKENS:
                kwargs["max_completion_tokens"] = Config.MAX_COMPLETION_TOKENS

            # Log the request payload and model name for debugging
            logger.error(f"O3Judge: Sending PDQI-9 request with model={model_name}, messages={messages}, kwargs={kwargs}")
            retry_count = 0
            max_retries = 2
            while retry_count <= max_retries:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content.strip()
                logger.error(f"Raw O3 response content: '{content}' (retry {retry_count})")
                if content:
                    break
                retry_count += 1
                import time
                time.sleep(1)  # Wait 1 second before retry
            if not content:
                logger.warning("Empty response content after retries with response_format. Retrying once WITHOUT response_format header.")
                # Remove response_format and retry once more
                kwargs_no_format = {k: v for k, v in kwargs.items() if k != "response_format"}
                try:
                    alt_response = self.client.chat.completions.create(**kwargs_no_format)
                    content = alt_response.choices[0].message.content.strip()
                    logger.error(f"Raw O3 alt response content (no response_format): '{content}'")
                except Exception as alt_e:
                    logger.error(f"Alternate retry without response_format failed: {alt_e}")
                    pass
                if not content:
                    logger.error("Received empty response content from Azure OpenAI PDQI-9 even after alternate retry.")
                    raise OpenAIResponseError("Empty response from Azure OpenAI service for PDQI-9 check. Check your deployment name, API version, and prompt length.")

            # Try to parse JSON response, log and raise detailed error if it fails
            try:
                scores = json.loads(content)
            except json.JSONDecodeError as e:
                # Attempt to repair truncated JSON by trimming to last closing brace
                last_brace = content.rfind('}')
                if last_brace != -1:
                    repaired = content[:last_brace+1]
                    try:
                        scores = json.loads(repaired)
                        logger.warning(f"Successfully repaired truncated JSON from O3 response. Original: {content} | Repaired: {repaired}")
                    except Exception as e2:
                        logger.error(f"Failed to repair O3 JSON response: {content}. Error: {e2}", exc_info=True)
                        raise OpenAIResponseError(f"Invalid or malformed response from Azure OpenAI service: {e}\nRaw content: {content}")
                else:
                    # As a last resort, extract integer scores via regex even if summary is truncated.
                    import re
                    pattern = r'"(up_to_date|accurate|thorough|useful|organized|concise|consistent|complete|actionable)"\s*:\s*(\d)'
                    matches = re.findall(pattern, content)
                    if matches:
                        logger.warning("Parsed %d PDQI scores via regex fallback due to malformed JSON.", len(matches))
                        scores = {k: int(v) for k, v in matches}
                        # Fill any missing keys with score 3 as neutral default
                        required_keys = [
                            'up_to_date', 'accurate', 'thorough', 'useful', 
                            'organized', 'concise', 'consistent', 'complete', 'actionable'
                        ]
                        for missing in [k for k in required_keys if k not in scores]:
                            scores[missing] = 3
                        # Provide minimal summary to avoid downstream failures
                        scores.setdefault("summary", "Partial PDQI-9 scores reconstructed from truncated response.")
                    else:
                        logger.error(f"Failed to parse O3 JSON response: {content}. Error: {e}", exc_info=True)
                        raise OpenAIResponseError(f"Invalid or malformed response from Azure OpenAI service: {e}\nRaw content: {content}")

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

            if validate is not None:
                PDQI_SCHEMA = {
                    "type": "object",
                    "properties": {k: {"type": "integer", "minimum": 1, "maximum": 5} for k in required_keys},
                    "required": required_keys,
                    "additionalProperties": True
                }
                try:
                    validate(instance=scores, schema=PDQI_SCHEMA)
                except ValidationError as ve:
                    logger.warning(f"PDQI schema validation failed: {ve.message}. Attempting to coerce numeric strings.")
                    # Coerce numeric strings into ints where possible
                    coerced = {}
                    for k in required_keys:
                        v = scores.get(k)
                        if isinstance(v, str) and v.strip().replace('.', '', 1).isdigit():
                            coerced[k] = int(float(v))
                        else:
                            coerced[k] = v
                    scores.update(coerced)
                    # Re-validate; raise if still broken
                    validate(instance=scores, schema=PDQI_SCHEMA)

            logger.info("O3 PDQI-9 scoring completed successfully.")
            return scores

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
    # Preserve backward-compat: only forward model_precision when caller explicitly overrides default
    if model_precision == "medium":
        return judge.score_pdqi9(clinical_note)
    return judge.score_pdqi9(clinical_note, model_precision=model_precision)