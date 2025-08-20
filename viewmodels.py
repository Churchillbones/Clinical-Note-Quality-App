from dataclasses import dataclass, asdict
from typing import Dict, Any

@dataclass
class GradingViewModel:
    """Normalize grading result into numeric-friendly view model."""
    pdqi_scores: Dict[str, Any]
    pdqi_total: float  # Changed from pdqi_average to pdqi_total for 9-45 scoring
    heuristic_analysis: Dict[str, Any]
    factuality_analysis: Dict[str, Any]
    hybrid_score: float
    overall_grade: str
    weights_used: Dict[str, Any]
    chain_of_thought: str = ""

    @classmethod
    def from_result(cls, result: Dict[str, Any]):
        # Deep-copy PDQI scores and ensure numeric types
        pdqi_scores: Dict[str, Any] = {}
        for k, v in result.get("pdqi_scores", {}).items():
            if k in {"summary", "rationale"}:
                pdqi_scores[k] = v
            else:
                try:
                    pdqi_scores[k] = float(v)
                except (TypeError, ValueError):
                    pdqi_scores[k] = 0.0
        return cls(
            pdqi_scores=pdqi_scores,
            pdqi_total=float(result.get("pdqi_total", 0)),  # Changed from pdqi_average to pdqi_total
            heuristic_analysis=result.get("heuristic_analysis", {}),
            factuality_analysis=result.get("factuality_analysis", {}),
            hybrid_score=float(result.get("hybrid_score", 0)),
            overall_grade=result.get("overall_grade", "N/A"),
            weights_used=result.get("weights_used", {}),
            chain_of_thought=result.get("chain_of_thought", ""),
        )

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self) 