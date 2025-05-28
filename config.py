import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT = os.environ.get('AZ_OPENAI_ENDPOINT')
    AZURE_OPENAI_KEY = os.environ.get('AZ_OPENAI_KEY')
    AZURE_O3_DEPLOYMENT = os.environ.get('AZ_O3_DEPLOYMENT', 'gpt-o3')
    
    # Model Configuration
    TEMPERATURE = 0.0
    MAX_TOKENS = 1000
    
    # PDQI-9 Scoring Instructions
    PDQI_INSTRUCTIONS = """
You are an expert clinical documentation reviewer. Grade this clinical note using the PDQI-9 rubric on a scale of 1-5 for each dimension:

1. **up_to_date**: Current, evidence-based information (1=outdated, 5=current best practices)
2. **accurate**: Factually correct medical information (1=major errors, 5=completely accurate)
3. **thorough**: Comprehensive coverage of relevant details (1=minimal, 5=comprehensive)
4. **useful**: Practical value for clinical decision-making (1=not useful, 5=highly useful)
5. **organized**: Logical structure and flow (1=disorganized, 5=well-structured)
6. **concise**: Appropriate length without redundancy (1=verbose/sparse, 5=optimal length)
7. **consistent**: Internal consistency and coherence (1=contradictory, 5=consistent)
8. **complete**: All necessary information included (1=incomplete, 5=complete)
9. **actionable**: Clear next steps and recommendations (1=vague, 5=specific actions)

Return ONLY a JSON object with these exact keys and integer scores 1-5:
{"up_to_date": X, "accurate": X, "thorough": X, "useful": X, "organized": X, "concise": X, "consistent": X, "complete": X, "actionable": X}
"""

    # O3 Factuality Assessment Prompt
    FACTUALITY_INSTRUCTIONS = """
You are an expert clinical documentation reviewer. Assess the factual consistency between the provided Clinical Note and the Encounter Transcript.

Consider the following:
- Does the Clinical Note accurately reflect key information present in the Encounter Transcript?
- Are there any significant contradictions or discrepancies between the two texts?
- Are claims made in the Clinical Note supported by evidence in the Encounter Transcript?

Provide a single consistency score from 1 to 5, where:
1 = Very Inconsistent: Major contradictions or unsupported claims.
2 = Inconsistent: Some notable discrepancies or unsupported claims.
3 = Neutral/Unclear: Not enough information to clearly judge, or minor, negligible discrepancies.
4 = Consistent: The Clinical Note generally aligns well with the Encounter Transcript.
5 = Very Consistent: The Clinical Note strongly and accurately reflects the Encounter Transcript with no notable discrepancies.

Return ONLY a JSON object with a single key "consistency_score" and an integer score from 1 to 5.
Example: {"consistency_score": 4}
"""

    # Hybrid Scoring Weights
    PDQI_WEIGHT = 0.7
    HEURISTIC_WEIGHT = 0.2
    FACTUALITY_WEIGHT = 0.1 