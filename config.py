import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT = os.environ.get('AZ_OPENAI_ENDPOINT') or os.environ.get('AZURE_ENDPOINT')
    AZURE_OPENAI_KEY = os.environ.get('AZ_OPENAI_KEY') or os.environ.get('AZURE_API_KEY')
    # Use MODEL_NAME and API_VERSION for compatibility
    MODEL_NAME = os.environ.get('MODEL_NAME', 'gpt-4o')
    API_VERSION = os.environ.get('API_VERSION', '2024-05-13-preview')
    # For backward compatibility, also set GPT4O_DEPLOYMENT and AZURE_GPT4O_API_VERSION
    GPT4O_DEPLOYMENT = MODEL_NAME
    AZURE_GPT4O_API_VERSION = API_VERSION
    # O3 config (unchanged)
    AZURE_O3_DEPLOYMENT = os.environ.get('AZ_O3_DEPLOYMENT', 'o3-mini')
    AZURE_O3_API_VERSION = os.environ.get('AZ_O3_API_VERSION', '2025-01-01-preview')
    AZURE_OPENAI_API_VERSION = os.environ.get('AZ_OPENAI_API_VERSION', AZURE_O3_API_VERSION)
    MAX_COMPLETION_TOKENS = 1000  # Changed from MAX_TOKENS for API compatibility
    # For o3-mini model, use model_low, model_medium, or model_high instead of temperature
    # Options: "low", "medium", "high"
    MODEL_PRECISION = os.environ.get('MODEL_PRECISION', 'medium')
    # Add deployment names for each precision level
    AZURE_O3_HIGH_DEPLOYMENT = os.environ.get('AZ_O3_HIGH_DEPLOYMENT', AZURE_O3_DEPLOYMENT)
    AZURE_O3_LOW_DEPLOYMENT = os.environ.get('AZ_O3_LOW_DEPLOYMENT', AZURE_O3_DEPLOYMENT)

    # PDQI-9 Scoring Instructions
    PDQI_INSTRUCTIONS = """
You are an expert clinical documentation reviewer. Critically and rigorously grade this clinical note using the PDQI-9 rubric on a scale of 1-5 for each dimension. Be strict and do not give the benefit of the doubt. Identify any weaknesses or deficiencies, even if minor. For each score, consider the lowest score that is justifiable based on the evidence in the note.

1. **up_to_date**: Current, evidence-based information (1=outdated, 5=current best practices)
2. **accurate**: Factually correct medical information (1=major errors, 5=completely accurate)
3. **thorough**: Comprehensive coverage of relevant details (1=minimal, 5=comprehensive)
4. **useful**: Practical value for clinical decision-making (1=not useful, 5=highly useful)
5. **organized**: Logical structure and flow (1=disorganized, 5=well-structured)
6. **concise**: Appropriate length without redundancy (1=verbose/sparse, 5=optimal length)
7. **consistent**: Internal consistency and coherence (1=contradictory, 5=consistent)
8. **complete**: All necessary information included (1=incomplete, 5=complete)
9. **actionable**: Clear next steps and recommendations (1=vague, 5=specific actions)

After scoring, provide a concise narrative summary (2-4 sentences) explaining the main reasons for the scores, highlighting both strengths and weaknesses. Be specific and critical in your analysis.

Return ONLY a JSON object with these exact keys:
- the nine PDQI-9 dimension keys with integer scores 1-5,
- a string key 'summary' containing the concise narrative explanation,
- and an optional string key 'rationale' containing a step-by-step chain-of-thought justification (this will only be used internally for debugging and will not be shown to end-users).

Example expected JSON format (minified):
{"up_to_date":3,"accurate":4,"thorough":2,"useful":3,"organized":4,"concise":3,"consistent":3,"complete":4,"actionable":2,"summary":"...","rationale":"..."}

The optional 'rationale' should be no more than 300 words to avoid truncation.
"""

    # Factuality Scoring Instructions
    FACTUALITY_INSTRUCTIONS = """
You are an expert clinical documentation reviewer. Assess the factual consistency between the clinical note and the encounter transcript. Assign a 'consistency_score' from 1 (major inconsistencies) to 5 (fully consistent). Return ONLY a JSON object with the key 'consistency_score' (integer 1-5).
"""

    # Hybrid scoring weights (should sum to 1.0)
    PDQI_WEIGHT = 0.7
    HEURISTIC_WEIGHT = 0.2
    FACTUALITY_WEIGHT = 0.1

    AZURE_FACTUALITY_DEPLOYMENT = os.environ.get('AZ_FACTUALITY_DEPLOYMENT', AZURE_O3_DEPLOYMENT)

    # Feature flags
    USE_NINE_RINGS = os.environ.get('USE_NINE_RINGS', '').lower() in {'1', 'true', 'yes'}