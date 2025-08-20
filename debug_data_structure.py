#!/usr/bin/env python3
"""
Debug script to understand the data structure issue.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clinical_note_quality.domain.models import PDQIScore, PDQIDimension, HybridResult
from clinical_note_quality.services.grading_service import GradingService


def debug_data_structure():
    """Debug the data structure being passed to templates."""
    print("="*60)
    print("DEBUG: DATA STRUCTURE ANALYSIS")
    print("="*60)
    
    # Create test PDQIScore
    scores = {}
    for i, dim in enumerate(PDQIDimension):
        scores[dim.value] = float(4 + (i % 2))  # Alternate between 4 and 5
    
    pdqi = PDQIScore(scores=scores, summary="Test", rationale="Test rationale")
    print(f"1. PDQIScore.total: {pdqi.total}")
    print(f"2. PDQIScore.to_dict() keys: {list(pdqi.to_dict().keys())}")
    
    pdqi_dict = pdqi.to_dict()
    if "scores" in pdqi_dict:
        print(f"3. PDQIScore.to_dict()['scores']: {pdqi_dict['scores']}")
    
    # Test what HybridResult.as_dict() would produce
    print(f"\n4. Testing HybridResult.as_dict() structure:")
    
    # Simulate a minimal HybridResult (we can't create a real one easily without all dependencies)
    test_result = {
        "pdqi_scores": pdqi_dict,
        "pdqi_total": round(pdqi.total, 2),  # This is what should be in as_dict()
        "hybrid_score": 4.2,
        "overall_grade": "B"
    }
    
    print(f"   Result keys: {list(test_result.keys())}")
    print(f"   pdqi_total present: {'pdqi_total' in test_result}")
    print(f"   pdqi_total value: {test_result.get('pdqi_total', 'MISSING!')}")
    
    # Test the template access pattern
    print(f"\n5. Template access simulation:")
    try:
        template_value = test_result["pdqi_total"]
        print(f"   ✅ result['pdqi_total'] = {template_value}")
    except KeyError as e:
        print(f"   ❌ result['pdqi_total'] failed: {e}")
    
    # Test the route fallback logic
    print(f"\n6. Route fallback logic test:")
    if "pdqi_total" not in test_result:
        print("   pdqi_total missing, would calculate fallback")
        pdqi_scores = test_result.get("pdqi_scores", {})
        if isinstance(pdqi_scores, dict) and "scores" in pdqi_scores:
            scores_dict = pdqi_scores["scores"]
            numeric_scores = [float(v) for k, v in scores_dict.items() 
                            if k not in ["summary", "rationale", "model_provenance"] 
                            and isinstance(v, (int, float))]
            calculated_total = sum(numeric_scores) if numeric_scores else 0.0
            print(f"   Would calculate: {calculated_total}")
        else:
            print("   Would use flat structure fallback")
    else:
        print(f"   ✅ pdqi_total already present: {test_result['pdqi_total']}")
    
    return test_result


if __name__ == "__main__":
    try:
        result = debug_data_structure()
        print(f"\n{'='*60}")
        print("✅ DATA STRUCTURE DEBUG COMPLETE")
        print(f"{'='*60}")
    except Exception as e:
        print(f"\n❌ DEBUG FAILED: {e}")
        import traceback
        traceback.print_exc()
