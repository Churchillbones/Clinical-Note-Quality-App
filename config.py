import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT = os.environ.get('AZ_OPENAI_ENDPOINT') or os.environ.get('AZURE_ENDPOINT')
    AZURE_OPENAI_KEY = os.environ.get('AZ_OPENAI_KEY') or os.environ.get('AZURE_API_KEY')
    # GPT-4o Configuration - supports multiple environment variable names for flexibility
    MODEL_NAME = os.environ.get('MODEL_NAME', 'gpt-4o')
    GPT4O_DEPLOYMENT = os.environ.get('GPT4O_DEPLOYMENT', MODEL_NAME)
    
    # API Version - check multiple possible environment variable names
    API_VERSION = (
        os.environ.get('API_VERSION') or 
        os.environ.get('AZURE_API_VERSION') or
        '2024-02-15-preview'  # Default to working version
    )
    AZURE_GPT4O_API_VERSION = (
        os.environ.get('AZURE_GPT4O_API_VERSION') or 
        API_VERSION
    )
    # O3 config (unchanged)
    AZURE_O3_DEPLOYMENT = os.environ.get('AZ_O3_DEPLOYMENT', 'o3-mini')
    AZURE_O3_API_VERSION = os.environ.get('AZ_O3_API_VERSION', '2025-04-01-preview')
    AZURE_OPENAI_API_VERSION = os.environ.get('AZ_OPENAI_API_VERSION', AZURE_O3_API_VERSION)
    MAX_COMPLETION_TOKENS = 8000  # Increased to prevent response truncation and ensure complete factuality assessments
    # For o3-mini model, use model_low, model_medium, or model_high instead of temperature
    # Options: "low", "medium", "high"
    MODEL_PRECISION = os.environ.get('MODEL_PRECISION', 'medium')
    # Disable beta responses API (not available in Azure Government)
    DISABLE_RESPONSES_API = os.environ.get('DISABLE_RESPONSES_API', 'true').lower() in ('true', '1', 'yes')
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

For each dimension, provide detailed explanations including:
- A narrative explanation (2-3 sentences) for why this specific score was assigned
- Up to 3 brief evidence excerpts (≤30 words each) from the note that support the score
- Up to 2 specific improvement suggestions for enhancing this dimension

After scoring, provide a concise overall summary (2-4 sentences) explaining the main patterns across dimensions, highlighting both strengths and weaknesses.

Return ONLY a JSON object with these exact keys:
- the nine PDQI-9 dimension keys with integer scores 1-5,
- a string key 'summary' containing the overall narrative explanation,
- a string key 'scoring_rationale' containing your methodology and key decision factors,
- an array key 'dimension_explanations' containing objects for each dimension with keys: 'dimension', 'score', 'narrative', 'evidence_excerpts' (array), 'improvement_suggestions' (array)

Example expected JSON format:
{
  "up_to_date": 3,
  "accurate": 4,
  "thorough": 2,
  "useful": 3,
  "organized": 4,
  "concise": 3,
  "consistent": 3,
  "complete": 4,
  "actionable": 2,
  "summary": "The note demonstrates solid organization and accuracy but lacks thoroughness in key clinical areas...",
  "scoring_rationale": "Scoring prioritized evidence-based content and clinical utility. Deducted points for missing elements...",
  "dimension_explanations": [
    {
      "dimension": "up_to_date",
      "score": 3,
      "narrative": "The note includes current medications but lacks recent diagnostic updates.",
      "evidence_excerpts": ["taking Terazosin for prostate issues", "elevated prostate number"],
      "improvement_suggestions": ["Include recent lab values", "Reference current guidelines"]
    }
  ]
}

Keep narratives focused and actionable. Limit evidence excerpts to the most compelling examples. Ensure improvement suggestions are specific and implementable.
"""

    # Enhanced Factuality & Hallucination Detection Instructions
    FACTUALITY_INSTRUCTIONS = """
You are an expert clinical documentation reviewer. Perform comprehensive factual consistency analysis between the clinical note and encounter transcript, including detection of unsubstantiated claims (hallucinations).

**PRIMARY ANALYSIS:**
Evaluate factual accuracy across these key areas:
- **Demographics**: Patient age, gender, identifiers
- **Chief Complaint**: Primary reason for visit
- **History**: Medical history, symptoms, timeline
- **Medications**: Current medications, dosages, changes
- **Examination**: Physical findings, vital signs
- **Assessment**: Diagnoses, clinical impressions
- **Plan**: Treatment plans, follow-up instructions

**HALLUCINATION DETECTION:**
Identify unsubstantiated claims - statements in the note that appear factual but lack evidence in the transcript:
- **Fabricated Details**: Overly specific information not mentioned in transcript
- **Unsupported Clinical Findings**: Test results, vital signs, or examination findings without transcript support
- **Invented Context**: Background information, family history, or social history not discussed
- **False Attributions**: Statements claimed to be from patient but not in transcript
- **Speculative Statements**: Definitive claims about conditions not definitively established

Assign a 'consistency_score' from 1-5:
- **5**: Fully consistent - All major facts align, no hallucinations detected
- **4**: Mostly consistent - Minor discrepancies, minimal unsubstantiated details
- **3**: Moderately consistent - Some inconsistencies or unsubstantiated claims
- **2**: Inconsistent - Notable fabricated information or unsupported claims
- **1**: Highly inconsistent - Multiple hallucinations or major fabricated content

Return ONLY a JSON object with these keys:
- 'consistency_score' (integer 1-5)
- 'consistency_narrative' (string): 2-3 sentences explaining the overall assessment
- 'claims' (array of objects): Each claim object should have:
  - 'claim' (string): The factual claim from the note
  - 'support' (string): One of "Supported", "Not Supported", or "Unclear"
  - 'explanation' (string): Brief explanation of the assessment
- 'hallucinations' (array of objects): Unsubstantiated claims detected:
  - 'claim' (string): The unsubstantiated statement
  - 'risk_level' (string): "high", "medium", or "low"
  - 'medical_category' (string): Category like "diagnostic_findings", "medications", "test_results"
  - 'confidence' (float): Confidence level 0.0-1.0 that this is hallucinated
  - 'recommendation' (string): Suggested action for verification
- 'claims_narratives' (array of strings): Individual explanations for key claims checked (for backward compatibility)
- 'summary' (string): Brief summary of findings

Example format:
{
  "consistency_score": 4,
  "consistency_narrative": "The note demonstrates strong factual consistency with the transcript, with accurate documentation of key clinical findings. Two minor unsubstantiated claims detected requiring verification.",
  "claims": [
    {
      "claim": "Patient age documented as 45",
      "support": "Supported",
      "explanation": "Transcript confirms patient age as 45 years old"
    },
    {
      "claim": "Chief complaint of chest pain",
      "support": "Supported", 
      "explanation": "Patient clearly states chest pain as primary concern in transcript"
    },
    {
      "claim": "Prescribed 10mg atorvastatin daily",
      "support": "Not Supported",
      "explanation": "Transcript indicates 20mg atorvastatin, not 10mg as documented"
    }
  ],
  "hallucinations": [
    {
      "claim": "Patient reported chest pain radiating to left arm",
      "risk_level": "high",
      "medical_category": "diagnostic_findings",
      "confidence": 0.85,
      "recommendation": "Verify radiation pattern - transcript mentions chest pain but no radiation details"
    },
    {
      "claim": "Family history of cardiac disease",
      "risk_level": "medium",
      "medical_category": "medical_history", 
      "confidence": 0.72,
      "recommendation": "Confirm family history - not discussed in encounter transcript"
    }
  ],
  "claims_narratives": [
    "Patient age documented as 45 matches transcript",
    "Chief complaint of chest pain accurately captured",
    "Medication dosage shows discrepancy: note says 10mg, transcript says 20mg"
  ],
  "summary": "High consistency with minor medication dosage discrepancy and two unsubstantiated claims requiring verification"
}

Focus on clinical accuracy and provide actionable feedback for documentation improvement.
"""

    # Hybrid scoring weights (should sum to 1.0)
    PDQI_WEIGHT = 0.7
    HEURISTIC_WEIGHT = 0.2
    FACTUALITY_WEIGHT = 0.1

    AZURE_FACTUALITY_DEPLOYMENT = os.environ.get('AZ_FACTUALITY_DEPLOYMENT', AZURE_O3_DEPLOYMENT)

    # Feature flags
    USE_NINE_RINGS = os.environ.get('USE_NINE_RINGS', '').lower() in {'1', 'true', 'yes'}
    
    # NEW: Enable O3-based hallucination detection within factuality analysis
    # When True: O3-mini performs both factuality and hallucination detection in single call
    # When False: Uses separate embedding-based hallucination detection (legacy approach)
    USE_O3_HALLUCINATION_DETECTION = os.environ.get('USE_O3_HALLUCINATION_DETECTION', 'true').lower() in {'1', 'true', 'yes'}
    
    # Chain of Thought / Reasoning Configuration
    ENABLE_REASONING_SUMMARY = os.environ.get('ENABLE_REASONING_SUMMARY', 'true').lower() in {'1', 'true', 'yes'}
    REASONING_SUMMARY_TYPE = os.environ.get('REASONING_SUMMARY_TYPE', 'concise')  # Options: 'auto', 'concise', 'detailed'
    
    # Preview API version for responses.create() with reasoning summaries
    AZURE_OPENAI_PREVIEW_API_VERSION = os.environ.get('AZURE_OPENAI_PREVIEW_API_VERSION', '2025-04-01-preview')
    USE_RESPONSES_API_FOR_REASONING = os.environ.get('USE_RESPONSES_API_FOR_REASONING', 'true').lower() in {'1', 'true', 'yes'}