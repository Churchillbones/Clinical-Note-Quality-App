"""
Diagnostic script for the Clinical Note Quality App
This script tests each component of the grading system independently
to identify where issues might be occurring.
"""
import logging
import sys
import json
from config import Config
from grading.o3_judge import O3Judge, score_with_o3
from grading.heuristics import analyze_heuristics, get_heuristic_composite
from grading.factuality import analyze_factuality
from grading.hybrid import grade_note_hybrid
from grading.exceptions import OpenAIServiceError, OpenAIAuthError, OpenAIResponseError

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                     format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('diagnostics')

def check_environment_vars():
    """Check if all required environment variables are set"""
    logger.info("Checking environment variables...")
    
    missing = []
    if not Config.AZURE_OPENAI_ENDPOINT:
        missing.append("AZ_OPENAI_ENDPOINT")
    if not Config.AZURE_OPENAI_KEY:
        missing.append("AZ_OPENAI_KEY")
        
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        return False
    
    logger.info("All critical environment variables are set.")
    endpoint_preview = Config.AZURE_OPENAI_ENDPOINT[:10] + "..." if Config.AZURE_OPENAI_ENDPOINT else "None"
    logger.info(f"AZURE_OPENAI_ENDPOINT: {endpoint_preview}")
    logger.info(f"AZURE_OPENAI_API_VERSION: {Config.AZURE_OPENAI_API_VERSION}")
    logger.info(f"AZURE_O3_DEPLOYMENT: {Config.AZURE_O3_DEPLOYMENT}")
    return True

def test_openai_connection(model_precision="medium"):
    """Test connection to OpenAI API"""
    logger.info("Testing OpenAI connection...")
    
    try:
        judge = O3Judge()
        # Select deployment based on model_precision
        if model_precision == "high":
            model_name = Config.AZURE_O3_HIGH_DEPLOYMENT
        elif model_precision == "low":
            model_name = Config.AZURE_O3_LOW_DEPLOYMENT
        else:
            model_name = Config.AZURE_O3_DEPLOYMENT
        from openai.types.chat import ChatCompletionMessageParam
        from typing import List
        
        messages: List[ChatCompletionMessageParam] = [{"role": "user", "content": "Hello, this is a test."}]
        response = judge.client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_completion_tokens=10
        )
        logger.info("Connection to OpenAI API successful!")
        return True
    except Exception as e:
        logger.error(f"Error connecting to OpenAI API: {str(e)}")
        return False

def test_pdqi_scoring(model_precision="medium"):
    """Test PDQI-9 scoring with a simple clinical note"""
    logger.info("Testing PDQI-9 scoring...")
    
    sample_note = """
    Patient: John Doe
    DOB: 01/01/1980
    
    CHIEF COMPLAINT: Chest pain
    
    HISTORY: Patient presents with chest pain that started yesterday. 
    Pain is described as sharp and radiating to the left arm. 
    No prior history of heart disease. No shortness of breath.
    
    ASSESSMENT: Likely musculoskeletal pain, but cannot rule out cardiac origin.
    
    PLAN: 
    1. ECG to rule out cardiac etiology
    2. Chest X-ray
    3. Follow up in 2 days
    """
    
    try:
        scores = score_with_o3(sample_note, model_precision=model_precision)
        logger.info(f"PDQI-9 scoring successful: {scores}")
        return True
    except Exception as e:
        logger.error(f"Error in PDQI-9 scoring: {str(e)}")
        return False

def test_heuristics():
    """Test heuristic analysis with a simple clinical note"""
    logger.info("Testing heuristic analysis...")
    
    sample_note = """
    Patient: John Doe
    DOB: 01/01/1980
    
    CHIEF COMPLAINT: Chest pain
    
    HISTORY: Patient presents with chest pain that started yesterday. 
    Pain is described as sharp and radiating to the left arm. 
    No prior history of heart disease. No shortness of breath.
    
    ASSESSMENT: Likely musculoskeletal pain, but cannot rule out cardiac origin.
    
    PLAN: 
    1. ECG to rule out cardiac etiology
    2. Chest X-ray
    3. Follow up in 2 days
    """
    
    try:
        heuristic_results = analyze_heuristics(sample_note)
        composite_score = get_heuristic_composite(heuristic_results)
        logger.info(f"Heuristic analysis successful: {heuristic_results}")
        logger.info(f"Composite heuristic score: {composite_score}")
        return True
    except Exception as e:
        logger.error(f"Error in heuristic analysis: {str(e)}")
        return False

def test_factuality(model_precision="medium"):
    """Test factuality analysis with a simple clinical note and transcript"""
    logger.info("Testing factuality analysis...")
    
    sample_note = """
    Patient: John Doe
    DOB: 01/01/1980
    
    CHIEF COMPLAINT: Chest pain
    
    HISTORY: Patient presents with chest pain that started yesterday. 
    Pain is described as sharp and radiating to the left arm. 
    No prior history of heart disease. No shortness of breath.
    
    ASSESSMENT: Likely musculoskeletal pain, but cannot rule out cardiac origin.
    
    PLAN: 
    1. ECG to rule out cardiac etiology
    2. Chest X-ray
    3. Follow up in 2 days
    """
    
    sample_transcript = """
    Doctor: Hello, Mr. Doe. What brings you in today?
    Patient: I've been having this chest pain since yesterday.
    Doctor: Can you describe the pain?
    Patient: It's sharp and sometimes goes to my left arm.
    Doctor: Have you ever had heart problems before?
    Patient: No, never.
    Doctor: Any trouble breathing?
    Patient: No, my breathing is fine.
    Doctor: I think this might be muscular, but we should check your heart too.
    Patient: Okay.
    Doctor: I'll order an ECG and chest X-ray. Come back in 2 days.
    """
    
    try:
        factuality_result = analyze_factuality(sample_note, sample_transcript, model_precision=model_precision)
        logger.info(f"Factuality analysis successful: {factuality_result}")
        return True
    except Exception as e:
        logger.error(f"Error in factuality analysis: {str(e)}")
        return False

def test_hybrid_grading(model_precision="medium"):
    """Test the complete hybrid grading pipeline"""
    logger.info("Testing hybrid grading pipeline...")
    
    sample_note = """
    Patient: John Doe
    DOB: 01/01/1980
    
    CHIEF COMPLAINT: Chest pain
    
    HISTORY: Patient presents with chest pain that started yesterday. 
    Pain is described as sharp and radiating to the left arm. 
    No prior history of heart disease. No shortness of breath.
    
    ASSESSMENT: Likely musculoskeletal pain, but cannot rule out cardiac origin.
    
    PLAN: 
    1. ECG to rule out cardiac etiology
    2. Chest X-ray
    3. Follow up in 2 days
    """
    
    sample_transcript = """
    Doctor: Hello, Mr. Doe. What brings you in today?
    Patient: I've been having this chest pain since yesterday.
    Doctor: Can you describe the pain?
    Patient: It's sharp and sometimes goes to my left arm.
    Doctor: Have you ever had heart problems before?
    Patient: No, never.
    Doctor: Any trouble breathing?
    Patient: No, my breathing is fine.
    Doctor: I think this might be muscular, but we should check your heart too.
    Patient: Okay.
    Doctor: I'll order an ECG and chest X-ray. Come back in 2 days.
    """
    
    try:
        result = grade_note_hybrid(clinical_note=sample_note, encounter_transcript=sample_transcript, model_precision=model_precision)
        logger.info(f"Hybrid grading successful: {result}")
        return True
    except Exception as e:
        logger.error(f"Error in hybrid grading pipeline: {str(e)}", exc_info=True)
        return False

def run_all_tests():
    """Run all diagnostic tests"""
    logger.info("Starting diagnostics for Clinical Note Quality App")
    
    env_check = check_environment_vars()
    if not env_check:
        logger.error("Environment variable check failed. Fix these issues before continuing.")
        return
    
    model_precision = "medium"  # Default for diagnostics
    connection_check = test_openai_connection(model_precision=model_precision)
    if not connection_check:
        logger.error("OpenAI API connection test failed. Fix connection issues before continuing.")
        return
    
    pdqi_check = test_pdqi_scoring(model_precision=model_precision)
    heuristics_check = test_heuristics()
    factuality_check = test_factuality(model_precision=model_precision)
    hybrid_check = test_hybrid_grading(model_precision=model_precision)
    
    # Summary
    logger.info("\n--- DIAGNOSTIC SUMMARY ---")
    logger.info(f"Environment Variables: {'✅ PASS' if env_check else '❌ FAIL'}")
    logger.info(f"OpenAI Connection: {'✅ PASS' if connection_check else '❌ FAIL'}")
    logger.info(f"PDQI-9 Scoring: {'✅ PASS' if pdqi_check else '❌ FAIL'}")
    logger.info(f"Heuristic Analysis: {'✅ PASS' if heuristics_check else '❌ FAIL'}")
    logger.info(f"Factuality Analysis: {'✅ PASS' if factuality_check else '❌ FAIL'}")
    logger.info(f"Hybrid Grading Pipeline: {'✅ PASS' if hybrid_check else '❌ FAIL'}")

if __name__ == "__main__":
    run_all_tests()
