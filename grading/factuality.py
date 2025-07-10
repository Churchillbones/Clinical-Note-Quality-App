import warnings
warnings.warn(
    "'grading.factuality' is deprecated; use 'clinical_note_quality.services.factuality_service' instead.",
    DeprecationWarning,
    stacklevel=2,
)
from openai import AzureOpenAI, APIConnectionError, AuthenticationError, APIStatusError, RateLimitError, APIError
from openai.types.chat import ChatCompletionMessageParam
import json
import logging
from typing import Any, Dict, List, Optional
from config import Config
from grading.exceptions import OpenAIServiceError, OpenAIAuthError, OpenAIResponseError
import asyncio
from openai import AsyncAzureOpenAI

logger = logging.getLogger(__name__)

# --- SYNC FACTUALITY COMPONENT (O3) --- #

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
            api_version=Config.AZURE_O3_API_VERSION  # Use O3 API version
        )

        messages: List[ChatCompletionMessageParam] = [
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
        # Use a separate deployment for factuality if specified
        if hasattr(Config, 'AZURE_FACTUALITY_DEPLOYMENT') and Config.AZURE_FACTUALITY_DEPLOYMENT:
            factuality_model_name = Config.AZURE_FACTUALITY_DEPLOYMENT
        else:
            factuality_model_name = model_name
            
        kwargs = {
            "model": factuality_model_name, 
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": Config.MAX_COMPLETION_TOKENS  # Use enhanced token budget
        }
        
        # Add reasoning parameter for chain of thought summaries (O3/O4 models)
        reasoning_enabled = False
        if (hasattr(Config, 'ENABLE_REASONING_SUMMARY') and Config.ENABLE_REASONING_SUMMARY and 
            hasattr(Config, 'REASONING_SUMMARY_TYPE')):
            try:
                import openai
                client_version = getattr(openai, '__version__', '0.0.0')
                # Reasoning requires openai >= 1.52.0 and specific API versions
                if client_version >= '1.52.0':
                    # Use reasoning_effort parameter for o1/o3/o4 models (correct format)
                    reasoning_effort = "medium"  # Map from Config.REASONING_SUMMARY_TYPE
                    if hasattr(Config, 'REASONING_SUMMARY_TYPE'):
                        effort_map = {"concise": "low", "detailed": "high", "auto": "medium"}
                        reasoning_effort = effort_map.get(Config.REASONING_SUMMARY_TYPE, "medium")
                    
                    kwargs["reasoning_effort"] = reasoning_effort
                    reasoning_enabled = True
                    logger.info(f"Factuality: Enabled reasoning effort: {reasoning_effort}")
                else:
                    logger.info(f"Factuality: Reasoning not supported in OpenAI client {client_version}, requires >= 1.52.0")
            except Exception as e:
                logger.info(f"Factuality: Reasoning parameter not supported: {e}")

        # Log the request payload and model name for debugging
        logger.error(f"Factuality: Sending request with model={factuality_model_name}, messages={messages}, kwargs={kwargs}")

        try:
            response = client.chat.completions.create(**kwargs)
        except TypeError as e:
            if ("reasoning" in str(e) or "reasoning_effort" in str(e)) and reasoning_enabled:
                # Reasoning parameter not supported, retry without it
                logger.warning(f"Factuality: Reasoning parameter not supported, retrying without: {e}")
                kwargs.pop("reasoning", None)
                kwargs.pop("reasoning_effort", None)
                reasoning_enabled = False
                response = client.chat.completions.create(**kwargs)
            else:
                raise
        
        raw_content = response.choices[0].message.content
        if raw_content is None:
            logger.error("Received None content from Azure OpenAI factuality check.")
            return 3  # Neutral score
        
        content = raw_content.strip()
        logger.error(f"Raw O3 factuality response content: '{content}'")
        if not content:
            logger.warning("Empty response content from factuality check. Retrying once without response_format …")
            kwargs_no_format = {k: v for k, v in kwargs.items() if k != "response_format"}
            try:
                alt_response = client.chat.completions.create(**kwargs_no_format)
                alt_raw_content = alt_response.choices[0].message.content
                if alt_raw_content is None:
                    logger.error("Received None content from Azure OpenAI factuality check retry.")
                    return 3  # Neutral score
                content = alt_raw_content.strip()
                logger.error(f"Raw O3 alt factuality response (no response_format): '{content}'")
            except Exception as alt_e:
                logger.error(f"Alternate factuality retry failed: {alt_e}")
            if not content:
                logger.error("Still empty response from Azure OpenAI factuality check after alternate retry; returning neutral score 3.")
                return 3  # Neutral score
        try:
            score_data = json.loads(content)
            consistency_score = score_data.get('consistency_score')
            
            if isinstance(consistency_score, int) and 1 <= consistency_score <= 5:
                logger.info(f"O3 factuality scoring completed successfully. Score: {consistency_score}.")
                
                # Enhanced validation for narrative fields (backward compatible)
                consistency_narrative = score_data.get('consistency_narrative', '')
                claims_narratives = score_data.get('claims_narratives', [])
                summary = score_data.get('summary', '')
                
                # Validate narrative content without truncation
                if claims_narratives and isinstance(claims_narratives, list):
                    validated_claims = []
                    for i, narrative in enumerate(claims_narratives):
                        if isinstance(narrative, str):
                            validated_claims.append(narrative)
                        else:
                            logger.warning(f"Claims narrative {i} is not a string, skipping")
                    claims_narratives = validated_claims
                elif claims_narratives:
                    logger.warning("claims_narratives is not a list, ignoring")
                    claims_narratives = []
                    
                logger.info(f"Enhanced factuality response: narrative={bool(consistency_narrative)}, claims={len(claims_narratives)}")
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
        raise OpenAIServiceError(f"API error: {e.status_code}")
    except APIError as e: # Catch any other OpenAI SDK error
        logger.error(f"Azure OpenAI SDK error during factuality check: {e}", exc_info=True)
        raise OpenAIServiceError(f"Azure OpenAI SDK error during factuality check: {e}")
    except Exception as e:
        # If it's already an OpenAIResponseError, propagate it so callers/tests can handle.
        if isinstance(e, OpenAIResponseError):
            raise
        # Otherwise, treat as unexpected and return neutral score
        logger.error(f"Unexpected error during factuality assessment, returning neutral score: {e}", exc_info=True)
        return 3

def assess_consistency_with_o3_enhanced(clinical_note: str, encounter_transcript: str, model_precision: str = "medium") -> Dict[str, Any]:
    """Enhanced O3 factuality assessment with narrative explanations."""
    if not Config.AZURE_OPENAI_ENDPOINT or not Config.AZURE_OPENAI_KEY:
        logger.warning("Azure OpenAI credentials not configured for enhanced factuality check.")
        return {
            'consistency_score': 3.0,
            'claims_checked': 0,
            'summary': "Azure OpenAI not configured",
            'claims': [],
            'consistency_narrative': "",
            'claims_narratives': []
        }

    try:
        client = AzureOpenAI(
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
            api_key=Config.AZURE_OPENAI_KEY,
            api_version=Config.AZURE_O3_API_VERSION
        )

        messages: List[ChatCompletionMessageParam] = [
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

        # Use separate deployment for factuality if specified
        if hasattr(Config, 'AZURE_FACTUALITY_DEPLOYMENT') and Config.AZURE_FACTUALITY_DEPLOYMENT:
            factuality_model_name = Config.AZURE_FACTUALITY_DEPLOYMENT
        else:
            factuality_model_name = model_name
            
        kwargs = {
            "model": factuality_model_name, 
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": Config.MAX_COMPLETION_TOKENS
        }
        
        # Add reasoning parameter for chain of thought summaries (O3/O4 models)
        reasoning_enabled = False
        if (hasattr(Config, 'ENABLE_REASONING_SUMMARY') and Config.ENABLE_REASONING_SUMMARY and 
            hasattr(Config, 'REASONING_SUMMARY_TYPE')):
            try:
                import openai
                client_version = getattr(openai, '__version__', '0.0.0')
                # Reasoning requires openai >= 1.52.0 and specific API versions
                if client_version >= '1.52.0':
                    # Use reasoning_effort parameter for o1/o3/o4 models (correct format)
                    reasoning_effort = "medium"  # Map from Config.REASONING_SUMMARY_TYPE
                    if hasattr(Config, 'REASONING_SUMMARY_TYPE'):
                        effort_map = {"concise": "low", "detailed": "high", "auto": "medium"}
                        reasoning_effort = effort_map.get(Config.REASONING_SUMMARY_TYPE, "medium")
                    
                    kwargs["reasoning_effort"] = reasoning_effort
                    reasoning_enabled = True
                    logger.info(f"Factuality: Enabled reasoning effort: {reasoning_effort}")
                else:
                    logger.info(f"Factuality: Reasoning not supported in OpenAI client {client_version}, requires >= 1.52.0")
            except Exception as e:
                logger.info(f"Factuality: Reasoning parameter not supported: {e}")

        try:
            response = client.chat.completions.create(**kwargs)
        except TypeError as e:
            if ("reasoning" in str(e) or "reasoning_effort" in str(e)) and reasoning_enabled:
                # Reasoning parameter not supported, retry without it
                logger.warning(f"Enhanced Factuality: Reasoning parameter not supported, retrying without: {e}")
                kwargs.pop("reasoning", None)
                kwargs.pop("reasoning_effort", None)
                reasoning_enabled = False
                response = client.chat.completions.create(**kwargs)
            else:
                raise
        
        raw_content = response.choices[0].message.content
        if raw_content is None:
            logger.error("Received None content from enhanced factuality check.")
            return _fallback_factuality_response()
        
        content = raw_content.strip()
        logger.info(f"Enhanced factuality response content: {content[:200]}...")

        if not content:
            logger.error("Empty response from enhanced factuality check.")
            return _fallback_factuality_response()

        try:
            score_data = json.loads(content)
            
            # Extract and validate core fields
            consistency_score = score_data.get('consistency_score')
            if not isinstance(consistency_score, int) or not 1 <= consistency_score <= 5:
                logger.error(f"Invalid consistency score: {consistency_score}")
                return _fallback_factuality_response()

            # Extract narrative fields without truncation
            consistency_narrative = str(score_data.get('consistency_narrative', ''))
            claims_narratives = score_data.get('claims_narratives', [])
            summary = str(score_data.get('summary', ''))
            
            # Validate claims_narratives without truncation
            if isinstance(claims_narratives, list):
                validated_claims_narratives = [str(claim) for claim in claims_narratives if claim]
            else:
                validated_claims_narratives = []

            logger.info(f"Enhanced factuality completed: score={consistency_score}, narrative_len={len(consistency_narrative)}, claims_count={len(validated_claims_narratives)}")

            # Extract claims array if present, otherwise create from narratives for backward compatibility
            claims = score_data.get('claims', [])
            if not claims and validated_claims_narratives:
                # Create claims from narratives for backward compatibility
                claims = []
                for i, narrative in enumerate(validated_claims_narratives):
                    claims.append({
                        'claim': f"Clinical assertion {i+1}",
                        'support': 'Evaluated',
                        'explanation': narrative
                    })
            elif claims:
                # Validate claims structure
                validated_claims = []
                for claim in claims:
                    if isinstance(claim, dict):
                        validated_claim = {
                            'claim': str(claim.get('claim', 'Unknown claim')),
                            'support': str(claim.get('support', 'Unclear')),
                            'explanation': str(claim.get('explanation', ''))
                        }
                        validated_claims.append(validated_claim)
                claims = validated_claims

            # Extract reasoning summary if available
            reasoning_summary = ""
            if reasoning_enabled:
                # Note: With chat.completions.create() and reasoning_effort parameter,
                # the reasoning summary is not directly exposed in the response.
                # The reasoning happens internally but isn't returned as accessible text.
                logger.info("Factuality: Reasoning effort was enabled but summary not accessible via chat.completions API")
                # Document internal reasoning process for assessment documentation
                logger.info(f"Factuality: Internal reasoning processed - score: {consistency_score}, narrative length: {len(consistency_narrative)}, claims analyzed: {len(validated_claims_narratives)}")
            else:
                reasoning_summary = ""
                # Log when reasoning is not enabled for internal tracking
                logger.info(f"Factuality: Standard processing completed - score: {consistency_score}, narrative length: {len(consistency_narrative)}")

            return {
                'consistency_score': float(consistency_score),
                'claims_checked': len(claims) if claims else (len(validated_claims_narratives) if validated_claims_narratives else 1),
                'summary': summary or f"Factuality assessment completed with score {consistency_score}",
                'claims': claims,  # Elite Python: Enhanced claims structure with proper validation
                'consistency_narrative': consistency_narrative,
                'claims_narratives': validated_claims_narratives
                # reasoning_summary kept internal only per user requirements
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse enhanced factuality JSON: {content[:200]}... Error: {e}")
            return _fallback_factuality_response()

    except Exception as e:
        logger.error(f"Enhanced factuality assessment failed: {e}", exc_info=True)
        return _fallback_factuality_response()

def _fallback_factuality_response() -> Dict[str, Any]:
    """Fallback response for enhanced factuality assessment failures."""
    return {
        'consistency_score': 3.0,
        'claims_checked': 0,
        'summary': "Factuality assessment failed, neutral score assigned",
        'claims': [],  # Elite Python: Empty lists maintain consistency
        'consistency_narrative': "",
        'claims_narratives': []  # Elite Python: Empty lists maintain consistency
        # reasoning_summary kept internal only per user requirements
    }

def analyze_factuality(clinical_note: str, encounter_transcript: str = "", model_precision: str = "medium") -> Dict[str, Any]:
    """Analyze factual consistency between note and transcript using O3."""
    
    if not encounter_transcript.strip():
        # No transcript to check against, or transcript is only whitespace
        logger.info("No encounter transcript provided for factuality check.")
        return {
            'consistency_score': 3.0,  # Neutral score (scaled to 1-5)
            'claims_checked': 0,
            'summary': "No transcript provided for factuality analysis",
            'claims': [],  # Elite Python: Consistent empty structure
            'consistency_narrative': "",
            'claims_narratives': []  # Elite Python: Consistent empty structure
            # reasoning_summary kept internal only per user requirements
        }

    try:
        # Call O3 for enhanced consistency assessment with narratives
        if model_precision == "medium":
            raw_response = assess_consistency_with_o3_enhanced(clinical_note, encounter_transcript)
        else:
            raw_response = assess_consistency_with_o3_enhanced(clinical_note, encounter_transcript, model_precision=model_precision)
        
        # Return enhanced format with narrative explanations
        return raw_response
        
    except Exception as e:
        logger.error(f"Enhanced factuality analysis failed, falling back to basic score: {e}")
        # Fallback to basic O3 assessment
        if model_precision == "medium":
            o3_consistency_score = assess_consistency_with_o3(clinical_note, encounter_transcript)
        else:
            o3_consistency_score = assess_consistency_with_o3(clinical_note, encounter_transcript, model_precision=model_precision)
        
        return {
            'consistency_score': float(o3_consistency_score),
            'claims_checked': 1,
            'summary': f"Basic consistency assessment completed with score {o3_consistency_score}",
            'claims': [],  # Elite Python: Maintain data consistency
            'consistency_narrative': "",
            'claims_narratives': []  # Elite Python: Maintain data consistency
            # reasoning_summary kept internal only per user requirements
        }

# --- ASYNC FACTUALITY COMPONENT (GPT-4o) --- #

async def extract_claims_gpt4o(clinical_note: str, client: AsyncAzureOpenAI, model_name: str) -> list:
    """Extract factual claims from the clinical note using GPT-4o."""
    prompt = (
        "Extract all discrete, checkable factual claims from the following clinical note. "
        "Return a JSON array of strings, each string being a single claim.\n"
        f"Clinical Note:\n{clinical_note}"
    )
    messages: List[ChatCompletionMessageParam] = [
        {"role": "system", "content": "You are a clinical information extraction expert."},
        {"role": "user", "content": prompt}
    ]
    response = await client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_completion_tokens=Config.MAX_COMPLETION_TOKENS,  # Use enhanced token budget
        response_format={"type": "json_object"}
    )
    try:
        raw_content = response.choices[0].message.content
        if raw_content is None:
            logger.error("Received None content from claim extraction.")
            return []
        claims = json.loads(raw_content)
        if isinstance(claims, list):
            return claims
        # If the model returns a dict with a key, try to extract the list
        if isinstance(claims, dict):
            for v in claims.values():
                if isinstance(v, list):
                    return v
        raise ValueError("Could not extract claims as a list.")
    except Exception as e:
        logger.error(f"Claim extraction failed: {e}")
        return []

async def fact_check_claims_gpt4o(claims: list, transcript: str, client: AsyncAzureOpenAI, model_name: str) -> list:
    """Fact check each claim against the transcript using GPT-4o."""
    results = []
    for claim in claims:
        prompt = (
            "Given the claim and the transcript, respond with a JSON object: "
            '{"support": "Supported"|"Not Supported"|"Unclear", "explanation": "..."}'
            f"\nClaim: \"{claim}\"\nTranscript:\n{transcript}"
        )
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are a clinical fact-checking expert."},
            {"role": "user", "content": prompt}
        ]
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_completion_tokens=min(Config.MAX_COMPLETION_TOKENS // 3, 1500),  # Balanced allocation for per-claim analysis
            response_format={"type": "json_object"}
        )
        try:
            raw_content = response.choices[0].message.content
            if raw_content is None:
                logger.error(f"Received None content from fact checking claim: {claim}")
                results.append({"claim": claim, "support": "Unclear", "explanation": "No response from API"})
                continue
            result = json.loads(raw_content)
            result["claim"] = claim
            results.append(result)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse fact check response for claim '{claim}': {e}")
            results.append({"claim": claim, "support": "Unclear", "explanation": f"Parse error: {e}"})
        except Exception as e:
            logger.error(f"Error fact-checking claim '{claim}': {e}")
            results.append({"claim": claim, "support": "Unclear", "explanation": f"Error: {e}"})
    return results

async def analyze_factuality_with_agent(clinical_note: str, encounter_transcript: str, api_key: Optional[str] = None, azure_endpoint: Optional[str] = None, api_version: Optional[str] = None, model_name: Optional[str] = None) -> dict:
    """Full agent-based factuality analysis: extract claims, fact check, and score."""
    final_api_key = api_key or Config.AZURE_OPENAI_KEY
    final_azure_endpoint = azure_endpoint or Config.AZURE_OPENAI_ENDPOINT
    final_api_version = api_version or Config.AZURE_GPT4O_API_VERSION  # Use GPT-4o API version
    final_model_name = model_name or Config.GPT4O_DEPLOYMENT
    
    if not final_api_key or not final_azure_endpoint or not final_api_version or not final_model_name:
        raise ValueError("Missing required Azure OpenAI configuration parameters")
    
    client = AsyncAzureOpenAI(api_key=final_api_key, azure_endpoint=final_azure_endpoint, api_version=final_api_version)
    claims = await extract_claims_gpt4o(clinical_note, client, final_model_name)
    if not claims:
        return {"consistency_score": 3.0, "claims_checked": 0, "claims": [], "summary": "No claims extracted."}
    results = await fact_check_claims_gpt4o(claims, encounter_transcript, client, final_model_name)
    supported = sum(1 for r in results if r["support"] == "Supported")
    unclear = sum(1 for r in results if r["support"] == "Unclear")
    total = len(results)
    # Weighted score: Supported=1, Unclear=0.5, Not Supported=0
    score = ((supported + 0.5*unclear) / total) * 5 if total > 0 else 3.0
    summary = f"{supported} of {total} claims supported; {unclear} unclear."
    return {
        "consistency_score": round(score, 2),
        "claims_checked": total,
        "claims": results,
        "summary": summary
    }