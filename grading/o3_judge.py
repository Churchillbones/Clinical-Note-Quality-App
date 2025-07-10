import warnings
warnings.warn(
    "'grading.o3_judge' is deprecated; use 'clinical_note_quality.services.pdqi_service' instead.",
    DeprecationWarning,
    stacklevel=2,
)
from openai import AzureOpenAI, APIConnectionError, AuthenticationError, APIStatusError, RateLimitError, APIError
from openai.types.chat import ChatCompletionMessageParam
from openai.types import Reasoning
from openai.types.responses import Response, ResponseReasoningItem, ResponseOutputRefusal
try:
    from jsonschema import validate, ValidationError
except ModuleNotFoundError:
    validate = None
    ValidationError = Exception
import json
import logging
from typing import Dict, Any, List, Tuple
from config import Config
from grading.exceptions import OpenAIServiceError, OpenAIAuthError, OpenAIResponseError

logger = logging.getLogger(__name__)

class O3Judge:
    def __init__(self):
        if not Config.AZURE_OPENAI_ENDPOINT or not Config.AZURE_OPENAI_KEY:
            raise ValueError("Azure OpenAI credentials not configured")
        self.client = AzureOpenAI(
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_key=Config.AZURE_OPENAI_KEY,
            api_version=Config.AZURE_O3_API_VERSION  # Use O3 API version
        )

    def _try_enable_reasoning(self, kwargs: Dict[str, Any]) -> bool:
        """Try to enable reasoning parameter if supported by the model."""
        # Don't add reasoning parameter as it's not supported in current API
        logger.info("Skipping reasoning parameter - not supported in current API")
        return False

    def _extract_reasoning_summary(self, response, reasoning_enabled: bool) -> str:
        """Extract reasoning summary from response if available."""
        reasoning_summary = ""
        
        if reasoning_enabled and response:
            try:
                # Try to access reasoning content from various possible locations
                if hasattr(response, 'reasoning'):
                    reasoning_summary = str(getattr(response, 'reasoning', ''))
                    logger.info(f"Extracted reasoning summary: {len(reasoning_summary)} characters")
                elif hasattr(response, 'choices') and response.choices:
                    choice = response.choices[0]
                    if hasattr(choice, 'reasoning'):
                        reasoning_summary = str(getattr(choice, 'reasoning', ''))
                        logger.info(f"Extracted choice reasoning: {len(reasoning_summary)} characters")
            except Exception as e:
                logger.warning(f"Could not extract reasoning: {e}")
        
        return reasoning_summary

    def _make_pdqi_request(self, kwargs: dict, reasoning_enabled: bool) -> Tuple[str, str]:
        """Make PDQI request with retry logic and reasoning extraction."""
        content = ""
        reasoning_summary = ""
        
        # Remove reasoning parameter if it exists to avoid errors
        kwargs_safe = kwargs.copy()
        kwargs_safe.pop('reasoning', None)
        
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(**kwargs_safe)
                
                # Extract reasoning summary if enabled
                reasoning_summary = self._extract_reasoning_summary(response, reasoning_enabled)
                
                # Extract main content
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content or ""
                    if content:
                        logger.info(f"Successfully got PDQI response on attempt {attempt + 1}")
                        break
                else:
                    logger.warning(f"Empty response on attempt {attempt + 1}")
                    
            except Exception as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt == 2:  # Last attempt
                    raise
        
        return content, reasoning_summary

    def score_pdqi9(self, clinical_note: str, model_precision: str = "medium") -> Dict[str, Any]:
        """Score clinical note using PDQI-9 dimensions with O3 model."""
        try:
            # Try responses API first (newer, more advanced)
            return self._score_with_responses_api(clinical_note, model_precision)
        except Exception as e:
            logger.warning(f"Responses API failed: {e}, falling back to chat.completions")
            return self._score_with_chat_completions(clinical_note, model_precision)

    def _score_with_responses_api(self, clinical_note: str, model_precision: str = "medium") -> Dict[str, Any]:
        """Try scoring with the newer responses API (beta)."""
        try:
            # Import responses API
            from openai import AzureOpenAI
            
            # Select deployment based on model_precision
            if model_precision == "high":
                model_name = Config.AZURE_O3_HIGH_DEPLOYMENT
            elif model_precision == "low":
                model_name = Config.AZURE_O3_LOW_DEPLOYMENT
            else:
                model_name = Config.AZURE_O3_DEPLOYMENT
            
            # Prepare messages
            messages = [
                {"role": "system", "content": Config.PDQI_INSTRUCTIONS},
                {"role": "user", "content": f"Clinical Note:\n\n{clinical_note}"}
            ]
            
            # Create response with reasoning enabled - cast client to Any for beta API access
            client_any: Any = self.client
            response = client_any.beta.chat.completions.create(
                model=model_name,
                messages=messages,
                max_completion_tokens=getattr(Config, 'MAX_COMPLETION_TOKENS', 4000),
                response_format={"type": "json_object"}
            )
            
            # Extract content and reasoning from response
            response_content = ""
            reasoning_content = ""
            
            # Handle response structure safely using getattr
            if hasattr(response, 'output') and response.output:
                for output_item in response.output:
                    # Cast to Any to avoid type checker issues
                    item: Any = output_item
                    
                    # Check if this is reasoning content
                    if getattr(item, 'type', None) == "reasoning":
                        # Safe access to reasoning content - try multiple possible attributes
                        content_attr = getattr(item, 'content', None)
                        text_attr = getattr(item, 'text', None)
                        
                        if content_attr is not None:
                            reasoning_content = str(content_attr)
                            logger.info(f"Responses API: Extracted reasoning content ({len(reasoning_content)} chars)")
                        elif text_attr is not None:
                            reasoning_content = str(text_attr)
                            logger.info(f"Responses API: Extracted reasoning content ({len(reasoning_content)} chars)")
                    
                    # Check if this is the main response content
                    elif getattr(item, 'type', None) == "message":
                        # Safe access to message content - handle various response structures
                        content_attr = getattr(item, 'content', None)
                        text_attr = getattr(item, 'text', None)
                        
                        if content_attr is not None:
                            # Could be string or object with text attribute
                            if isinstance(content_attr, str):
                                response_content = str(content_attr)
                            elif hasattr(content_attr, 'text'):
                                response_content = str(getattr(content_attr, 'text', ''))
                            elif isinstance(content_attr, list) and len(content_attr) > 0:
                                # Handle list of content items
                                first_item = content_attr[0]
                                if hasattr(first_item, 'text'):
                                    response_content = str(getattr(first_item, 'text', ''))
                                elif isinstance(first_item, str):
                                    response_content = str(first_item)
                        elif text_attr is not None:
                            response_content = str(text_attr)
                        
                        if response_content:
                            logger.info(f"Responses API: Extracted response content ({len(response_content)} chars)")
            
            # Validate we got content
            if not response_content:
                logger.warning("Responses API: No response content found, checking alternative structure")
                # Fallback: try to access response differently using proper attributes
                response_any: Any = response
                if hasattr(response_any, 'output_text'):
                    response_content = str(getattr(response_any, 'output_text', ''))
                elif hasattr(response_any, 'text'):
                    response_content = str(getattr(response_any, 'text', ''))
            
            if response_content:
                # Parse JSON from response content
                import re
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    json_content = json_match.group(0)
                    scores = json.loads(json_content)
                    
                    # Add reasoning summary to scores if available
                    if reasoning_content:
                        scores["reasoning_summary"] = reasoning_content
                        logger.info(f"Responses API: Successfully extracted reasoning summary ({len(reasoning_content)} characters)")
                    
                    logger.info("Responses API: Successfully parsed PDQI scores with reasoning")
                    return scores
                else:
                    logger.warning("Responses API: Could not extract JSON from response content")
            
            # If we get here, responses API didn't work as expected
            logger.warning("Responses API: Didn't return expected format, falling back to chat.completions")
            return self._score_with_chat_completions(clinical_note, model_precision)
            
        except Exception as e:
            logger.warning(f"Responses API failed: {e}, falling back to chat.completions")
            return self._score_with_chat_completions(clinical_note, model_precision)

    def _score_with_chat_completions(self, clinical_note: str, model_precision: str = "medium") -> Dict[str, Any]:
        """Original chat.completions.create() implementation."""
        try:
            from openai import AuthenticationError, APIConnectionError, RateLimitError, APIStatusError, APIError
            from jsonschema import ValidationError, validate
            
            messages: List[ChatCompletionMessageParam] = [
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
            
            # Try to enable reasoning parameter for chain of thought summaries
            reasoning_enabled = self._try_enable_reasoning(kwargs)
            
            # Make request with retry logic
            content, reasoning_summary = self._make_pdqi_request(kwargs, reasoning_enabled)
            
            # Defensive programming: Ensure content is not None or empty
            if not content:
                logger.error("Empty response content after retries")
                raise OpenAIResponseError("Empty response from Azure OpenAI service for PDQI-9 check")

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
                    pattern = r'"(up_to_date|accurate|thorough|useful|organized|concise|consistent|complete|actionable)"\s*:\s*([1-5])'
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
                    else:
                        logger.error(f"Failed to parse O3 JSON response: {content}. Error: {e}", exc_info=True)
                        raise OpenAIResponseError(f"Invalid or malformed response from Azure OpenAI service: {e}\nRaw content: {content}")

            # Defensive programming: Ensure scores is not None
            if scores is None:
                logger.error("Parsed scores is None, creating fallback scores")
                scores = {
                    'up_to_date': 3, 'accurate': 3, 'thorough': 3, 'useful': 3,
                    'organized': 3, 'concise': 3, 'consistent': 3, 'complete': 3, 'actionable': 3,
                    'summary': 'Fallback scores due to parsing error'
                }

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

            # Validate enhanced dimension explanations if present
            if 'dimension_explanations' in scores:
                dimension_explanations = scores['dimension_explanations']
                if isinstance(dimension_explanations, list):
                    for i, explanation in enumerate(dimension_explanations):
                        if not isinstance(explanation, dict):
                            logger.warning(f"Dimension explanation {i} is not a dict, skipping validation")
                            continue
                        
                        # Validate required fields in each explanation
                        required_explanation_keys = ['dimension', 'score', 'narrative']
                        missing_keys = [k for k in required_explanation_keys if k not in explanation]
                        if missing_keys:
                            logger.warning(f"Dimension explanation {i} missing keys: {missing_keys}")
                        
                        # Validate dimension name is valid
                        if 'dimension' in explanation and explanation['dimension'] not in required_keys:
                            logger.warning(f"Invalid dimension name in explanation {i}: {explanation['dimension']}")
                        
                        # Validate score consistency
                        if ('dimension' in explanation and 'score' in explanation and 
                            explanation['dimension'] in scores and 
                            scores[explanation['dimension']] != explanation['score']):
                            logger.warning(f"Score mismatch for {explanation['dimension']}: main={scores[explanation['dimension']]}, explanation={explanation['score']}")
                    
                    logger.info(f"Validated {len(dimension_explanations)} dimension explanations")
                else:
                    logger.warning("dimension_explanations is not a list, ignoring enhanced validation")

            # Schema validation if available
            try:
                from jsonschema import validate, ValidationError
                # Enhanced schema for full narrative response format
                dimension_explanation_schema = {
                    "type": "object",
                    "properties": {
                        "dimension": {"type": "string", "enum": required_keys},
                        "score": {"type": "integer", "minimum": 1, "maximum": 5},
                        "narrative": {"type": "string", "minLength": 1},
                        "evidence_excerpts": {"type": "array", "items": {"type": "string"}},
                        "improvement_suggestions": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["dimension", "score", "narrative"],
                    "additionalProperties": False
                }
                
                PDQI_SCHEMA = {
                    "type": "object",
                    "properties": {
                        **{k: {"type": "integer", "minimum": 1, "maximum": 5} for k in required_keys},
                        "summary": {"type": "string", "minLength": 1},
                        "scoring_rationale": {"type": "string"},
                        "reasoning_summary": {"type": "string"},  # Allow reasoning summary
                        "dimension_explanations": {
                            "type": "array",
                            "items": dimension_explanation_schema,
                            "minItems": 0,
                            "maxItems": 9
                        },
                        # Backward compatibility
                        "rationale": {"type": "string"}
                    },
                    "required": required_keys,
                    "additionalProperties": True  # Allow additional properties
                }
                
                try:
                    validate(instance=scores, schema=PDQI_SCHEMA)
                except ValidationError as ve:
                    # Fix: ValidationError doesn't have .message attribute in newer versions
                    error_message = str(ve)
                    logger.warning(f"PDQI schema validation failed: {error_message}. Attempting to coerce numeric strings.")
                    
                    # Create a new dictionary with proper typing for coerced values
                    coerced_scores: Dict[str, int] = {}
                    for k in required_keys:
                        v = scores.get(k)
                        if isinstance(v, str) and v.strip().replace('.', '', 1).isdigit():
                            # Convert numeric strings to integers
                            coerced_scores[k] = int(float(v))
                        elif isinstance(v, float):
                            # Convert floats to integers
                            coerced_scores[k] = int(v)
                        elif isinstance(v, int):
                            # Keep integers as-is
                            coerced_scores[k] = v
                        else:
                            # For any other type, set a default value of 3 for required keys
                            logger.warning(f"Unexpected type for required key {k}: {type(v)}, using default value 3")
                            coerced_scores[k] = 3
                    
                    # Update only the required keys with coerced values (all values are guaranteed to be int)
                    for k, v in coerced_scores.items():
                        # Explicit cast to ensure type checker knows this is an int
                        scores[k] = int(v)  # type: ignore[assignment]
                    
                    # Re-validate; raise if still broken
                    validate(instance=scores, schema=PDQI_SCHEMA)
                    
            except ImportError:
                logger.info("jsonschema not available, skipping schema validation")

            logger.info("O3 PDQI-9 scoring completed successfully.")
            
            # Add reasoning summary to response if available
            if reasoning_summary:
                scores["reasoning_summary"] = reasoning_summary
                logger.info(f"Added reasoning summary to PDQI response: {len(reasoning_summary)} characters")
            
            return scores

        except OpenAIResponseError:
            # Re-raise if it's already the correct type from checks above
            raise
        except ValueError as e:
            # Catch validation errors raised above (should be less likely now)
            logger.error(f"ValueError during O3 response processing. Error: {e}", exc_info=True)
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
        except APIStatusError as e:
            logger.error(f"Azure OpenAI API error. Status: {e.status_code}, Message: {e.message}", exc_info=True)
            raise OpenAIServiceError(f"Azure OpenAI API error: {e.status_code} {e.message}")
        except APIError as e:
            logger.error(f"Azure OpenAI SDK error: {e}", exc_info=True)
            raise OpenAIServiceError(f"Azure OpenAI SDK error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in PDQI scoring: {e}", exc_info=True)
            raise OpenAIServiceError(f"Unexpected error in PDQI scoring: {e}")

def score_with_o3(clinical_note: str, model_precision: str = "medium") -> Dict[str, Any]:
    """Convenience function for scoring with O3."""
    judge = O3Judge()
    # Preserve backward-compat: only forward model_precision when caller explicitly overrides default
    if model_precision == "medium":
        return judge.score_pdqi9(clinical_note)
    return judge.score_pdqi9(clinical_note, model_precision=model_precision)