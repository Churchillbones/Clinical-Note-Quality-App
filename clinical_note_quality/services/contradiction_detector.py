"""
Layer 2: Contradiction Detection Service
Detects conflicting information between clinical notes and transcripts using embeddings.

Following Claude.md principles:
- Clean Architecture: Domain-focused, no external dependencies in core logic
- Dependency Inversion: Accepts LLM client via constructor injection
- Single Responsibility: Focused only on contradiction detection
- Async/await: Non-blocking operations for embedding API calls
- DRY: Uses shared utilities for common patterns
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional, Dict, Set
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from clinical_note_quality.adapters.azure.async_client import AsyncAzureLLMClient
from clinical_note_quality.domain.semantic_models import (
    Contradiction,
    ContradictionResult,
    ContradictionType,
    MedicalCategory,
)
from clinical_note_quality.services.semantic_protocols import ContradictionDetectorProtocol
from clinical_note_quality.services.text_analysis_utils import (
    TextAnalyzer,
    SimilarityAnalyzer,
    MedicalSeverityCalculator,
)

logger = logging.getLogger(__name__)


class ContradictionDetector(ContradictionDetectorProtocol):
    """Detects contradictions between clinical notes and transcripts using embeddings.
    
    This service uses text-embedding-3-large via Azure OpenAI to identify conflicting
    information between what's documented in the clinical note versus what was
    discussed in the encounter transcript.
    
    Key Features:
    - Numerical contradiction detection (dosages, vital signs)
    - Temporal contradiction detection (timing conflicts)
    - Negation contradiction detection (presence vs absence)
    - Factual contradiction detection (different facts about same topic)
    - Medical category classification and severity scoring
    """

    # Similarity range for contradiction detection
    # Too similar = same info, too different = unrelated topics
    SIMILARITY_RANGE = (0.65, 0.85)

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
                logger.warning(f"Error closing LLM client in ContradictionDetector: {e}")

    async def detect_contradictions(
        self, 
        note: str, 
        transcript: str
    ) -> ContradictionResult:
        """Detect contradictions between note and transcript.
        
        This is the main entry point for contradiction detection. It identifies
        semantically related but factually different information.
        """
        start_time = time.time()
        
        try:
            # Handle edge cases
            if not transcript.strip():
                return ContradictionResult(
                    contradictions=[],
                    processing_time_ms=(time.time() - start_time) * 1000
                )
            
            # Extract factual statements from both documents
            note_statements = self._extract_factual_statements(note)
            transcript_statements = self._extract_factual_statements(transcript)
            
            if not note_statements or not transcript_statements:
                return ContradictionResult(
                    contradictions=[],
                    processing_time_ms=(time.time() - start_time) * 1000
                )
            
            # Find contradictions using semantic analysis
            contradictions = await self._find_contradictions(
                note_statements, 
                transcript_statements
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            return ContradictionResult(
                contradictions=contradictions,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error in contradiction detection: {e}", exc_info=True)
            # Return empty result on error
            return ContradictionResult(
                contradictions=[],
                processing_time_ms=(time.time() - start_time) * 1000
            )

    def _extract_factual_statements(self, text: str) -> List[str]:
        """Extract factual statements that could contain contradictions."""
        sentences = TextAnalyzer.extract_sentences(text, min_length=10)
        
        factual_statements = []
        for sentence in sentences:
            if TextAnalyzer.is_factual_claim(sentence):
                factual_statements.append(sentence)
        
        return factual_statements

    async def _find_contradictions(
        self, 
        note_statements: List[str], 
        transcript_statements: List[str]
    ) -> List[Contradiction]:
        """Find contradictions between note and transcript statements."""
        contradictions = []
        
        # Get embeddings for all statements
        all_statements = note_statements + transcript_statements
        
        try:
            from clinical_note_quality import get_settings
            settings = get_settings()
            
            embeddings = await self._llm_client.create_embeddings(
                texts=all_statements,
                model=settings.EMBEDDING_DEPLOYMENT
            )
            
            note_embeddings = np.array(embeddings[:len(note_statements)])
            transcript_embeddings = np.array(embeddings[len(note_statements):])
            
        except Exception as e:
            logger.error(f"Failed to get embeddings: {e}")
            return []
        
        # Compare each note statement with transcript statements
        for i, note_stmt in enumerate(note_statements):
            note_embedding = note_embeddings[i:i+1]  # Keep 2D shape
            
            # Find transcript statements in the "contradiction zone"
            similarities = cosine_similarity(note_embedding, transcript_embeddings)[0]
            
            for j, similarity in enumerate(similarities):
                # Check if similarity is in contradiction range
                if SimilarityAnalyzer.is_in_similarity_range(similarity, self.SIMILARITY_RANGE):
                    transcript_stmt = transcript_statements[j]
                    
                    # Check if these statements are actually contradictory
                    contradiction = self._analyze_potential_contradiction(
                        note_stmt, transcript_stmt, similarity
                    )
                    
                    if contradiction:
                        contradictions.append(contradiction)
        
        return contradictions

    def _analyze_potential_contradiction(
        self, 
        note_stmt: str, 
        transcript_stmt: str, 
        similarity: float
    ) -> Optional[Contradiction]:
        """Analyze if two similar statements are actually contradictory."""
        
        # Check for numerical contradictions
        numerical_contradiction = self._check_numerical_contradiction(note_stmt, transcript_stmt)
        if numerical_contradiction:
            return self._create_contradiction(
                note_stmt, transcript_stmt, ContradictionType.NUMERICAL,
                numerical_contradiction, similarity
            )
        
        # Check for negation contradictions
        if self._has_negation_contradiction(note_stmt, transcript_stmt):
            return self._create_contradiction(
                note_stmt, transcript_stmt, ContradictionType.NEGATION,
                "Conflicting presence/absence of condition", similarity
            )
        
        # Check for temporal contradictions
        if self._has_temporal_contradiction(note_stmt, transcript_stmt):
            return self._create_contradiction(
                note_stmt, transcript_stmt, ContradictionType.TEMPORAL,
                "Conflicting timing information", similarity
            )
        
        # Check for other factual contradictions
        if self._has_factual_contradiction(note_stmt, transcript_stmt):
            return self._create_contradiction(
                note_stmt, transcript_stmt, ContradictionType.FACTUAL,
                "Conflicting factual information", similarity
            )
        
        return None

    def _check_numerical_contradiction(self, stmt1: str, stmt2: str) -> Optional[str]:
        """Check for conflicting numerical values."""
        values1 = TextAnalyzer.extract_numerical_values(stmt1)
        values2 = TextAnalyzer.extract_numerical_values(stmt2)
        
        if values1 and values2:
            # Compare values with same units
            for val1 in values1:
                for val2 in values2:
                    # Same unit, different number
                    if (val1['unit'] == val2['unit'] and 
                        val1['unit'] != 'none' and 
                        val1['number'] != val2['number']):
                        return f"Different {val1['unit']}: {val1['full_match']} vs {val2['full_match']}"
        
        # Special case for blood pressure
        bp1 = TextAnalyzer.extract_blood_pressure(stmt1)
        bp2 = TextAnalyzer.extract_blood_pressure(stmt2)
        if bp1 and bp2 and bp1[0] != bp2[0]:
            return f"Different blood pressure: {bp1[0]} vs {bp2[0]}"
        
        return None

    def _has_negation_contradiction(self, stmt1: str, stmt2: str) -> bool:
        """Check for negation contradictions using utility functions."""
        stmt1_negative = TextAnalyzer.has_negation(stmt1)
        stmt2_negative = TextAnalyzer.has_negation(stmt2)
        
        stmt1_positive = TextAnalyzer.has_affirmation(stmt1)
        stmt2_positive = TextAnalyzer.has_affirmation(stmt2)
        
        # Contradiction if one is clearly negative and other is clearly positive
        return (stmt1_negative and stmt2_positive) or (stmt1_positive and stmt2_negative)

    def _has_temporal_contradiction(self, stmt1: str, stmt2: str) -> bool:
        """Check for temporal contradictions using utility functions."""
        temporal1 = TextAnalyzer.extract_temporal_indicators(stmt1)
        temporal2 = TextAnalyzer.extract_temporal_indicators(stmt2)
        
        return SimilarityAnalyzer.has_temporal_conflict(temporal1, temporal2)

    def _has_factual_contradiction(self, stmt1: str, stmt2: str) -> bool:
        """Check for other factual contradictions."""
        # Extract key medical terms
        terms1 = TextAnalyzer.extract_medical_terms(stmt1)
        terms2 = TextAnalyzer.extract_medical_terms(stmt2)
        
        # If they share some terms but have different specific terms, 
        # might be contradictory
        shared_terms = terms1.intersection(terms2)
        different_terms = terms1.symmetric_difference(terms2)
        
        # Heuristic: if they share context but have different specific terms
        return len(shared_terms) > 0 and len(different_terms) > 2

    def _create_contradiction(
        self, 
        note_stmt: str, 
        transcript_stmt: str,
        contradiction_type: ContradictionType,
        explanation: str,
        similarity: float
    ) -> Contradiction:
        """Create a Contradiction object with appropriate metadata."""
        
        # Categorize the medical category
        medical_category = TextAnalyzer.categorize_medical_content(note_stmt)
        
        # Calculate severity using utility
        base_severity = MedicalSeverityCalculator.calculate_base_severity(medical_category)
        severity = MedicalSeverityCalculator.adjust_severity_for_detection_type(
            base_severity, contradiction_type.value
        )
        
        # Confidence from similarity using utility
        confidence = SimilarityAnalyzer.calculate_confidence_from_similarity(similarity)
        
        return Contradiction(
            note_statement=note_stmt,
            transcript_statement=transcript_stmt,
            contradiction_type=contradiction_type,
            severity=severity,
            medical_category=medical_category,
            explanation=explanation,
            confidence=confidence
        )
