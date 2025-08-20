"""Domain models for semantic gap detection.

These models represent information gaps found between clinical notes and transcripts.
Following Clean Architecture principles - no external dependencies beyond standard library.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any


class MedicalCategory(str, Enum):
    """Enumeration of medical information categories for gap classification."""

    MEDICATION = "medication"
    ALLERGY = "allergy"
    DIAGNOSIS = "diagnosis"
    PROCEDURE = "procedure"
    VITAL_SIGNS = "vital_signs"
    SYMPTOM = "symptom"
    LAB_RESULT = "lab_result"
    FOLLOW_UP = "follow_up"
    SOCIAL_HISTORY = "social_history"
    FAMILY_HISTORY = "family_history"


@dataclass(frozen=True)
class SemanticGap:
    """Represents medically important information present in transcript but missing from note.
    
    This is a pure domain value object with validation and serialization capabilities.
    Immutable by design to ensure data integrity throughout the application.
    """

    transcript_content: str
    importance_score: float  # 0-1, higher = more critical to document
    medical_category: MedicalCategory
    suggested_section: str  # Where this should appear in the note
    confidence: float  # 0-1, how confident we are this is truly missing

    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate SemanticGap invariants on construction."""
        if not self.transcript_content or not self.transcript_content.strip():
            raise ValueError("Transcript content cannot be empty")
        
        if not 0 <= self.importance_score <= 1:
            raise ValueError("Importance score must be between 0 and 1")
        
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        
        if not self.suggested_section or not self.suggested_section.strip():
            raise ValueError("Suggested section cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON responses."""
        return {
            "transcript_content": self.transcript_content,
            "importance_score": self.importance_score,
            "medical_category": self.medical_category.value,
            "suggested_section": self.suggested_section,
            "confidence": self.confidence,
        }

    @property
    def is_critical(self) -> bool:
        """Determine if this gap represents critical missing information."""
        return self.importance_score >= 0.8


@dataclass(frozen=True)
class SemanticGapResult:
    """Aggregate result from semantic gap detection analysis.
    
    Contains all gaps found, metadata about the analysis, and convenience methods
    for accessing different categories of gaps.
    """

    gaps: List[SemanticGap]
    total_gaps_found: int
    critical_gaps_count: int
    semantic_coverage: float  # 0-1, what percentage of transcript is covered by note
    processing_time_ms: int

    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate SemanticGapResult invariants."""
        if not 0 <= self.semantic_coverage <= 1:
            raise ValueError("Semantic coverage must be between 0 and 1")
        
        if self.critical_gaps_count > self.total_gaps_found:
            raise ValueError("Critical gaps count cannot exceed total gaps")
        
        if self.total_gaps_found < 0:
            raise ValueError("Total gaps found cannot be negative")
        
        if self.processing_time_ms < 0:
            raise ValueError("Processing time cannot be negative")

    @property
    def critical_gaps(self) -> List[SemanticGap]:
        """Get only the critical gaps (high importance)."""
        return [gap for gap in self.gaps if gap.is_critical]

    @property
    def gaps_by_category(self) -> Dict[MedicalCategory, List[SemanticGap]]:
        """Group gaps by medical category for easier analysis."""
        result: Dict[MedicalCategory, List[SemanticGap]] = {}
        for gap in self.gaps:
            if gap.medical_category not in result:
                result[gap.medical_category] = []
            result[gap.medical_category].append(gap)
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Serialize complete result to dictionary."""
        return {
            "gaps": [gap.to_dict() for gap in self.gaps],
            "total_gaps_found": self.total_gaps_found,
            "critical_gaps_count": self.critical_gaps_count,
            "semantic_coverage": self.semantic_coverage,
            "processing_time_ms": self.processing_time_ms,
            "critical_gaps": [gap.to_dict() for gap in self.critical_gaps],
            "gaps_by_category": {
                category.value: [gap.to_dict() for gap in gaps]
                for category, gaps in self.gaps_by_category.items()
            },
        }


# Week 2: Layer 2 & 3 Domain Models


class ContradictionType(str, Enum):
    """Types of contradictions that can be detected between note and transcript."""
    
    NUMERICAL = "numerical"          # Different numbers (dosages, vitals)
    TEMPORAL = "temporal"           # Time-related conflicts  
    NEGATION = "negation"          # Presence vs absence of condition
    FACTUAL = "factual"            # Different facts about same topic


class RiskLevel(str, Enum):
    """Risk levels for hallucinations and contradictions."""
    
    HIGH = "high"       # Critical medical safety risk
    MEDIUM = "medium"   # Moderate clinical importance
    LOW = "low"         # Minor documentation issue


@dataclass(frozen=True)
class Contradiction:
    """Represents conflicting information between note and transcript.
    
    A contradiction occurs when the note and transcript contain semantically
    related but factually different information about the same medical concept.
    """
    
    note_statement: str
    transcript_statement: str
    contradiction_type: ContradictionType
    severity: float  # 0.0 to 1.0, higher = more serious
    medical_category: MedicalCategory
    explanation: str
    confidence: float  # 0.0 to 1.0, how confident we are this is a contradiction
    
    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate Contradiction invariants."""
        if not self.note_statement or not self.note_statement.strip():
            raise ValueError("Note statement cannot be empty")
            
        if not self.transcript_statement or not self.transcript_statement.strip():
            raise ValueError("Transcript statement cannot be empty")
            
        if not 0 <= self.severity <= 1:
            raise ValueError("Severity must be between 0 and 1")
            
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")
    
    @property
    def is_high_severity(self) -> bool:
        """True if this contradiction has high clinical severity."""
        return self.severity > 0.8
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "note_statement": self.note_statement,
            "transcript_statement": self.transcript_statement,
            "contradiction_type": self.contradiction_type.value,
            "severity": self.severity,
            "medical_category": self.medical_category.value,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "is_high_severity": self.is_high_severity,
        }


@dataclass(frozen=True)
class Hallucination:
    """Represents unsupported claims in the clinical note.
    
    A hallucination is medical information documented in the note that has
    no corresponding support in the encounter transcript or available data.
    """
    
    claim: str
    risk_level: RiskLevel
    medical_category: MedicalCategory
    confidence: float  # 0.0 to 1.0, how confident we are this is hallucinated
    recommendation: str  # What to do about it
    context_similarity: float  # 0.0 to 1.0, similarity to transcript content
    
    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate Hallucination invariants."""
        if not self.claim or not self.claim.strip():
            raise ValueError("Claim cannot be empty")
            
        if not self.recommendation or not self.recommendation.strip():
            raise ValueError("Recommendation cannot be empty")
            
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")
            
        if not 0 <= self.context_similarity <= 1:
            raise ValueError("Context similarity must be between 0 and 1")
    
    @property
    def is_high_risk(self) -> bool:
        """True if this hallucination poses high clinical risk."""
        return self.risk_level == RiskLevel.HIGH
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "claim": self.claim,
            "risk_level": self.risk_level.value,
            "medical_category": self.medical_category.value,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
            "context_similarity": self.context_similarity,
            "is_high_risk": self.is_high_risk,
        }


@dataclass(frozen=True)
class ContradictionResult:
    """Complete result of contradiction analysis.
    
    Aggregates all contradictions found with summary statistics
    and performance metrics.
    """
    
    contradictions: List[Contradiction]
    processing_time_ms: float
    
    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate ContradictionResult invariants."""
        if self.processing_time_ms < 0:
            raise ValueError("Processing time cannot be negative")
    
    @property
    def total_contradictions_found(self) -> int:
        """Total number of contradictions detected."""
        return len(self.contradictions)
    
    @property
    def high_severity_count(self) -> int:
        """Number of contradictions with high severity (>0.8)."""
        return sum(1 for c in self.contradictions if c.is_high_severity)
    
    @property
    def contradictions_by_type(self) -> Dict[ContradictionType, List[Contradiction]]:
        """Group contradictions by type."""
        result: Dict[ContradictionType, List[Contradiction]] = {}
        for contradiction in self.contradictions:
            if contradiction.contradiction_type not in result:
                result[contradiction.contradiction_type] = []
            result[contradiction.contradiction_type].append(contradiction)
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_contradictions_found": self.total_contradictions_found,
            "high_severity_count": self.high_severity_count,
            "processing_time_ms": self.processing_time_ms,
            "contradictions": [c.to_dict() for c in self.contradictions],
            "contradictions_by_type": {
                ctype.value: [c.to_dict() for c in contradictions]
                for ctype, contradictions in self.contradictions_by_type.items()
            },
        }


@dataclass(frozen=True)
class HallucinationResult:
    """Complete result of hallucination analysis.
    
    Aggregates all hallucinations found with summary statistics
    and performance metrics.
    """
    
    hallucinations: List[Hallucination]
    processing_time_ms: float
    
    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate HallucinationResult invariants."""
        if self.processing_time_ms < 0:
            raise ValueError("Processing time cannot be negative")
    
    @property
    def total_hallucinations_found(self) -> int:
        """Total number of hallucinations detected."""
        return len(self.hallucinations)
    
    @property
    def high_risk_count(self) -> int:
        """Number of high-risk hallucinations."""
        return sum(1 for h in self.hallucinations if h.is_high_risk)
    
    @property
    def hallucinations_by_risk(self) -> Dict[RiskLevel, List[Hallucination]]:
        """Group hallucinations by risk level."""
        result: Dict[RiskLevel, List[Hallucination]] = {}
        for hallucination in self.hallucinations:
            if hallucination.risk_level not in result:
                result[hallucination.risk_level] = []
            result[hallucination.risk_level].append(hallucination)
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_hallucinations_found": self.total_hallucinations_found,
            "high_risk_count": self.high_risk_count,
            "processing_time_ms": self.processing_time_ms,
            "hallucinations": [h.to_dict() for h in self.hallucinations],
            "hallucinations_by_risk": {
                risk.value: [h.to_dict() for h in hallucinations]
                for risk, hallucinations in self.hallucinations_by_risk.items()
            },
        }


@dataclass(frozen=True)
class DiscrepancyAnalysisResult:
    """Comprehensive discrepancy analysis combining all three layers.
    
    This is the complete output of the Ultra-Thinking Layered Embedding Enhancement,
    providing semantic gaps, contradictions, and hallucinations in a unified result.
    """
    
    gap_result: SemanticGapResult
    contradiction_result: ContradictionResult
    hallucination_result: HallucinationResult
    overall_consistency_score: float  # 0.0 to 1.0
    critical_issues: List[str]  # Top critical issues requiring attention
    recommendations: List[str]  # Actionable recommendations
    
    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate DiscrepancyAnalysisResult invariants."""
        if not 0 <= self.overall_consistency_score <= 1:
            raise ValueError("Overall consistency score must be between 0 and 1")
    
    @property
    def total_processing_time(self) -> float:
        """Total processing time across all layers."""
        return (
            self.gap_result.processing_time_ms +
            self.contradiction_result.processing_time_ms +
            self.hallucination_result.processing_time_ms
        )
    
    @property
    def has_critical_issues(self) -> bool:
        """True if any critical issues were found."""
        return (
            self.gap_result.critical_gaps_count > 0 or
            self.contradiction_result.high_severity_count > 0 or
            self.hallucination_result.high_risk_count > 0
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "gap_result": self.gap_result.to_dict(),
            "contradiction_result": self.contradiction_result.to_dict(),
            "hallucination_result": self.hallucination_result.to_dict(),
            "overall_consistency_score": self.overall_consistency_score,
            "critical_issues": self.critical_issues,
            "recommendations": self.recommendations,
            "total_processing_time": self.total_processing_time,
            "has_critical_issues": self.has_critical_issues,
        }
