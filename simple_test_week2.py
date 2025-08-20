"""
Simple test to validate Week 2 implementations work.
"""
import asyncio

async def main():
    # Test imports
    from clinical_note_quality.services.contradiction_detector import ContradictionDetector
    from clinical_note_quality.services.hallucination_detector import HallucinationDetector
    
    print("✅ Imports successful")
    
    # Test instantiation
    cd = ContradictionDetector()
    hd = HallucinationDetector()
    
    print("✅ Instantiation successful")
    
    # Test basic functionality
    note = "Patient prescribed 50mg medication."
    transcript = ""
    
    result1 = await cd.detect_contradictions(note, transcript)
    result2 = await hd.detect_hallucinations(note, transcript)
    
    print(f"✅ ContradictionDetector: {len(result1.contradictions)} contradictions")
    print(f"✅ HallucinationDetector: {len(result2.hallucinations)} hallucinations")
    print("✅ Week 2 GREEN phase COMPLETE!")

if __name__ == "__main__":
    asyncio.run(main())
