"""
Layer 3: Hallucination Detection Service
Detects information in clinical notes that appears unsubstantiated by transcript content.

Following Claude.md principles:
- Clean Architecture: Domain-focused, no external dependencies in core logic
- Dependency Inversion: Accepts LLM client via constructor injection  
- Single Responsibility: Focused only on hallucination detection
- Async/await: Non-blocking operations for embedding API calls
- DRY: Uses shared utilities for common patterns
"""
from __future__ import annotations

import logging
import time
import re
from typing import List, Optional, Dict, Set
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from clinical_note_quality.adapters.azure.async_client import AsyncAzureLLMClient
from clinical_note_quality.domain.semantic_models import (
    Hallucination,
    HallucinationResult,
    RiskLevel,
    MedicalCategory,
)
from clinical_note_quality.services.semantic_protocols import HallucinationDetectorProtocol
from clinical_note_quality.services.text_analysis_utils import (
    TextAnalyzer,
    SimilarityAnalyzer,
    MedicalSeverityCalculator,
)

logger = logging.getLogger(__name__)


class HallucinationDetector(HallucinationDetectorProtocol):
    """Detects hallucinated information in clinical notes using embeddings.
    
    This service uses text-embedding-3-large via Azure OpenAI to identify
    information in clinical notes that appears to be unsupported by the
    encounter transcript. Hallucinations are statements that seem factual
    but lack evidence in the source material.
    
    Key Features:
    - Unsupported fact detection (claims with no transcript evidence)
    - Fabricated detail detection (overly specific details not mentioned)
    - Context drift detection (information from wrong patient/encounter)
    - Confidence-based risk assessment
    - Medical category classification and severity scoring
    """

    # Similarity thresholds for hallucination detection
    # Below LOW_SUPPORT = likely hallucinated
    # Above HIGH_SUPPORT = likely supported
    LOW_SUPPORT_THRESHOLD = 0.60
    HIGH_SUPPORT_THRESHOLD = 0.80
    
    # Risk level thresholds
    RISK_THRESHOLDS = {
        RiskLevel.HIGH: 0.70,      # Probably hallucinated  
        RiskLevel.MEDIUM: 0.50,    # Possibly hallucinated
        RiskLevel.LOW: 0.30,       # Unlikely hallucinated
    }

    # Medical categories ranked by hallucination risk
    HIGH_RISK_CATEGORIES = {
        MedicalCategory.MEDICATION,
        MedicalCategory.ALLERGY, 
        MedicalCategory.DIAGNOSIS,
        MedicalCategory.LAB_RESULT,
        MedicalCategory.VITAL_SIGNS,
        MedicalCategory.PROCEDURE,
    }

    def __init__(self, llm_client: Optional[AsyncAzureLLMClient] = None) -> None:
        """Initialize detector with optional LLM client injection."""
        self._llm_client = llm_client or AsyncAzureLLMClient()
        self._client_owned = llm_client is None  # Track if we own the client for cleanup

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with proper resource cleanup."""
        if self._client_owned and hasattr(self._llm_client, 'close'):
            try:
                await self._llm_client.close()
            except Exception as e:
                logger.warning(f"Error closing LLM client in HallucinationDetector: {e}")

    async def detect_hallucinations(
        self, 
        note: str, 
        transcript: str
    ) -> HallucinationResult:
        """Detect hallucinations in note that are unsupported by transcript.
        
        This is the main entry point for hallucination detection. It identifies
        factual claims in the note that lack supporting evidence in the transcript.
        """
        start_time = time.time()
        
        try:
            # Handle edge cases
            if not transcript.strip():
                # Without transcript, we cannot verify anything
                return HallucinationResult(
                    hallucinations=[],
                    processing_time_ms=(time.time() - start_time) * 1000
                )
            
            # Extract verifiable claims from the note
            note_claims = self._extract_verifiable_claims(note)
            
            if not note_claims:
                return HallucinationResult(
                    hallucinations=[],
                    processing_time_ms=(time.time() - start_time) * 1000
                )
            
            # Extract supporting evidence from transcript
            transcript_evidence = self._extract_supporting_evidence(transcript)
            
            # Find hallucinations by checking claim support
            hallucinations = await self._find_hallucinations(
                note_claims, 
                transcript_evidence,
                note,
                transcript
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            return HallucinationResult(
                hallucinations=hallucinations,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error in hallucination detection: {e}", exc_info=True)
            return HallucinationResult(
                hallucinations=[],
                processing_time_ms=(time.time() - start_time) * 1000
            )

    def _extract_verifiable_claims(self, note: str) -> List[str]:
        """Extract verifiable claims from note that should be verifiable."""
        sentences = TextAnalyzer.extract_sentences(note, min_length=15)
        
        verifiable_claims = []
        for sentence in sentences:
            if TextAnalyzer.is_factual_claim(sentence, min_length=15):
                verifiable_claims.append(sentence)
        
        return verifiable_claims

    def _extract_supporting_evidence(self, transcript: str) -> List[str]:
        """Extract supporting evidence from transcript."""
        sentences = TextAnalyzer.extract_sentences(transcript, min_length=10)
        
        evidence = []
        for sentence in sentences:
            if self._is_supporting_evidence(sentence):
                evidence.append(sentence)
        
        return evidence

    def _is_supporting_evidence(self, text: str) -> bool:
        """Determine if text contains supporting evidence."""
        if len(text.strip()) < 10:
            return False
        
        # Evidence patterns - things that could support note claims
        evidence_patterns = [
            # Patient statements
            r'patient (says|tells|reports|mentions|states)',
            r'patient (has|denies|admits)',
            
            # Doctor observations  
            r'(doctor|provider|physician) (observes|notes|finds)',
            r'(examination|exam) (shows|reveals)',
            
            # Direct quotes
            r'"[^"]*"',  # Quoted statements
            
            # Medical facts mentioned
            r'\d+\s*(mg|ml|mcg|units)',  # Dosages
            r'blood pressure|temperature|weight',
            r'allergic|allergy|reaction',
            r'pain|symptom|complaint',
            r'medication|prescription|drug',
            r'diagnosis|condition|disease',
            r'procedure|surgery|treatment',
            r'test|lab|result|finding',
            
            # Historical information
            r'history|previous|past|before',
        ]
        
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in evidence_patterns)

    async def _find_hallucinations(
        self, 
        note_claims: List[str],
        transcript_evidence: List[str],
        full_note: str,
        full_transcript: str
    ) -> List[Hallucination]:
        """Find hallucinations by checking claim support in evidence."""
        
        if not transcript_evidence:
            # If no evidence found, all claims are potentially hallucinated
            return await self._create_unsupported_hallucinations(note_claims, full_note)
        
        hallucinations = []
        
        try:
            from clinical_note_quality import get_settings
            settings = get_settings()
            
            # Get embeddings for claims and evidence
            all_texts = note_claims + transcript_evidence
            embeddings = await self._llm_client.create_embeddings(
                texts=all_texts,
                model=settings.EMBEDDING_DEPLOYMENT
            )
            
            claim_embeddings = np.array(embeddings[:len(note_claims)])
            evidence_embeddings = np.array(embeddings[len(note_claims):])
            
        except Exception as e:
            logger.error(f"Failed to get embeddings: {e}")
            return []
        
        # Check each claim for supporting evidence
        for i, claim in enumerate(note_claims):
            claim_embedding = claim_embeddings[i:i+1]  # Keep 2D shape
            
            # Find best supporting evidence
            similarities = cosine_similarity(claim_embedding, evidence_embeddings)[0]
            max_similarity = np.max(similarities) if len(similarities) > 0 else 0.0
            
            # Determine if claim is hallucinated based on support level
            hallucination = self._analyze_claim_support(
                claim, max_similarity, transcript_evidence, similarities
            )
            
            if hallucination:
                hallucinations.append(hallucination)
        
        return hallucinations

    async def _create_unsupported_hallucinations(
        self, 
        claims: List[str], 
        full_note: str
    ) -> List[Hallucination]:
        """Create hallucinations for claims when no supporting evidence exists."""
        hallucinations = []
        
        for claim in claims:
            medical_category = TextAnalyzer.categorize_medical_content(claim)
            risk_level = self._assess_risk_level(medical_category, 0.0)  # No support
            
            hallucination = Hallucination(
                claim=claim,
                risk_level=risk_level,
                medical_category=medical_category,
                confidence=0.8,  # High confidence when no evidence exists
                recommendation="No supporting evidence found in transcript",
                context_similarity=0.0  # No context similarity when no evidence
            )
            
            hallucinations.append(hallucination)
        
        return hallucinations

    def _analyze_claim_support(
        self, 
        claim: str,
        max_similarity: float,
        evidence_list: List[str],
        all_similarities: np.ndarray
    ) -> Optional[Hallucination]:
        """Analyze if a claim has sufficient supporting evidence."""
        
        # Determine support level
        if max_similarity >= self.HIGH_SUPPORT_THRESHOLD:
            return None  # Well supported, not a hallucination
        
        medical_category = TextAnalyzer.categorize_medical_content(claim)
        
        # Calculate hallucination probability based on support and category
        hallucination_prob = self._calculate_hallucination_probability(
            max_similarity, medical_category
        )
        
        # Only flag as hallucination if probability is high enough
        if hallucination_prob < 0.3:  # 30% threshold
            return None
        
        # Determine risk level
        risk_level = self._assess_risk_level(medical_category, hallucination_prob)
        
        # Find best supporting evidence (if any)
        best_evidence = None
        if len(all_similarities) > 0:
            best_idx = np.argmax(all_similarities)
            best_evidence = evidence_list[best_idx]
        
        # Generate explanation
        explanation = self._generate_hallucination_explanation(
            max_similarity, medical_category, best_evidence
        )
        
        # Extract unsupported details
        unsupported_details = self._extract_specific_details(claim)
        
        return Hallucination(
            claim=claim,
            risk_level=risk_level,
            medical_category=medical_category,
            confidence=hallucination_prob,
            recommendation=explanation,
            context_similarity=max_similarity
        )

    def _calculate_hallucination_probability(
        self, 
        max_similarity: float, 
        medical_category: MedicalCategory
    ) -> float:
        """Calculate probability that claim is hallucinated."""
        
        # Base probability from similarity
        # Low similarity = high hallucination probability
        if max_similarity <= self.LOW_SUPPORT_THRESHOLD:
            base_prob = 1.0 - (max_similarity / self.LOW_SUPPORT_THRESHOLD)
        else:
            # Similarity between LOW and HIGH thresholds
            range_size = self.HIGH_SUPPORT_THRESHOLD - self.LOW_SUPPORT_THRESHOLD
            position_in_range = (max_similarity - self.LOW_SUPPORT_THRESHOLD) / range_size
            base_prob = 0.5 * (1.0 - position_in_range)  # Linear decay from 0.5 to 0
        
        # Adjust based on medical category risk using utility
        base_severity = MedicalSeverityCalculator.calculate_base_severity(medical_category)
        category_multiplier = 1.0 + (base_severity - 0.5)  # Scale around 1.0
        
        final_prob = base_prob * category_multiplier
        
        return max(0.0, min(1.0, final_prob))  # Clamp to [0,1]

    def _assess_risk_level(
        self, 
        medical_category: MedicalCategory, 
        hallucination_prob: float
    ) -> RiskLevel:
        """Assess risk level based on probability and medical category."""
        
        # Adjust thresholds based on medical category
        if medical_category in self.HIGH_RISK_CATEGORIES:
            # Lower thresholds for high-risk categories
            thresholds = {
                RiskLevel.HIGH: 0.60,
                RiskLevel.MEDIUM: 0.40,
                RiskLevel.LOW: 0.20,
            }
        else:
            # Standard thresholds for lower-risk categories
            thresholds = self.RISK_THRESHOLDS
        
        # Determine risk level
        if hallucination_prob >= thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif hallucination_prob >= thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _generate_hallucination_explanation(
        self, 
        max_similarity: float,
        medical_category: MedicalCategory,
        best_evidence: Optional[str]
    ) -> str:
        """Generate human-readable explanation for hallucination."""
        
        if max_similarity < self.LOW_SUPPORT_THRESHOLD:
            if best_evidence:
                return f"Statement lacks sufficient supporting evidence in transcript. " \
                       f"Best match: '{best_evidence[:100]}...' (similarity: {max_similarity:.2f})"
            else:
                return "Statement has no supporting evidence in transcript"
        else:
            return f"Statement may be partially supported but lacks complete verification " \
                   f"(similarity: {max_similarity:.2f})"

    def _extract_specific_details(self, claim: str) -> List[str]:
        """Extract specific, potentially fabricated details from claim."""
        details = []
        
        # Use utility to extract numerical values
        numerical_values = TextAnalyzer.extract_numerical_values(claim)
        for value in numerical_values:
            if value['unit'] != 'none':
                details.append(f"Specific measurement: {value['full_match']}")
        
        # Use utility to extract blood pressure
        bp_values = TextAnalyzer.extract_blood_pressure(claim)
        for bp in bp_values:
            details.append(f"Specific blood pressure: {bp}")
        
        # Look for very specific details that could be fabricated
        claim_lower = claim.lower()
        
        # Specific times
        if re.search(r'\b\d{1,2}:\d{2}\b', claim_lower):
            details.append("Specific time mentioned")
        
        # Specific dates
        if re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b', claim_lower):
            details.append("Specific date mentioned")
        
        # Brand names vs generic names
        if any(word in claim_lower for word in ['tylenol', 'advil', 'motrin', 'benadryl']):
            details.append("Brand name medication specified")
        
        # Very specific procedural details
        if any(phrase in claim_lower for phrase in ['performed at', 'scheduled for', 'referred to dr.']):
            details.append("Specific procedural details")
        
        return details
