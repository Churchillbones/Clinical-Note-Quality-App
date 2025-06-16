from openai import AzureOpenAI, APIConnectionError, AuthenticationError, APIStatusError, RateLimitError, APIError
import json
import logging
from typing import Dict
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
        kwargs = {"model": model_name, "messages": messages,
                  "response_format": {"type": "json_object"},
                  "max_completion_tokens": 400}

        # Use a separate deployment for factuality if specified
        if hasattr(Config, 'AZURE_FACTUALITY_DEPLOYMENT') and Config.AZURE_FACTUALITY_DEPLOYMENT:
            factuality_model_name = Config.AZURE_FACTUALITY_DEPLOYMENT
        else:
            factuality_model_name = model_name
        kwargs = {"model": factuality_model_name, "messages": messages,
                  "response_format": {"type": "json_object"},
                  "max_completion_tokens": 400}

        # Log the request payload and model name for debugging
        logger.error(f"Factuality: Sending request with model={factuality_model_name}, messages={messages}, kwargs={kwargs}")

        response = client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content.strip()
        logger.error(f"Raw O3 factuality response content: '{content}'")
        if not content:
            logger.warning("Empty response content from factuality check. Retrying once without response_format …")
            kwargs_no_format = {k: v for k, v in kwargs.items() if k != "response_format"}
            try:
                alt_response = client.chat.completions.create(**kwargs_no_format)
                content = alt_response.choices[0].message.content.strip()
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
    if model_precision == "medium":
        o3_consistency_score = assess_consistency_with_o3(clinical_note, encounter_transcript)
    else:
        o3_consistency_score = assess_consistency_with_o3(clinical_note, encounter_transcript, model_precision=model_precision)
    
    # The 'entailment_score' key was used previously. We'll keep a similar structure.
    # The new O3 prompt directly asks for a 'consistency_score' (1-5).
    return {
        'consistency_score': float(o3_consistency_score), # Already 1-5
        'claims_checked': 1 # Indicates one overall check was performed
    }

# --- ASYNC FACTUALITY COMPONENT (GPT-4o) --- #

async def extract_claims_gpt4o(clinical_note: str, client: AsyncAzureOpenAI, model_name: str) -> list:
    """Extract factual claims from the clinical note using GPT-4o."""
    prompt = (
        "Extract all discrete, checkable factual claims from the following clinical note. "
        "Return a JSON array of strings, each string being a single claim.\n"
        f"Clinical Note:\n{clinical_note}"
    )
    messages = [
        {"role": "system", "content": "You are a clinical information extraction expert."},
        {"role": "user", "content": prompt}
    ]
    response = await client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=1500,
        response_format={"type": "json_object"}
    )
    try:
        claims = json.loads(response.choices[0].message.content)
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
        messages = [
            {"role": "system", "content": "You are a clinical fact-checking expert."},
            {"role": "user", "content": prompt}
        ]
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=600,
            response_format={"type": "json_object"}
        )
        try:
            result = json.loads(response.choices[0].message.content)
            result["claim"] = claim
            results.append(result)
        except Exception as e:
            logger.error(f"Fact check failed for claim '{claim}': {e}")
            results.append({"claim": claim, "support": "Unclear", "explanation": "Model error or invalid response."})
    return results

async def analyze_factuality_with_agent(clinical_note: str, encounter_transcript: str, api_key: str = None, azure_endpoint: str = None, api_version: str = None, model_name: str = None) -> dict:
    """Full agent-based factuality analysis: extract claims, fact check, and score."""
    api_key = api_key or Config.AZURE_OPENAI_KEY
    azure_endpoint = azure_endpoint or Config.AZURE_OPENAI_ENDPOINT
    api_version = api_version or Config.AZURE_GPT4O_API_VERSION  # Use GPT-4o API version
    model_name = model_name or Config.GPT4O_DEPLOYMENT
    client = AsyncAzureOpenAI(api_key=api_key, azure_endpoint=azure_endpoint, api_version=api_version)
    claims = await extract_claims_gpt4o(clinical_note, client, model_name)
    if not claims:
        return {"consistency_score": 3.0, "claims_checked": 0, "claims": [], "summary": "No claims extracted."}
    results = await fact_check_claims_gpt4o(claims, encounter_transcript, client, model_name)
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