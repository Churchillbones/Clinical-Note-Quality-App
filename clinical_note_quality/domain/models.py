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
class PDQIScore:
    """Value-object encapsulating PDQI-9 scores and optional commentary."""

    scores: Mapping[str, float]
    summary: str = ""
    rationale: str = ""

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

    @property
    def average(self) -> float:
        numeric = [float(self.scores[k]) for k in PDQIDimension.numeric_keys()]
        return sum(numeric) / len(numeric)

    def to_dict(self) -> Dict[str, Any]:
        ret = dict(self.scores)
        ret["summary"] = self.summary
        if self.rationale:
            ret["rationale"] = self.rationale
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FactualityResult:
    """Result from factuality assessment."""

    consistency_score: float
    claims_checked: int
    summary: str = ""
    claims: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HybridResult:
    """Aggregate of PDQI, heuristic, and factuality analyses."""

    pdqi: PDQIScore
    heuristic: HeuristicResult
    factuality: FactualityResult
    hybrid_score: float
    overall_grade: str
    weights_used: Mapping[str, float]
    chain_of_thought: str = ""

    # ----- Convenience API -------------------------------------------------

    @classmethod
    def from_raw(cls, data: Dict[str, Any]) -> "HybridResult":  # noqa: D401
        """Construct from the raw dict returned by legacy `grade_note_hybrid`."""
        pdqi_obj = PDQIScore(
            scores={k: data["pdqi_scores"].get(k, 0) for k in PDQIDimension.numeric_keys()},
            summary=data["pdqi_scores"].get("summary", ""),
            rationale=data["pdqi_scores"].get("rationale", ""),
        )
        heur = data.get("heuristic_analysis", {})
        heuristic_obj = HeuristicResult(
            length_score=float(heur.get("length_score", 0)),
            redundancy_score=float(heur.get("redundancy_score", 0)),
            structure_score=float(heur.get("structure_score", 0)),
            composite_score=float(heur.get("composite_score", 0)),
            word_count=int(heur.get("word_count", 0)),
            character_count=int(heur.get("character_count", 0)),
        )
        fact = data.get("factuality_analysis", {})
        factuality_obj = FactualityResult(
            consistency_score=float(fact.get("consistency_score", 0)),
            claims_checked=int(fact.get("claims_checked", 0)),
            summary=fact.get("summary", ""),
            claims=fact.get("claims", []),
        )
        return cls(
            pdqi=pdqi_obj,
            heuristic=heuristic_obj,
            factuality=factuality_obj,
            hybrid_score=float(data.get("hybrid_score", 0)),
            overall_grade=data.get("overall_grade", ""),
            weights_used=data.get("weights_used", {}),
            chain_of_thought=data.get("chain_of_thought", ""),
        )

    def as_dict(self) -> Dict[str, Any]:
        """Serialise for JSON responses."""
        return {
            "pdqi_scores": self.pdqi.to_dict(),
            "pdqi_average": round(self.pdqi.average, 2),
            "heuristic_analysis": self.heuristic.to_dict(),
            "factuality_analysis": self.factuality.to_dict(),
            "hybrid_score": self.hybrid_score,
            "overall_grade": self.overall_grade,
            "weights_used": dict(self.weights_used),
            "chain_of_thought": self.chain_of_thought,
        } 