"""Composite grading service (Milestone 7).

Produces a `HybridResult` by orchestrating PDQI, heuristic, and factuality
services while applying weighted aggregation rules defined in settings.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import anyio

from clinical_note_quality.domain import HybridResult
from clinical_note_quality import get_settings
from clinical_note_quality.services import (
    get_pdqi_service,
    get_heuristic_service,
    get_factuality_service,
)
from clinical_note_quality.observability import (
    get_logger,
    RequestTracker,
    record_pdqi_score,
)

logger = get_logger(__name__)


def _numeric_grade(score: float) -> str:
    if score >= 4.5:
        return "A"
    if score >= 3.5:
        return "B"
    if score >= 2.5:
        return "C"
    if score >= 1.5:
        return "D"
    return "F"


class GradingService:  # noqa: D101 – obvious
    def __init__(
        self,
        *,
        settings=None,
        pdqi_service=None,
        heuristic_service=None,
        factuality_service=None,
    ) -> None:
        self.settings = settings or get_settings()
        self.pdqi_service = pdqi_service or get_pdqi_service()
        self.heuristic_service = heuristic_service or get_heuristic_service()
        self.factuality_service = factuality_service or get_factuality_service()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def grade(
        self,
        note: str,
        transcript: str = "",
        precision: str = "medium",
    ) -> HybridResult:  # noqa: D401,E501
        with RequestTracker(precision=precision) as correlation_id:
            logger.info("GradingService: starting grade pipeline", note_length=len(note))

            pdqi = self.pdqi_service.score(note, precision=precision)
            heuristics = self.heuristic_service.analyze(note)
            factuality = self.factuality_service.assess(note, transcript, precision=precision)

            # Record PDQI metrics
            for dimension, score in pdqi.scores.items():
                record_pdqi_score(dimension, float(score), pdqi.model_provenance)

            hybrid_score = (
                pdqi.average * self.settings.PDQI_WEIGHT
                + heuristics.composite_score * self.settings.HEURISTIC_WEIGHT
                + factuality.consistency_score * self.settings.FACTUALITY_WEIGHT
            )
            hybrid_score = max(1.0, min(5.0, round(hybrid_score, 2)))

            # Enhanced chain of thought for internal assessment documentation
            chain_parts = []
            
            # PDQI Analysis
            if pdqi.rationale:
                chain_parts.append("PDQI Rationale:\n" + pdqi.rationale.strip())
            if pdqi.summary:
                chain_parts.append("PDQI Summary:\n" + pdqi.summary.strip())
            if pdqi.scoring_rationale:
                chain_parts.append("PDQI Scoring Methodology:\n" + pdqi.scoring_rationale.strip())
                
            # Heuristic Analysis 
            if heuristics.composite_narrative:
                chain_parts.append("Heuristic Analysis:\n" + heuristics.composite_narrative.strip())
            else:
                heuristic_summary = f"Length: {heuristics.length_score:.1f}, Redundancy: {heuristics.redundancy_score:.1f}, Structure: {heuristics.structure_score:.1f}"
                chain_parts.append("Heuristic Analysis:\n" + heuristic_summary)
                
            # Factuality Analysis
            if factuality.summary:
                chain_parts.append("Factuality Summary:\n" + factuality.summary.strip())
            if factuality.consistency_narrative:
                chain_parts.append("Factuality Assessment:\n" + factuality.consistency_narrative.strip())
                
            # Component Integration
            weights_explanation = f"Hybrid Score Calculation: PDQI ({self.settings.PDQI_WEIGHT}) × {pdqi.average:.2f} + Heuristic ({self.settings.HEURISTIC_WEIGHT}) × {heuristics.composite_score:.2f} + Factuality ({self.settings.FACTUALITY_WEIGHT}) × {factuality.consistency_score:.2f} = {hybrid_score:.2f}"
            chain_parts.append("Score Integration:\n" + weights_explanation)
            
            chain_of_thought = "\n\n".join(chain_parts)
            
            # Create comprehensive AI Reasoning Process Analysis Log
            reasoning_log_parts = []
            
            # Header
            reasoning_log_parts.append("🧠 AI REASONING PROCESS ANALYSIS LOG")
            reasoning_log_parts.append("=" * 50)
            
            # PDQI Analysis Section
            if pdqi.rationale or pdqi.summary or pdqi.scoring_rationale:
                reasoning_log_parts.append("\n📊 PDQI-9 CLINICAL QUALITY ANALYSIS")
                reasoning_log_parts.append("-" * 35)
                if pdqi.summary:
                    reasoning_log_parts.append(f"Overall Assessment: {pdqi.summary.strip()}")
                if pdqi.rationale:
                    reasoning_log_parts.append(f"Detailed Rationale: {pdqi.rationale.strip()}")
                if pdqi.scoring_rationale:
                    reasoning_log_parts.append(f"Scoring Methodology: {pdqi.scoring_rationale.strip()}")
                reasoning_log_parts.append(f"Average Score: {pdqi.average:.2f}/5.0")
            
            # Heuristic Analysis Section  
            reasoning_log_parts.append("\n🔍 HEURISTIC QUALITY ANALYSIS")
            reasoning_log_parts.append("-" * 30)
            if heuristics.composite_narrative:
                reasoning_log_parts.append(f"Comprehensive Analysis: {heuristics.composite_narrative.strip()}")
            else:
                reasoning_log_parts.append(f"Length Assessment: {heuristics.length_score:.1f}/5.0")
                reasoning_log_parts.append(f"Redundancy Analysis: {heuristics.redundancy_score:.1f}/5.0") 
                reasoning_log_parts.append(f"Structure Evaluation: {heuristics.structure_score:.1f}/5.0")
            reasoning_log_parts.append(f"Composite Score: {heuristics.composite_score:.2f}/5.0")
            
            # Factuality Analysis Section
            if factuality.summary or factuality.consistency_narrative:
                reasoning_log_parts.append("\n✅ FACTUALITY CONSISTENCY ANALYSIS")
                reasoning_log_parts.append("-" * 35)
                if factuality.summary:
                    reasoning_log_parts.append(f"Summary: {factuality.summary.strip()}")
                if factuality.consistency_narrative:
                    reasoning_log_parts.append(f"Detailed Assessment: {factuality.consistency_narrative.strip()}")
                if factuality.claims:
                    reasoning_log_parts.append(f"Claims Analyzed: {len(factuality.claims)}")
                    for i, claim in enumerate(factuality.claims[:3], 1):  # Show first 3 claims
                        reasoning_log_parts.append(f"  {i}. {claim.get('claim', '')[:100]}... → {claim.get('support', 'Unknown')}")
                reasoning_log_parts.append(f"Consistency Score: {factuality.consistency_score:.2f}/5.0")
            
            # Integration Analysis Section
            reasoning_log_parts.append("\n⚖️ HYBRID SCORE INTEGRATION")
            reasoning_log_parts.append("-" * 28)
            reasoning_log_parts.append(f"Component Weights: PDQI ({self.settings.PDQI_WEIGHT:.1f}) + Heuristic ({self.settings.HEURISTIC_WEIGHT:.1f}) + Factuality ({self.settings.FACTUALITY_WEIGHT:.1f})")
            reasoning_log_parts.append(f"Calculation: ({pdqi.average:.2f} × {self.settings.PDQI_WEIGHT:.1f}) + ({heuristics.composite_score:.2f} × {self.settings.HEURISTIC_WEIGHT:.1f}) + ({factuality.consistency_score:.2f} × {self.settings.FACTUALITY_WEIGHT:.1f}) = {hybrid_score:.2f}")
            reasoning_log_parts.append(f"Final Grade: {_numeric_grade(hybrid_score)} ({hybrid_score:.2f}/5.0)")
            
            # Footer
            reasoning_log_parts.append("\n" + "=" * 50)
            reasoning_log_parts.append("Analysis completed with O3 reasoning models")
            
            reasoning_analysis_log = "\n".join(reasoning_log_parts)
            reasoning_summary = ""  # Keep empty as reasoning stays in analysis log

            result = HybridResult(
                pdqi=pdqi,
                heuristic=heuristics,
                factuality=factuality,
                hybrid_score=hybrid_score,
                overall_grade=_numeric_grade(hybrid_score),
                weights_used={
                    "pdqi_weight": self.settings.PDQI_WEIGHT,
                    "heuristic_weight": self.settings.HEURISTIC_WEIGHT,
                    "factuality_weight": self.settings.FACTUALITY_WEIGHT,
                },
                chain_of_thought=chain_of_thought,
                reasoning_summary=reasoning_summary,
                reasoning_analysis_log=reasoning_analysis_log,
            )
            logger.info(
                "GradingService: completed", 
                hybrid_score=hybrid_score,
                overall_grade=result.overall_grade,
                pdqi_average=pdqi.average,
                model_provenance=pdqi.model_provenance
            )
            return result

    async def grade_async(
        self,
        note: str,
        transcript: str = "",
        precision: str = "medium",
    ) -> HybridResult:  
        """Async version with concurrent subsystem evaluation using anyio task groups."""
        with RequestTracker(precision=precision) as correlation_id:
            logger.info("GradingService: starting async grade pipeline", note_length=len(note))
        
            async def run_pdqi():
                """Run PDQI scoring in executor for now (until services are fully async)."""
                return await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.pdqi_service.score(note, precision=precision)
                )
            
            async def run_heuristics():
                """Run heuristic analysis in executor."""
                return await asyncio.get_event_loop().run_in_executor(
                    None, self.heuristic_service.analyze, note
                )
            
            async def run_factuality():
                """Run factuality assessment in executor."""
                return await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.factuality_service.assess(note, transcript, precision=precision)
                )
            
            # Launch tasks concurrently using anyio task groups
            results = {}
            
            async def pdqi_wrapper():
                results['pdqi'] = await run_pdqi()
            
            async def heuristics_wrapper():
                results['heuristics'] = await run_heuristics()
            
            async def factuality_wrapper():
                results['factuality'] = await run_factuality()
            
            async with anyio.create_task_group() as tg:
                tg.start_soon(pdqi_wrapper)
                tg.start_soon(heuristics_wrapper) 
                tg.start_soon(factuality_wrapper)
            
            # Extract results
            pdqi = results['pdqi']
            heuristics = results['heuristics']
            factuality = results['factuality']
            
            # Same aggregation logic as sync version
            hybrid_score = (
                pdqi.average * self.settings.PDQI_WEIGHT
                + heuristics.composite_score * self.settings.HEURISTIC_WEIGHT
                + factuality.consistency_score * self.settings.FACTUALITY_WEIGHT
            )
            hybrid_score = max(1.0, min(5.0, round(hybrid_score, 2)))

            # Enhanced chain of thought for internal assessment documentation
            chain_parts = []
            
            # PDQI Analysis
            if pdqi.rationale:
                chain_parts.append("PDQI Rationale:\n" + pdqi.rationale.strip())
            if pdqi.summary:
                chain_parts.append("PDQI Summary:\n" + pdqi.summary.strip())
            if pdqi.scoring_rationale:
                chain_parts.append("PDQI Scoring Methodology:\n" + pdqi.scoring_rationale.strip())
                
            # Heuristic Analysis 
            if heuristics.composite_narrative:
                chain_parts.append("Heuristic Analysis:\n" + heuristics.composite_narrative.strip())
            else:
                heuristic_summary = f"Length: {heuristics.length_score:.1f}, Redundancy: {heuristics.redundancy_score:.1f}, Structure: {heuristics.structure_score:.1f}"
                chain_parts.append("Heuristic Analysis:\n" + heuristic_summary)
                
            # Factuality Analysis
            if factuality.summary:
                chain_parts.append("Factuality Summary:\n" + factuality.summary.strip())
            if factuality.consistency_narrative:
                chain_parts.append("Factuality Assessment:\n" + factuality.consistency_narrative.strip())
                
            # Component Integration
            weights_explanation = f"Hybrid Score Calculation: PDQI ({self.settings.PDQI_WEIGHT}) × {pdqi.average:.2f} + Heuristic ({self.settings.HEURISTIC_WEIGHT}) × {heuristics.composite_score:.2f} + Factuality ({self.settings.FACTUALITY_WEIGHT}) × {factuality.consistency_score:.2f} = {hybrid_score:.2f}"
            chain_parts.append("Score Integration:\n" + weights_explanation)
            
            chain_of_thought = "\n\n".join(chain_parts)

            # Create comprehensive AI Reasoning Process Analysis Log (async version)
            reasoning_log_parts = []
            
            # Header
            reasoning_log_parts.append("🧠 AI REASONING PROCESS ANALYSIS LOG")
            reasoning_log_parts.append("=" * 50)
            
            # PDQI Analysis Section
            if pdqi.rationale or pdqi.summary or pdqi.scoring_rationale:
                reasoning_log_parts.append("\n📊 PDQI-9 CLINICAL QUALITY ANALYSIS")
                reasoning_log_parts.append("-" * 35)
                if pdqi.summary:
                    reasoning_log_parts.append(f"Overall Assessment: {pdqi.summary.strip()}")
                if pdqi.rationale:
                    reasoning_log_parts.append(f"Detailed Rationale: {pdqi.rationale.strip()}")
                if pdqi.scoring_rationale:
                    reasoning_log_parts.append(f"Scoring Methodology: {pdqi.scoring_rationale.strip()}")
                reasoning_log_parts.append(f"Average Score: {pdqi.average:.2f}/5.0")
            
            # Heuristic Analysis Section  
            reasoning_log_parts.append("\n🔍 HEURISTIC QUALITY ANALYSIS")
            reasoning_log_parts.append("-" * 30)
            if heuristics.composite_narrative:
                reasoning_log_parts.append(f"Comprehensive Analysis: {heuristics.composite_narrative.strip()}")
            else:
                reasoning_log_parts.append(f"Length Assessment: {heuristics.length_score:.1f}/5.0")
                reasoning_log_parts.append(f"Redundancy Analysis: {heuristics.redundancy_score:.1f}/5.0") 
                reasoning_log_parts.append(f"Structure Evaluation: {heuristics.structure_score:.1f}/5.0")
            reasoning_log_parts.append(f"Composite Score: {heuristics.composite_score:.2f}/5.0")
            
            # Factuality Analysis Section
            if factuality.summary or factuality.consistency_narrative:
                reasoning_log_parts.append("\n✅ FACTUALITY CONSISTENCY ANALYSIS")
                reasoning_log_parts.append("-" * 35)
                if factuality.summary:
                    reasoning_log_parts.append(f"Summary: {factuality.summary.strip()}")
                if factuality.consistency_narrative:
                    reasoning_log_parts.append(f"Detailed Assessment: {factuality.consistency_narrative.strip()}")
                if factuality.claims:
                    reasoning_log_parts.append(f"Claims Analyzed: {len(factuality.claims)}")
                    for i, claim in enumerate(factuality.claims[:3], 1):  # Show first 3 claims
                        reasoning_log_parts.append(f"  {i}. {claim.get('claim', '')[:100]}... → {claim.get('support', 'Unknown')}")
                reasoning_log_parts.append(f"Consistency Score: {factuality.consistency_score:.2f}/5.0")
            
            # Integration Analysis Section
            reasoning_log_parts.append("\n⚖️ HYBRID SCORE INTEGRATION")
            reasoning_log_parts.append("-" * 28)
            reasoning_log_parts.append(f"Component Weights: PDQI ({self.settings.PDQI_WEIGHT:.1f}) + Heuristic ({self.settings.HEURISTIC_WEIGHT:.1f}) + Factuality ({self.settings.FACTUALITY_WEIGHT:.1f})")
            reasoning_log_parts.append(f"Calculation: ({pdqi.average:.2f} × {self.settings.PDQI_WEIGHT:.1f}) + ({heuristics.composite_score:.2f} × {self.settings.HEURISTIC_WEIGHT:.1f}) + ({factuality.consistency_score:.2f} × {self.settings.FACTUALITY_WEIGHT:.1f}) = {hybrid_score:.2f}")
            reasoning_log_parts.append(f"Final Grade: {_numeric_grade(hybrid_score)} ({hybrid_score:.2f}/5.0)")
            
            # Footer
            reasoning_log_parts.append("\n" + "=" * 50)
            reasoning_log_parts.append("Analysis completed with O3 reasoning models")
            
            reasoning_analysis_log = "\n".join(reasoning_log_parts)
            reasoning_summary = ""  # Keep empty as reasoning stays in analysis log

            result = HybridResult(
                pdqi=pdqi,
                heuristic=heuristics,
                factuality=factuality,
                hybrid_score=hybrid_score,
                overall_grade=_numeric_grade(hybrid_score),
                weights_used={
                    "pdqi_weight": self.settings.PDQI_WEIGHT,
                    "heuristic_weight": self.settings.HEURISTIC_WEIGHT,
                    "factuality_weight": self.settings.FACTUALITY_WEIGHT,
                },
                chain_of_thought=chain_of_thought,
                reasoning_summary=reasoning_summary,
                reasoning_analysis_log=reasoning_analysis_log,
            )
            logger.info(
                "GradingService: async completed", 
                hybrid_score=hybrid_score,
                overall_grade=result.overall_grade,
                pdqi_average=pdqi.average,
                model_provenance=pdqi.model_provenance
            )
            return result


# ------------------------------------------------------------------
# Legacy compatibility
# ------------------------------------------------------------------

def grade_note_hybrid(clinical_note: str, encounter_transcript: str = "", model_precision: str = "medium"):
    """Legacy compatibility wrapper for tests and backwards compatibility.
    
    Returns a dictionary in the old format to maintain API compatibility.
    """
    service = GradingService()
    result = service.grade(clinical_note, encounter_transcript, model_precision)
    
    # Convert HybridResult back to legacy dictionary format WITH enhanced narratives
    pdqi_data = result.pdqi.to_dict()  # This includes all enhanced narrative fields
    
    return {
        'pdqi_scores': pdqi_data,  # Enhanced: Now includes dimension_explanations & scoring_rationale
        'pdqi_average': result.pdqi.average,
        'heuristic_analysis': result.heuristic.to_dict(),  # Enhanced: Includes narrative fields
        'factuality_analysis': result.factuality.to_dict(),  # Enhanced: Includes narrative fields
        'hybrid_score': result.hybrid_score,
        'overall_grade': result.overall_grade,
        'weights_used': result.weights_used,
        'chain_of_thought': result.chain_of_thought,
        # Enhanced: Include new narrative fields
        'final_grade_narrative': result.final_grade_narrative,
        'component_weighting_explanation': result.component_weighting_explanation,
        'reasoning_analysis_log': result.reasoning_analysis_log  # 🧠 AI Reasoning Process Analysis Log
    }