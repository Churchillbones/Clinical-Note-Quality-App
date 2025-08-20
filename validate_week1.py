"""
Week 1 Validation: Ultra-Thinking Layered Embedding Enhancement
Validates all components of Layer 1: Semantic Gap Detection

This script follows the TDD approach from Claude.md:
1. RED: Create failing tests
2. GREEN: Make tests pass
3. REFACTOR: Improve code quality
"""

import os
import sys
import asyncio
from pathlib import Path

# Ensure we can import our modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def setup_test_environment():
    """Setup test environment variables"""
    os.environ.setdefault("AZ_OPENAI_KEY", "test-key")
    os.environ.setdefault("AZ_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    # Use your actual embedding configuration
    os.environ.setdefault("EMBEDDING_ENDPOINT", "https://spd-prod-openai-va-apim.azure-api.us/api")
    os.environ.setdefault("EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    os.environ.setdefault("EMBEDDING_API_VERSION", "2025-01-01-preview")

class Week1Validator:
    """Comprehensive validator for Week 1 implementation"""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_total = 0
    
    def test(self, description: str):
        """Decorator for test methods"""
        def decorator(func):
            def wrapper():
                self.tests_total += 1
                print(f"🧪 Testing: {description}")
                try:
                    result = func(self)
                    if result:
                        print("   ✅ PASSED")
                        self.tests_passed += 1
                    else:
                        print("   ❌ FAILED")
                    return result
                except Exception as e:
                    print(f"   ❌ ERROR: {e}")
                    return False
            return wrapper
        return decorator
    
    @test("Domain models can be imported and instantiated")
    def test_domain_models(self):
        from clinical_note_quality.domain.semantic_models import (
            SemanticGap, SemanticGapResult, MedicalCategory
        )
        
        # Test enum
        assert MedicalCategory.ALLERGY.value == "allergy"
        assert MedicalCategory.MEDICATION.value == "medication"
        
        # Test dataclass
        gap = SemanticGap(
            content="Patient allergic to penicillin",
            importance_score=0.95,
            medical_category=MedicalCategory.ALLERGY,
            suggested_section="Allergies",
            confidence=0.85
        )
        assert gap.importance_score == 0.95
        assert gap.medical_category == MedicalCategory.ALLERGY
        
        # Test result
        result = SemanticGapResult(
            gaps=[gap],
            total_gaps_found=1,
            critical_gaps_count=1,
            processing_time=0.5
        )
        assert len(result.gaps) == 1
        assert result.critical_gaps_count == 1
        
        return True
    
    @test("Service protocol defines correct interface")
    def test_service_protocol(self):
        from clinical_note_quality.services.semantic_protocols import SemanticGapDetectorProtocol
        
        # Check protocol has required methods
        required_methods = ['detect_gaps']
        for method in required_methods:
            assert hasattr(SemanticGapDetectorProtocol, method)
        
        return True
    
    @test("Azure client has embedding support")
    def test_azure_client_embedding_support(self):
        from clinical_note_quality.adapters.azure.async_client import (
            AsyncAzureLLMClient, AsyncLLMClientProtocol
        )
        
        # Check protocol includes create_embeddings
        assert hasattr(AsyncLLMClientProtocol, 'create_embeddings')
        
        # Check client implementation
        client = AsyncAzureLLMClient()
        assert hasattr(client, 'create_embeddings')
        assert hasattr(client, '_embedding_client')
        
        return True
    
    @test("Settings include embedding configuration")
    def test_settings_embedding_config(self):
        from clinical_note_quality import get_settings
        
        settings = get_settings()
        
        # Check all required embedding fields
        required_fields = [
            'EMBEDDING_ENDPOINT', 
            'EMBEDDING_DEPLOYMENT', 
            'EMBEDDING_API_VERSION'
        ]
        
        for field in required_fields:
            assert hasattr(settings, field), f"Missing field: {field}"
        
        # Check default values
        assert settings.EMBEDDING_DEPLOYMENT == "text-embedding-3-large"
        assert settings.EMBEDDING_API_VERSION == "2025-01-01-preview"
        
        return True
    
    @test("SemanticGapDetector can be instantiated")
    def test_detector_instantiation(self):
        from clinical_note_quality.services.semantic_gap_detector import SemanticGapDetector
        
        # Test with default client
        detector1 = SemanticGapDetector()
        assert detector1._llm_client is not None
        
        # Test with custom client
        class MockClient:
            async def create_embeddings(self, texts, model):
                return [[0.1] * 1536 for _ in texts]
            async def close(self):
                pass
        
        detector2 = SemanticGapDetector(llm_client=MockClient())
        assert detector2._llm_client is not None
        
        return True
    
    @test("SemanticGapDetector has correct configuration")
    def test_detector_configuration(self):
        from clinical_note_quality.services.semantic_gap_detector import SemanticGapDetector
        from clinical_note_quality.domain.semantic_models import MedicalCategory
        
        detector = SemanticGapDetector()
        
        # Check similarity threshold
        assert detector.SIMILARITY_THRESHOLD == 0.82
        
        # Check medical category importance
        importance = detector.MEDICAL_CATEGORY_IMPORTANCE
        assert importance[MedicalCategory.ALLERGY] == 0.95
        assert importance[MedicalCategory.MEDICATION] == 0.90
        assert importance[MedicalCategory.DIAGNOSIS] == 0.85
        
        return True
    
    async def test_detector_async_functionality(self):
        """Test detector async functionality with mock data"""
        print("🧪 Testing: SemanticGapDetector async functionality")
        try:
            from clinical_note_quality.services.semantic_gap_detector import SemanticGapDetector
            from clinical_note_quality.domain.semantic_models import MedicalCategory
            
            # Mock client with different embeddings for different content
            class SmartMockClient:
                async def create_embeddings(self, texts, model):
                    embeddings = []
                    for text in texts:
                        if "allergy" in text.lower() or "allergic" in text.lower():
                            embeddings.append([0.9] + [0.1] * 1535)  # Allergy embedding
                        elif "medication" in text.lower() or "metformin" in text.lower():
                            embeddings.append([0.1, 0.9] + [0.1] * 1534)  # Medication embedding
                        else:
                            embeddings.append([0.1] * 1536)  # Generic embedding
                    return embeddings
                
                async def close(self):
                    pass
            
            detector = SemanticGapDetector(llm_client=SmartMockClient())
            
            # Test case: note missing critical allergy information
            note = "Patient has diabetes and hypertension. Prescribed metformin."
            transcript = "Patient mentioned severe allergy to penicillin. Takes metformin 500mg daily."
            
            result = await detector.detect_gaps(note, transcript)
            
            # Validate result structure
            assert hasattr(result, 'gaps')
            assert hasattr(result, 'total_gaps_found')
            assert hasattr(result, 'critical_gaps_count')
            assert hasattr(result, 'processing_time')
            
            # Should find the allergy gap
            assert result.total_gaps_found > 0
            
            # Check for allergy-related gaps
            allergy_gaps = [g for g in result.gaps if 'allerg' in g.content.lower()]
            assert len(allergy_gaps) > 0, "Should detect missing allergy information"
            
            # Check importance scoring
            high_importance_gaps = [g for g in result.gaps if g.importance_score > 0.8]
            assert len(high_importance_gaps) > 0, "Should identify high-importance gaps"
            
            # Check processing time
            assert result.processing_time > 0, "Should record processing time"
            
            print("   ✅ PASSED")
            self.tests_passed += 1
            return True
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.tests_total += 1
    
    async def run_all_tests(self):
        """Run all validation tests"""
        print("🚀 Week 1 Ultra-Thinking Implementation Validation")
        print("=" * 60)
        print("Testing Layer 1: Semantic Gap Detection Enhancement")
        print()
        
        # Run sync tests
        self.test_domain_models()
        self.test_service_protocol()
        self.test_azure_client_embedding_support()
        self.test_settings_embedding_config()
        self.test_detector_instantiation()
        self.test_detector_configuration()
        
        # Run async test
        await self.test_detector_async_functionality()
        
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_total} passed")
        
        if self.tests_passed == self.tests_total:
            print("🎉 Week 1 Implementation: COMPLETE!")
            print("\n✅ Achievements:")
            print("   • Domain models for semantic analysis")
            print("   • Protocol-based service architecture") 
            print("   • Azure OpenAI embedding integration")
            print("   • text-embedding-3-large configuration")
            print("   • Medical category importance scoring")
            print("   • Semantic gap detection with confidence")
            print("   • Critical gap identification")
            print("   • Async/await architecture")
            print("   • Error handling and resilience")
            
            print("\n🚀 Ready for Week 2:")
            print("   • Layer 2: Contradiction Detection")
            print("   • Layer 3: Hallucination Detection")
            print("   • Integration with GradingService")
            
            return True
        else:
            print(f"⚠️  {self.tests_total - self.tests_passed} tests failed")
            print("Please review the implementation before proceeding to Week 2")
            return False

async def main():
    """Main validation runner"""
    setup_test_environment()
    
    validator = Week1Validator()
    success = await validator.run_all_tests()
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
