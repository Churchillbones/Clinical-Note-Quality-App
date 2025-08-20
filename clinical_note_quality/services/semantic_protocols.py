"""Service protocols for semantic analysis.

Defines interfaces for semantic gap detection following Clean Architecture principles.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
from clinical_note_quality.domain.semantic_models import (
    SemanticGapResult,
    ContradictionResult,
    HallucinationResult,
    DiscrepancyAnalysisResult,
)


@runtime_checkable
class SemanticGapDetectorProtocol(Protocol):
    """Protocol for detecting semantic gaps between clinical notes and transcripts.
    
    This protocol defines the interface for services that can identify medically
    important information present in transcripts but missing from notes.
    """

    async def detect_gaps(self, note: str, transcript: str) -> SemanticGapResult:
        """Detect semantic gaps between note and transcript.
        
        Args:
            note: Clinical note text to analyze
            transcript: Encounter transcript text to compare against
            
        Returns:
            SemanticGapResult containing all gaps found and analysis metadata
        """
        ...


# Week 2: Layer 2 & 3 Protocols


@runtime_checkable
class ContradictionDetectorProtocol(Protocol):
    """Protocol for detecting contradictions between clinical notes and transcripts.
    
    This protocol defines the interface for services that can identify conflicting
    information between what's documented in the note versus what was said in the encounter.
    """

    async def detect_contradictions(
        self, 
        note: str, 
        transcript: str
    ) -> ContradictionResult:
        """Detect contradictions between note and transcript.
        
        Args:
            note: Clinical note text to analyze
            transcript: Encounter transcript text to compare against
            
        Returns:
            ContradictionResult containing all contradictions found and analysis metadata
        """
        ...


@runtime_checkable  
class HallucinationDetectorProtocol(Protocol):
    """Protocol for detecting hallucinations in clinical notes.
    
    This protocol defines the interface for services that can identify medical
    information documented in notes that lacks support in the encounter transcript.
    """

    async def detect_hallucinations(
        self,
        note: str,
        transcript: str
    ) -> HallucinationResult:
        """Detect hallucinations in the clinical note.
        
        Args:
            note: Clinical note text to analyze for unsupported claims
            transcript: Encounter transcript text for validation context
            
        Returns:
            HallucinationResult containing all hallucinations found and analysis metadata
        """
        ...


@runtime_checkable
class DiscrepancyAnalysisServiceProtocol(Protocol):
    """Protocol for comprehensive multi-layer discrepancy analysis.
    
    This protocol defines the interface for services that combine all three layers
    of discrepancy detection: gaps, contradictions, and hallucinations.
    """

    async def analyze_discrepancies(
        self,
        note: str,
        transcript: str
    ) -> DiscrepancyAnalysisResult:
        """Perform comprehensive three-layer discrepancy analysis.
        
        Orchestrates semantic gap detection, contradiction detection, and
        hallucination detection to provide unified discrepancy analysis.
        
        Args:
            note: Clinical note text to analyze
            transcript: Encounter transcript text to compare against
            
        Returns:
            DiscrepancyAnalysisResult with all layers of analysis and unified insights
        """
        ...
