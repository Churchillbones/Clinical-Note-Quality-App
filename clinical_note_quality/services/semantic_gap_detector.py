"""Semantic gap detection service implementation.

Identifies medically important information present in transcripts but missing from notes
using embedding-based semantic similarity analysis.
"""
from __future__ import annotations

import asyncio
import logging
import time
import re
from typing import List, Optional, Set

import nltk
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from clinical_note_quality.adapters.azure.async_client import AsyncAzureLLMClient
from clinical_note_quality.domain.semantic_models import (
    SemanticGap,
    SemanticGapResult,
    MedicalCategory,
)
from clinical_note_quality.services.semantic_protocols import SemanticGapDetectorProtocol

logger = logging.getLogger(__name__)

# Download NLTK data if not already present
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")


class SemanticGapDetector(SemanticGapDetectorProtocol):
    """Detects semantic gaps between clinical notes and transcripts using embeddings.
    
    This service uses text-embedding-3-large via Azure OpenAI to identify medically
    important information that appears in the encounter transcript but is missing
    from the clinical note. It focuses on critical medical categories like medications,
    allergies, diagnoses, and procedures.
    """

    # Similarity threshold for determining if content is semantically similar
    SIMILARITY_THRESHOLD = 0.82
    
    # Importance scores for different medical categories
    MEDICAL_CATEGORY_IMPORTANCE = {
        MedicalCategory.ALLERGY: 0.95,
        MedicalCategory.MEDICATION: 0.90,
        MedicalCategory.DIAGNOSIS: 0.85,
        MedicalCategory.PROCEDURE: 0.80,
        MedicalCategory.VITAL_SIGNS: 0.75,
        MedicalCategory.LAB_RESULT: 0.70,
        MedicalCategory.SYMPTOM: 0.65,
        MedicalCategory.FOLLOW_UP: 0.60,
        MedicalCategory.SOCIAL_HISTORY: 0.50,
        MedicalCategory.FAMILY_HISTORY: 0.45,
    }

    def __init__(self, llm_client: Optional[AsyncAzureLLMClient] = None) -> None:
        """Initialize detector with optional LLM client injection."""
        self._llm_client = llm_client or AsyncAzureLLMClient()

    async def detect_gaps(self, note: str, transcript: str) -> SemanticGapResult:
        """Detect semantic gaps between note and transcript.
        
        This is the main entry point for gap detection. It performs semantic
        analysis to identify information present in the transcript but missing
        from the note.
        """
        start_time = time.time()
        
        try:
            # Handle edge cases
            if not transcript.strip():
                return SemanticGapResult(
                    gaps=[],
                    total_gaps_found=0,
                    critical_gaps_count=0,
                    semantic_coverage=1.0,  # Perfect coverage - nothing to compare
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )

            if not note.strip():
                # Note is empty but transcript has content - everything is missing
                transcript_chunks = self._extract_medical_chunks(transcript)
                gaps = []
                for chunk in transcript_chunks[:5]:  # Limit to prevent overwhelming results
                    if self._is_medically_significant(chunk):
                        gap = SemanticGap(
                            transcript_content=chunk,
                            importance_score=self._calculate_importance(chunk),
                            medical_category=self._categorize_content(chunk),
                            suggested_section=self._suggest_section(chunk),
                            confidence=0.95,  # High confidence - note is completely empty
                        )
                        gaps.append(gap)
                
                critical_count = len([g for g in gaps if g.is_critical])
                return SemanticGapResult(
                    gaps=gaps,
                    total_gaps_found=len(gaps),
                    critical_gaps_count=critical_count,
                    semantic_coverage=0.0,  # No coverage - note is empty
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )

            # Main gap detection logic
            gaps = await self._perform_gap_analysis(note, transcript)
            
            critical_count = len([g for g in gaps if g.is_critical])
            semantic_coverage = self._calculate_semantic_coverage(note, transcript, gaps)
            
            return SemanticGapResult(
                gaps=gaps,
                total_gaps_found=len(gaps),
                critical_gaps_count=critical_count,
                semantic_coverage=semantic_coverage,
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        except Exception as e:
            logger.error(f"Error in semantic gap detection: {e}", exc_info=True)
            # Return safe fallback result on error
            return SemanticGapResult(
                gaps=[],
                total_gaps_found=0,
                critical_gaps_count=0,
                semantic_coverage=0.5,  # Neutral coverage on error
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

    async def _perform_gap_analysis(self, note: str, transcript: str) -> List[SemanticGap]:
        """Perform the core gap analysis using embeddings."""
        # Extract meaningful chunks from both documents
        note_chunks = self._extract_medical_chunks(note)
        transcript_chunks = self._extract_medical_chunks(transcript)

        if not transcript_chunks:
            return []

        # Get embeddings for all chunks
        all_chunks = note_chunks + transcript_chunks
        
        try:
            from clinical_note_quality import get_settings
            settings = get_settings()
            
            embeddings = await self._llm_client.create_embeddings(
                texts=all_chunks,
                model=settings.EMBEDDING_DEPLOYMENT
            )
        except Exception as e:
            logger.error(f"Failed to get embeddings: {e}")
            return []  # Return empty on embedding failure

        # Split embeddings back into note and transcript
        note_embeddings = np.array(embeddings[:len(note_chunks)])
        transcript_embeddings = np.array(embeddings[len(note_chunks):])

        # Find gaps: transcript chunks with no similar note chunks
        gaps = []
        for i, t_chunk in enumerate(transcript_chunks):
            if not self._is_medically_significant(t_chunk):
                continue

            t_embedding = transcript_embeddings[i:i+1]  # Keep 2D shape
            
            # Calculate similarities with all note chunks
            if len(note_embeddings) > 0:
                similarities = cosine_similarity(t_embedding, note_embeddings)[0]
                max_similarity = np.max(similarities)
            else:
                max_similarity = 0.0

            # If no similar chunk found in note, it's a gap
            if max_similarity < self.SIMILARITY_THRESHOLD:
                gap = SemanticGap(
                    transcript_content=t_chunk,
                    importance_score=self._calculate_importance(t_chunk),
                    medical_category=self._categorize_content(t_chunk),
                    suggested_section=self._suggest_section(t_chunk),
                    confidence=1.0 - max_similarity,
                )
                gaps.append(gap)

        # Sort by importance (most critical first)
        gaps.sort(key=lambda g: g.importance_score, reverse=True)
        
        # Return top 10 gaps to avoid overwhelming the user
        return gaps[:10]

    def _extract_medical_chunks(self, text: str) -> List[str]:
        """Extract medically meaningful chunks from text.
        
        Groups related sentences together and filters for medical significance.
        """
        sentences = nltk.sent_tokenize(text)
        chunks = []
        
        current_chunk = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Group related medical information together
            if self._should_group_sentences(current_chunk, sentence):
                current_chunk += f" {sentence}"
            else:
                if current_chunk and self._is_medically_significant(current_chunk):
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        # Add the last chunk
        if current_chunk and self._is_medically_significant(current_chunk):
            chunks.append(current_chunk.strip())
        
        return chunks

    def _should_group_sentences(self, chunk: str, sentence: str) -> bool:
        """Determine if a sentence should be grouped with the current chunk."""
        if not chunk:
            return False
        
        # Group if they share medical keywords
        chunk_keywords = self._extract_medical_keywords(chunk)
        sentence_keywords = self._extract_medical_keywords(sentence)
        
        return len(chunk_keywords.intersection(sentence_keywords)) > 0

    def _extract_medical_keywords(self, text: str) -> Set[str]:
        """Extract medical keywords from text."""
        text_lower = text.lower()
        keywords = set()
        
        # Common medical terms
        medical_terms = [
            'medication', 'medicine', 'drug', 'prescription', 'dose', 'mg', 'ml',
            'allergy', 'allergic', 'reaction',
            'diagnosis', 'condition', 'disease',
            'symptom', 'pain', 'ache', 'feels', 'reports',
            'blood pressure', 'heart rate', 'temperature', 'weight',
            'lab', 'test', 'result', 'level',
            'procedure', 'surgery', 'operation',
            'follow', 'appointment', 'return', 'visit',
        ]
        
        for term in medical_terms:
            if term in text_lower:
                keywords.add(term)
        
        return keywords

    def _is_medically_significant(self, text: str) -> bool:
        """Determine if text contains medically significant information."""
        text_lower = text.lower()
        
        # Medical significance indicators
        significant_patterns = [
            r'\b\d+\s*mg\b', r'\b\d+\s*ml\b', r'\b\d+\s*mcg\b',  # Dosages
            r'\ballerg\w*\b', r'\bmedication\b', r'\bdrug\b',
            r'\bdiagnos\w*\b', r'\bprescri\w*\b',
            r'\bblood pressure\b', r'\bheart rate\b', r'\btemperature\b',
            r'\bpain\b', r'\bsymptom\b', r'\baches?\b',
            r'\blab\w*\b', r'\btest\w*\b', r'\bresult\w*\b',
            r'\bfollow.up\b', r'\breturn\b', r'\bvisit\b',
        ]
        
        return any(re.search(pattern, text_lower) for pattern in significant_patterns)

    def _calculate_importance(self, text: str) -> float:
        """Calculate medical importance score (0-1) for text content."""
        text_lower = text.lower()
        
        # Base importance
        importance = 0.3
        
        # Category-based importance
        category = self._categorize_content(text)
        base_importance = self.MEDICAL_CATEGORY_IMPORTANCE.get(category, 0.3)
        importance = max(importance, base_importance)
        
        # Specific high-importance indicators
        if any(term in text_lower for term in ['allergic', 'allergy']):
            importance = max(importance, 0.95)
        if any(term in text_lower for term in ['mg', 'ml', 'mcg', 'units', 'dose']):
            importance = max(importance, 0.85)
        if any(term in text_lower for term in ['prescription', 'prescribed', 'medication']):
            importance = max(importance, 0.80)
        
        return min(1.0, importance)

    def _categorize_content(self, text: str) -> MedicalCategory:
        """Categorize medical content into appropriate category."""
        text_lower = text.lower()
        
        # Pattern matching for categories
        if any(term in text_lower for term in ['allergic', 'allergy', 'reaction to']):
            return MedicalCategory.ALLERGY
        
        if any(term in text_lower for term in ['mg', 'ml', 'prescription', 'medication', 'drug', 'takes', 'prescribed']):
            return MedicalCategory.MEDICATION
        
        if any(term in text_lower for term in ['diagnosed', 'diagnosis', 'condition', 'has been']):
            return MedicalCategory.DIAGNOSIS
        
        if any(term in text_lower for term in ['procedure', 'surgery', 'operation', 'performed']):
            return MedicalCategory.PROCEDURE
        
        if any(term in text_lower for term in ['blood pressure', 'heart rate', 'temperature', 'vital']):
            return MedicalCategory.VITAL_SIGNS
        
        if any(term in text_lower for term in ['pain', 'ache', 'symptom', 'feels', 'reports', 'complaint']):
            return MedicalCategory.SYMPTOM
        
        if any(term in text_lower for term in ['lab', 'test', 'result', 'level', 'value']):
            return MedicalCategory.LAB_RESULT
        
        if any(term in text_lower for term in ['follow', 'return', 'appointment', 'visit', 'see']):
            return MedicalCategory.FOLLOW_UP
        
        if any(term in text_lower for term in ['smoke', 'drink', 'alcohol', 'social', 'work', 'family']):
            return MedicalCategory.SOCIAL_HISTORY
        
        return MedicalCategory.SYMPTOM  # Default category

    def _suggest_section(self, text: str) -> str:
        """Suggest appropriate note section for the content."""
        category = self._categorize_content(text)
        
        section_mapping = {
            MedicalCategory.MEDICATION: "Current Medications",
            MedicalCategory.ALLERGY: "Allergies",
            MedicalCategory.DIAGNOSIS: "Assessment/Diagnosis",
            MedicalCategory.PROCEDURE: "Procedures/Plan",
            MedicalCategory.VITAL_SIGNS: "Vital Signs",
            MedicalCategory.SYMPTOM: "Chief Complaint",
            MedicalCategory.LAB_RESULT: "Laboratory Results",
            MedicalCategory.FOLLOW_UP: "Plan/Follow-up",
            MedicalCategory.SOCIAL_HISTORY: "Social History",
            MedicalCategory.FAMILY_HISTORY: "Family History",
        }
        
        return section_mapping.get(category, "Clinical Notes")

    def _calculate_semantic_coverage(self, note: str, transcript: str, gaps: List[SemanticGap]) -> float:
        """Calculate what percentage of transcript content is covered by the note."""
        transcript_chunks = self._extract_medical_chunks(transcript)
        
        if not transcript_chunks:
            return 1.0  # Perfect coverage if no medical content in transcript
        
        # Coverage = (transcript chunks - gap chunks) / total transcript chunks
        gap_contents = {gap.transcript_content for gap in gaps}
        covered_chunks = len([chunk for chunk in transcript_chunks if chunk not in gap_contents])
        
        coverage = covered_chunks / len(transcript_chunks)
        return max(0.0, min(1.0, coverage))  # Clamp to [0, 1]
