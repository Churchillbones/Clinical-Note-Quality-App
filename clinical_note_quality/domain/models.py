"""Domain models for Clinical Note Quality grading.

These dataclasses are **pure** and contain **no external dependencies** beyond the
standard library.  They purposefully avoid importing from *services* or
*adapters* so that the domain layer remains isolated and highly testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Any, Dict, List, Mapping


class PDQIDimension(str, Enum):
    """Enumeration of the nine PDQI-9 rubric dimensions."""

    UP_TO_DATE = "up_to_date"
    ACCURATE = "accurate"
    THOROUGH = "thorough"
    USEFUL = "useful"
    ORGANIZED = "organized"
    CONCISE = "concise"
    CONSISTENT = "consistent"
    COMPLETE = "complete"
    ACTIONABLE = "actionable"

    @classmethod
    def numeric_keys(cls) -> List[str]:
        """Return the PDQI keys expected to hold numeric scores."""

        return [member.value for member in cls]


@dataclass(frozen=True)
class PDQIDimensionExplanation:
    """Value-object encapsulating detailed explanation for a single PDQI dimension."""

    dimension: str
    score: float
    narrative: str
    evidence_excerpts: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate PDQIDimensionExplanation fields."""
        if self.dimension not in PDQIDimension.numeric_keys():
            raise ValueError(f"Invalid PDQI dimension: {self.dimension}")
        
        if not (1 <= self.score <= 5):
            raise ValueError(f"PDQI score must be between 1-5, got: {self.score}")
        
        if not isinstance(self.narrative, str) or not self.narrative.strip():
            raise ValueError("Narrative must be a non-empty string")
        
        if len(self.narrative) > 1000:
            raise ValueError("Narrative must not exceed 1000 characters")
        
        if not isinstance(self.evidence_excerpts, list):
            raise ValueError("Evidence excerpts must be a list")
        
        if not isinstance(self.improvement_suggestions, list):
            raise ValueError("Improvement suggestions must be a list")

    @classmethod
    def from_raw_data(cls, dimension: str, score: float, narrative: str, 
                      evidence_excerpts: List[str] | None = None, 
                      improvement_suggestions: List[str] | None = None) -> "PDQIDimensionExplanation":
        """Factory method to create PDQIDimensionExplanation from raw data."""
        return cls(
            dimension=dimension,
            score=score,
            narrative=narrative,
            evidence_excerpts=evidence_excerpts or [],
            improvement_suggestions=improvement_suggestions or []
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON responses."""
        return {
            "dimension": self.dimension,
            "score": self.score,
            "narrative": self.narrative,
            "evidence_excerpts": self.evidence_excerpts,
            "improvement_suggestions": self.improvement_suggestions
        }


@dataclass(frozen=True)
class PDQIScore:
    """Value-object encapsulating PDQI-9 scores and optional commentary."""

    scores: Mapping[str, float]
    summary: str = ""
    rationale: str = ""
    model_provenance: str = "o3"  # Track which strategy/model was used
    dimension_explanations: List[PDQIDimensionExplanation] = field(default_factory=list)
    scoring_rationale: str = ""
    reasoning_summary: str = ""  # Chain of thought reasoning summary

    def __post_init__(self) -> None:  # type: ignore[override]
        # Validate that all required keys exist and values are within 1-5.
        missing = [k for k in PDQIDimension.numeric_keys() if k not in self.scores]
        if missing:
            raise ValueError(f"Missing PDQI keys: {missing}")

        out_of_range = {
            k: v for k, v in self.scores.items() if k in PDQIDimension.numeric_keys() and not (1 <= float(v) <= 5)
        }
        if out_of_range:
            raise ValueError(f"PDQI scores out of 1-5 range: {out_of_range}")

        # Validate dimension_explanations if provided
        if self.dimension_explanations and len(self.dimension_explanations) != 9:
            raise ValueError(f"Must have exactly 9 dimension explanations, got: {len(self.dimension_explanations)}")
        
        # Validate dimension explanations match scores
        if self.dimension_explanations:
            explanation_dims = {exp.dimension for exp in self.dimension_explanations}
            expected_dims = set(PDQIDimension.numeric_keys())
            if explanation_dims != expected_dims:
                raise ValueError(f"Dimension explanations mismatch. Expected: {expected_dims}, got: {explanation_dims}")

    @property
    def total(self) -> float:
        """Return the total PDQI score (9-45 scale)."""
        numeric = [float(self.scores[k]) for k in PDQIDimension.numeric_keys()]
        return sum(numeric)
    
    @property  
    def average(self) -> float:
        """Return the average PDQI score (1-5 scale) - DEPRECATED, use total instead."""
        import warnings
        warnings.warn("PDQIScore.average is deprecated, use PDQIScore.total instead", DeprecationWarning, stacklevel=2)
        return self.total / 9.0

    def to_dict(self) -> Dict[str, Any]:
        ret: Dict[str, Any] = dict(self.scores)
        ret["summary"] = self.summary
        if self.rationale:
            ret["rationale"] = self.rationale
        ret["model_provenance"] = self.model_provenance
        
        # Include narrative fields if present
        if self.dimension_explanations:
            ret["dimension_explanations"] = [exp.to_dict() for exp in self.dimension_explanations]
        if self.scoring_rationale:
            ret["scoring_rationale"] = self.scoring_rationale
        # reasoning_summary kept internal only per user requirements
        # if self.reasoning_summary:
        #     ret["reasoning_summary"] = self.reasoning_summary
            
        return ret


@dataclass(frozen=True)
class HeuristicResult:
    """Result from heuristic analysis."""

    length_score: float
    redundancy_score: float
    structure_score: float
    composite_score: float
    word_count: int
    character_count: int
    length_narrative: str = ""
    redundancy_narrative: str = ""
    structure_narrative: str = ""
    composite_narrative: str = ""

    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate narrative field lengths."""
        narratives = [
            ("length_narrative", self.length_narrative),
            ("redundancy_narrative", self.redundancy_narrative),
            ("structure_narrative", self.structure_narrative),
            ("composite_narrative", self.composite_narrative)
        ]
        
        for name, narrative in narratives:
            if narrative and len(narrative) > 500:
                raise ValueError(f"{name} must not exceed 500 characters")
            if narrative and not narrative.strip():
                raise ValueError(f"{name} must be non-empty if provided")

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Only include narrative fields if they have content
        narrative_fields = ["length_narrative", "redundancy_narrative", "structure_narrative", "composite_narrative"]
        for field_name in narrative_fields:
            if not result[field_name]:
                del result[field_name]
        return result


@dataclass(frozen=True)
class FactualityResult:
    """Result from factuality assessment."""

    consistency_score: float
    claims_checked: int
    summary: str = ""
    claims: List[Dict[str, Any]] = field(default_factory=list)
    hallucinations: List[Dict[str, Any]] = field(default_factory=list)  # NEW: O3-detected hallucinations
    consistency_narrative: str = ""
    claims_narratives: List[str] = field(default_factory=list)
    reasoning_summary: str = ""  # Chain of thought reasoning summary

    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate narrative fields structure."""
        # Allow claims_narratives to be empty or have fewer entries than claims for backward compatibility
        # but if both are non-empty, claims_narratives should not exceed claims length
        if self.claims_narratives and self.claims and len(self.claims_narratives) > len(self.claims):
            raise ValueError(f"Claims narratives length ({len(self.claims_narratives)}) cannot exceed claims length ({len(self.claims)})")

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Only include narrative fields if they have content
        if not result["consistency_narrative"]:
            del result["consistency_narrative"]
        if not result["claims_narratives"]:
            del result["claims_narratives"]
        # reasoning_summary kept internal only per user requirements  
        if "reasoning_summary" in result:
            del result["reasoning_summary"]
        return result


@dataclass(frozen=True)
class HybridResult:
    """Aggregate of PDQI, heuristic, factuality, and embedding analyses."""

    pdqi: PDQIScore
    heuristic: HeuristicResult
    factuality: FactualityResult
    hybrid_score: float
    overall_grade: str
    weights_used: Mapping[str, float]
    chain_of_thought: str = ""
    final_grade_narrative: str = ""
    component_weighting_explanation: str = ""
    reasoning_summary: str = ""  # Aggregate reasoning summary from all components
    reasoning_analysis_log: str = ""  # 🧠 AI Reasoning Process Analysis Log
    
    # Week 2: Embedding-based analysis results
    discrepancy_analysis: Dict[str, Any] = field(default_factory=dict)  # Combined embedding analysis

    def __post_init__(self) -> None:  # type: ignore[override]
        """Validate narrative fields."""
        if self.final_grade_narrative and len(self.final_grade_narrative) > 1000:
            raise ValueError("Final grade narrative must not exceed 1000 characters")
        
        if self.component_weighting_explanation and len(self.component_weighting_explanation) > 500:
            raise ValueError("Component weighting explanation must not exceed 500 characters")

    # ----- Convenience API -------------------------------------------------

    @classmethod
    def from_raw(cls, data: Dict[str, Any]) -> "HybridResult":  # noqa: D401
        """Construct from the raw dict returned by legacy `grade_note_hybrid`."""
        pdqi_data = data.get("pdqi_scores", {})
        
        # Handle dimension explanations if present
        dimension_explanations = []
        if "dimension_explanations" in pdqi_data:
            for exp_data in pdqi_data["dimension_explanations"]:
                dimension_explanations.append(PDQIDimensionExplanation(
                    dimension=exp_data.get("dimension", ""),
                    score=float(exp_data.get("score", 0)),
                    narrative=exp_data.get("narrative", ""),
                    evidence_excerpts=exp_data.get("evidence_excerpts", []),
                    improvement_suggestions=exp_data.get("improvement_suggestions", [])
                ))

        pdqi_obj = PDQIScore(
            scores={k: pdqi_data.get(k, 0) for k in PDQIDimension.numeric_keys()},
            summary=pdqi_data.get("summary", ""),
            rationale=pdqi_data.get("rationale", ""),
            model_provenance=pdqi_data.get("model_provenance", "unknown"),
            dimension_explanations=dimension_explanations,
            scoring_rationale=pdqi_data.get("scoring_rationale", ""),
            reasoning_summary=pdqi_data.get("reasoning_summary", "")
        )
        
        heur = data.get("heuristic_analysis", {})
        heuristic_obj = HeuristicResult(
            length_score=float(heur.get("length_score", 0)),
            redundancy_score=float(heur.get("redundancy_score", 0)),
            structure_score=float(heur.get("structure_score", 0)),
            composite_score=float(heur.get("composite_score", 0)),
            word_count=int(heur.get("word_count", 0)),
            character_count=int(heur.get("character_count", 0)),
            length_narrative=heur.get("length_narrative", ""),
            redundancy_narrative=heur.get("redundancy_narrative", ""),
            structure_narrative=heur.get("structure_narrative", ""),
            composite_narrative=heur.get("composite_narrative", "")
        )
        
        fact = data.get("factuality_analysis", {})
        factuality_obj = FactualityResult(
            consistency_score=float(fact.get("consistency_score", 0)),
            claims_checked=int(fact.get("claims_checked", 0)),
            summary=fact.get("summary", ""),
            claims=fact.get("claims", []),
            consistency_narrative=fact.get("consistency_narrative", ""),
            claims_narratives=fact.get("claims_narratives", []),
            reasoning_summary=fact.get("reasoning_summary", "")
        )
        
        return cls(
            pdqi=pdqi_obj,
            heuristic=heuristic_obj,
            factuality=factuality_obj,
            hybrid_score=float(data.get("hybrid_score", 0)),
            overall_grade=data.get("overall_grade", ""),
            weights_used=data.get("weights_used", {}),
            chain_of_thought=data.get("chain_of_thought", ""),
            final_grade_narrative=data.get("final_grade_narrative", ""),
            component_weighting_explanation=data.get("component_weighting_explanation", ""),
            reasoning_summary=data.get("reasoning_summary", ""),
            reasoning_analysis_log=data.get("reasoning_analysis_log", "")
        )

    def as_dict(self) -> Dict[str, Any]:
        """Serialise for JSON responses."""
        result = {
            "pdqi_scores": self.pdqi.to_dict(),
            "pdqi_total": round(self.pdqi.total, 2),
            "heuristic_analysis": self.heuristic.to_dict(),
            "factuality_analysis": self.factuality.to_dict(),
            "hybrid_score": self.hybrid_score,
            "overall_grade": self.overall_grade,
            "weights_used": dict(self.weights_used),
            "chain_of_thought": self.chain_of_thought,
        }
        
        # Include narrative fields if they have content
        if self.final_grade_narrative:
            result["final_grade_narrative"] = self.final_grade_narrative
        if self.component_weighting_explanation:
            result["component_weighting_explanation"] = self.component_weighting_explanation
        # Add AI Reasoning Process Analysis Log
        if self.reasoning_analysis_log:
            result["reasoning_analysis_log"] = self.reasoning_analysis_log
        # reasoning_summary kept internal only per user requirements
        # if self.reasoning_summary:
        #     result["reasoning_summary"] = self.reasoning_summary
            
        return result 