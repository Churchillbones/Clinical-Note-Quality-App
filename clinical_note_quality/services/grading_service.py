"""Composite grading service (Milestone 7).

Produces a `HybridResult` by orchestrating PDQI, heuristic, factuality,
and embedding-based discrepancy services while applying weighted aggregation 
rules defined in settings.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List

import anyio

from clinical_note_quality.domain import HybridResult
from clinical_note_quality import get_settings
from clinical_note_quality.services.pdqi_service import get_pdqi_service
from clinical_note_quality.services.heuristic_service import get_heuristic_service
from clinical_note_quality.services.factuality_service import get_factuality_service
from clinical_note_quality.services.contradiction_detector import ContradictionDetector
from clinical_note_quality.services.hallucination_detector import HallucinationDetector
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
        contradiction_detector=None,
        hallucination_detector=None,
    ) -> None:
        self.settings = settings or get_settings()
        self.pdqi_service = pdqi_service or get_pdqi_service()
        self.heuristic_service = heuristic_service or get_heuristic_service()
        self.factuality_service = factuality_service or get_factuality_service()
        
        # Week 2: Embedding-based detection services
        self.contradiction_detector = contradiction_detector or ContradictionDetector()
        self.hallucination_detector = hallucination_detector or HallucinationDetector()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def grade(
        self,
        note: str,
        transcript: str = "",
        precision: str = "medium",
    ) -> HybridResult:  # noqa: D401,E501
        """Grade a clinical note using all available analysis methods."""
        
        with RequestTracker(precision=precision) as correlation_id:
            logger.info("GradingService: starting grade pipeline", note_length=len(note))

            # Track component timing for performance analysis
            pdqi_start = time.time()
            pdqi = self.pdqi_service.score(note, precision=precision)
            pdqi_duration = time.time() - pdqi_start
            
            heuristic_start = time.time()
            heuristics = self.heuristic_service.analyze(note)
            heuristic_duration = time.time() - heuristic_start
            
            # Week 2: Run embedding-based analysis FIRST when transcript is available
            # This allows us to feed high-risk hallucinations into factuality analysis
            discrepancy_analysis = {}
            high_risk_claims = []
            if transcript.strip():
                embedding_start = time.time()
                discrepancy_analysis = asyncio.run(
                    self._run_embedding_analysis(note, transcript)
                )
                embedding_duration = time.time() - embedding_start
                logger.info(f"Embedding analysis completed in {embedding_duration:.2f}s")
                
                # Extract high-risk claims for enhanced factuality verification
                high_risk_claims = discrepancy_analysis.get("high_risk_claims_for_verification", [])
            else:
                logger.info("No transcript provided - skipping embedding analysis")

            # Enhanced factuality analysis with high-risk hallucination integration
            factuality_start = time.time()
            factuality = self._assess_factuality_with_hallucination_integration(
                note, transcript, precision, high_risk_claims
            )
            factuality_duration = time.time() - factuality_start

            # Record PDQI metrics
            for dimension, score in pdqi.scores.items():
                record_pdqi_score(dimension, float(score), pdqi.model_provenance)

            hybrid_score = (
                (pdqi.total / 9.0) * self.settings.PDQI_WEIGHT  # Normalize 9-45 scale to 1-5 scale
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
                
            # Factuality Analysis (with Hallucination Integration)
            if factuality.summary:
                chain_parts.append("Factuality Summary:\n" + factuality.summary.strip())
            if factuality.consistency_narrative:
                chain_parts.append("Factuality Assessment:\n" + factuality.consistency_narrative.strip())
            
            # Add note about hallucination-factuality integration
            if high_risk_claims:
                integration_summary = f"Integrated {len(high_risk_claims)} high-risk unsubstantiated claims from hallucination detection into factuality verification process."
                chain_parts.append("Hallucination-Factuality Integration:\n" + integration_summary)

            # Week 2: Embedding Analysis
            if discrepancy_analysis:
                chain_parts.append("Embedding Analysis:\n" + self._format_embedding_summary(discrepancy_analysis))
                
            # Component Integration
            weights_explanation = f"Hybrid Score Calculation: PDQI Sum ({self.settings.PDQI_WEIGHT}) × {pdqi.total:.0f}/45→{(pdqi.total/9.0):.2f} + Heuristic ({self.settings.HEURISTIC_WEIGHT}) × {heuristics.composite_score:.2f} + Factuality ({self.settings.FACTUALITY_WEIGHT}) × {factuality.consistency_score:.2f} = {hybrid_score:.2f}"
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
                reasoning_log_parts.append(f"Total Score: {pdqi.total:.0f}/45 (Average: {(pdqi.total/9.0):.2f}/5.0)")
            
            # Heuristic Analysis Section  
            reasoning_log_parts.append("\n📏 HEURISTIC ANALYSIS")
            reasoning_log_parts.append("-" * 20)
            reasoning_log_parts.append(f"Length Score: {heuristics.length_score:.2f}/5.0")
            reasoning_log_parts.append(f"Redundancy Score: {heuristics.redundancy_score:.2f}/5.0")
            reasoning_log_parts.append(f"Structure Score: {heuristics.structure_score:.2f}/5.0")
            reasoning_log_parts.append(f"Composite Score: {heuristics.composite_score:.2f}/5.0")
            if heuristics.composite_narrative:
                reasoning_log_parts.append(f"Analysis: {heuristics.composite_narrative.strip()}")
            
            # Factuality Analysis Section
            reasoning_log_parts.append("\n🔍 FACTUALITY ANALYSIS")
            reasoning_log_parts.append("-" * 22)
            reasoning_log_parts.append(f"Consistency Score: {factuality.consistency_score:.2f}/5.0")
            reasoning_log_parts.append(f"Claims Checked: {factuality.claims_checked}")
            if high_risk_claims:
                reasoning_log_parts.append(f"High-Risk Claims Integrated: {len(high_risk_claims)} unsubstantiated claims verified")
            if factuality.consistency_narrative:
                reasoning_log_parts.append(f"Assessment: {factuality.consistency_narrative.strip()}")

            # Week 2: Embedding Analysis Section
            if discrepancy_analysis:
                reasoning_log_parts.append("\n🔬 EMBEDDING-BASED DISCREPANCY ANALYSIS")
                reasoning_log_parts.append("-" * 40)
                reasoning_log_parts.append(self._format_detailed_embedding_analysis(discrepancy_analysis))
            
            # Final Integration Section
            reasoning_log_parts.append("\n⚖️ HYBRID SCORE INTEGRATION")
            reasoning_log_parts.append("-" * 27)
            reasoning_log_parts.append(f"PDQI Component: {self.settings.PDQI_WEIGHT:.1f} × {pdqi.total:.0f}/45 = {self.settings.PDQI_WEIGHT:.1f} × {(pdqi.total/9.0):.2f} = {((pdqi.total/9.0) * self.settings.PDQI_WEIGHT):.2f}")
            reasoning_log_parts.append(f"Heuristic Component: {self.settings.HEURISTIC_WEIGHT:.1f} × {heuristics.composite_score:.2f} = {(heuristics.composite_score * self.settings.HEURISTIC_WEIGHT):.2f}")
            reasoning_log_parts.append(f"Factuality Component: {self.settings.FACTUALITY_WEIGHT:.1f} × {factuality.consistency_score:.2f} = {(factuality.consistency_score * self.settings.FACTUALITY_WEIGHT):.2f}")
            reasoning_log_parts.append(weights_explanation)
            reasoning_log_parts.append(f"Final Grade: {_numeric_grade(hybrid_score)} ({hybrid_score:.2f}/5.0)")
            
            reasoning_analysis_log = "\n".join(reasoning_log_parts)

            return HybridResult(
                pdqi=pdqi,
                heuristic=heuristics,
                factuality=factuality,
                hybrid_score=hybrid_score,
                overall_grade=_numeric_grade(hybrid_score),
                weights_used={
                    "pdqi": self.settings.PDQI_WEIGHT,
                    "heuristic": self.settings.HEURISTIC_WEIGHT,
                    "factuality": self.settings.FACTUALITY_WEIGHT,
                },
                chain_of_thought=chain_of_thought,
                reasoning_analysis_log=reasoning_analysis_log,
                discrepancy_analysis=discrepancy_analysis,  # Week 2: Include embedding results
            )

    # Week 2: Embedding Analysis Methods
    async def _run_embedding_analysis(self, note: str, transcript: str) -> Dict[str, Any]:
        """Run embedding-based contradiction and hallucination analysis."""
        
        # Run both analyses concurrently with proper resource management
        try:
            async with self.contradiction_detector as cd, self.hallucination_detector as hd:
                contradiction_result = await cd.detect_contradictions(note, transcript)
                hallucination_result = await hd.detect_hallucinations(note, transcript)
                
                # Extract high-risk hallucinations for factuality verification
                high_risk_claims = []
                for hallucination in hallucination_result.hallucinations:
                    if hallucination.risk_level == "high":
                        high_risk_claims.append({
                            "claim": hallucination.claim,
                            "medical_category": hallucination.medical_category.value,
                            "confidence": hallucination.confidence,
                            "source": "hallucination_detector"
                        })
                
                # Combine results for UI display
                return {
                    "contradictions": {
                        "results": [c.to_dict() for c in contradiction_result.contradictions],
                        "count": len(contradiction_result.contradictions),
                        "processing_time_ms": contradiction_result.processing_time_ms,
                    },
                    "hallucinations": {
                        "results": [h.to_dict() for h in hallucination_result.hallucinations],
                        "count": len(hallucination_result.hallucinations),
                        "processing_time_ms": hallucination_result.processing_time_ms,
                    },
                    "high_risk_claims_for_verification": high_risk_claims,  # NEW: Feed to factuality analysis
                    "summary": {
                        "total_issues": len(contradiction_result.contradictions) + len(hallucination_result.hallucinations),
                        "high_risk_count": self._count_high_risk_issues(contradiction_result, hallucination_result),
                        "medical_categories": self._analyze_medical_categories(contradiction_result, hallucination_result),
                    },
                    "has_transcript": True,
                }
        
        except Exception as e:
            logger.error(f"Error in embedding analysis: {e}", exc_info=True)
            return {
                "contradictions": {"results": [], "count": 0, "processing_time_ms": 0},
                "hallucinations": {"results": [], "count": 0, "processing_time_ms": 0},
                "high_risk_claims_for_verification": [],
                "summary": {"total_issues": 0, "high_risk_count": 0, "medical_categories": {}},
                "has_transcript": True,
                "error": str(e),
            }

    def _assess_factuality_with_hallucination_integration(
        self, 
        note: str, 
        transcript: str, 
        precision: str,
        high_risk_claims: List[Dict[str, Any]]
    ) -> Any:
        """Enhanced factuality assessment that specifically verifies high-risk hallucinations."""
        
        # Start with standard factuality assessment
        base_factuality = self.factuality_service.assess(note, transcript, precision=precision)
        
        if not high_risk_claims or not transcript.strip():
            # No high-risk claims to verify or no transcript - return standard assessment
            return base_factuality
        
        logger.info(f"Integrating {len(high_risk_claims)} high-risk hallucinations into factuality verification")
        
        # ACTUALLY VERIFY high-risk claims against transcript
        verified_hallucination_claims = self._verify_high_risk_claims(high_risk_claims, transcript)
        
        # Merge with existing claims and update totals
        existing_claims = base_factuality.claims if hasattr(base_factuality, 'claims') else []
        combined_claims = existing_claims + verified_hallucination_claims
        
        # Update claims_checked count to include high-risk hallucinations
        original_claims_checked = base_factuality.claims_checked
        enhanced_claims_checked = original_claims_checked + len(high_risk_claims)
        
        # Calculate impact on factuality score based on verification results
        verified_support_counts = {"Supported": 0, "Not Supported": 0, "Unclear": 0}
        for claim in verified_hallucination_claims:
            support = claim.get("support", "Unclear")
            verified_support_counts[support] = verified_support_counts.get(support, 0) + 1
        
        # Adjust factuality score if high-risk claims were not supported
        adjusted_score = base_factuality.consistency_score
        if high_risk_claims:
            unsupported_ratio = verified_support_counts["Not Supported"] / len(high_risk_claims)
            # Reduce score if significant high-risk claims are unsupported
            if unsupported_ratio > 0.5:  # More than 50% unsupported
                score_penalty = min(1.0, unsupported_ratio)  # Max penalty of 1 point
                adjusted_score = max(1.0, adjusted_score - score_penalty)
        
        # Create enhanced summary mentioning hallucination integration and results
        verification_summary = f" Verified {len(high_risk_claims)} high-risk unsubstantiated claims: {verified_support_counts['Supported']} supported, {verified_support_counts['Not Supported']} not supported, {verified_support_counts['Unclear']} unclear."
        enhanced_summary = base_factuality.summary + verification_summary
        
        # Return enhanced factuality result with integrated hallucination claims
        from clinical_note_quality.domain.models import FactualityResult
        return FactualityResult(
            consistency_score=round(adjusted_score, 2),
            claims_checked=enhanced_claims_checked,
            summary=enhanced_summary,
            claims=combined_claims,
            hallucinations=base_factuality.hallucinations if hasattr(base_factuality, 'hallucinations') else [],
            consistency_narrative=base_factuality.consistency_narrative,
            claims_narratives=base_factuality.claims_narratives,
            reasoning_summary=base_factuality.reasoning_summary
        )

    def _verify_high_risk_claims(self, high_risk_claims: List[Dict[str, Any]], transcript: str) -> List[Dict[str, Any]]:
        """Actually verify high-risk hallucination claims against the transcript."""
        verified_claims = []
        
        for claim_data in high_risk_claims:
            claim_text = claim_data["claim"]
            
            # Simple verification logic - check if claim content appears in transcript
            verification_result = self._verify_single_claim(claim_text, transcript)
            
            verified_claims.append({
                "claim": claim_text,
                "support": verification_result["support"],
                "explanation": verification_result["explanation"],
                "source": "hallucination_detector_verified",
                "medical_category": claim_data["medical_category"],
                "original_confidence": claim_data["confidence"],
                "verified_by_factuality": True
            })
        
        return verified_claims
    
    def _verify_single_claim(self, claim: str, transcript: str) -> Dict[str, str]:
        """Verify a single claim against transcript using simple text analysis."""
        
        # Extract key terms from the claim
        claim_lower = claim.lower()
        transcript_lower = transcript.lower()
        
        # Simple keyword matching approach
        # Extract potential medical terms, numbers, and specific details
        import re
        
        # Look for specific medical terms, numbers, medications, etc.
        medical_numbers = re.findall(r'\d+(?:\.\d+)?\s*(?:mg|mmhg|bpm|years?|days?|weeks?|months?)', claim_lower)
        medical_terms = re.findall(r'\b(?:hypertension|diabetes|chest pain|medication|history|myocardial|infarction|blood pressure|heart rate|systolic|diastolic)\b', claim_lower)
        
        # Check for presence of key elements
        numbers_found = sum(1 for num in medical_numbers if num in transcript_lower)
        terms_found = sum(1 for term in medical_terms if term in transcript_lower)
        
        total_key_elements = len(medical_numbers) + len(medical_terms)
        found_elements = numbers_found + terms_found
        
        if total_key_elements == 0:
            # No specific medical elements to verify - check general content overlap
            claim_words = set(claim_lower.split())
            transcript_words = set(transcript_lower.split())
            overlap = len(claim_words.intersection(transcript_words))
            
            if overlap >= len(claim_words) * 0.3:  # At least 30% word overlap
                return {
                    "support": "Unclear",
                    "explanation": f"Some content overlap detected but insufficient specific evidence in transcript (word overlap: {overlap}/{len(claim_words)})"
                }
            else:
                return {
                    "support": "Not Supported", 
                    "explanation": f"Minimal content overlap with transcript (word overlap: {overlap}/{len(claim_words)})"
                }
        else:
            # Medical elements present - check verification ratio
            if found_elements == total_key_elements:
                return {
                    "support": "Supported",
                    "explanation": f"All key medical elements found in transcript ({found_elements}/{total_key_elements} verified)"
                }
            elif found_elements > 0:
                return {
                    "support": "Unclear",
                    "explanation": f"Partial verification: {found_elements}/{total_key_elements} key elements found in transcript"
                }
            else:
                return {
                    "support": "Not Supported",
                    "explanation": f"No key medical elements found in transcript (0/{total_key_elements} verified)"
                }

    def _count_high_risk_issues(self, contradiction_result, hallucination_result) -> int:
        """Count high-severity contradictions and high-risk hallucinations."""
        high_risk_count = 0
        
        # Count high-severity contradictions (severity >= 0.8)
        for contradiction in contradiction_result.contradictions:
            if contradiction.severity >= 0.8:
                high_risk_count += 1
        
        # Count high-risk hallucinations
        for hallucination in hallucination_result.hallucinations:
            if hallucination.risk_level == "high":
                high_risk_count += 1
        
        return high_risk_count

    def _analyze_medical_categories(self, contradiction_result, hallucination_result) -> Dict[str, int]:
        """Analyze distribution of issues by medical category."""
        category_counts = {}
        
        # Count contradictions by category
        for contradiction in contradiction_result.contradictions:
            category = contradiction.medical_category.value
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Count hallucinations by category
        for hallucination in hallucination_result.hallucinations:
            category = hallucination.medical_category.value
            category_counts[category] = category_counts.get(category, 0) + 1
        
        return category_counts

    def _format_embedding_summary(self, discrepancy_analysis: Dict[str, Any]) -> str:
        """Format embedding analysis for chain of thought."""
        summary_parts = []
        
        contradiction_count = discrepancy_analysis.get("contradictions", {}).get("count", 0)
        hallucination_count = discrepancy_analysis.get("hallucinations", {}).get("count", 0)
        high_risk_count = discrepancy_analysis.get("summary", {}).get("high_risk_count", 0)
        
        summary_parts.append(f"Found {contradiction_count} contradictions and {hallucination_count} potential hallucinations")
        
        if high_risk_count > 0:
            summary_parts.append(f"{high_risk_count} high-risk issues requiring clinical attention")
        
        medical_categories = discrepancy_analysis.get("summary", {}).get("medical_categories", {})
        if medical_categories:
            top_category = max(medical_categories.items(), key=lambda x: x[1])
            summary_parts.append(f"Most issues in {top_category[0]} category ({top_category[1]} issues)")
        
        return ". ".join(summary_parts)

    def _format_detailed_embedding_analysis(self, discrepancy_analysis: Dict[str, Any]) -> str:
        """Format detailed embedding analysis for reasoning log."""
        details = []
        
        # Contradiction analysis
        contradictions = discrepancy_analysis.get("contradictions", {})
        details.append(f"Contradictions Found: {contradictions.get('count', 0)}")
        if contradictions.get("results"):
            for i, contradiction in enumerate(contradictions["results"][:3]):  # Show first 3
                details.append(f"  {i+1}. {contradiction.get('contradiction_type', 'unknown').title()} contradiction in {contradiction.get('medical_category', 'unknown')} (severity: {contradiction.get('severity', 0):.2f})")
        
        # Hallucination analysis  
        hallucinations = discrepancy_analysis.get("hallucinations", {})
        details.append(f"Hallucinations Found: {hallucinations.get('count', 0)}")
        if hallucinations.get("results"):
            for i, hallucination in enumerate(hallucinations["results"][:3]):  # Show first 3
                details.append(f"  {i+1}. {hallucination.get('risk_level', 'unknown').title()} risk hallucination in {hallucination.get('medical_category', 'unknown')} (confidence: {hallucination.get('confidence', 0):.2f})")
        
        # Hallucination-Factuality Integration
        high_risk_claims = discrepancy_analysis.get("high_risk_claims_for_verification", [])
        if high_risk_claims:
            details.append(f"High-Risk Claims Integrated: {len(high_risk_claims)} sent to factuality verification")
        
        # Summary statistics
        summary = discrepancy_analysis.get("summary", {})
        details.append(f"Total Issues: {summary.get('total_issues', 0)}")
        details.append(f"High-Risk Issues: {summary.get('high_risk_count', 0)}")
        
        return "\n".join(details)

    # ------------------------------------------------------------------
    # Legacy compatibility methods
    # ------------------------------------------------------------------

    async def grade_async(
        self,
        note: str,
        transcript: str = "",
        precision: str = "medium",
    ) -> HybridResult:
        """Async version with concurrent subsystem evaluation using anyio task groups."""
        
        async with anyio.create_task_group() as tg:
            pdqi_future = await tg.start_soon(
                anyio.to_thread.run_sync,
                lambda: self.pdqi_service.score(note, precision=precision)
            )
            heuristic_future = await tg.start_soon(
                anyio.to_thread.run_sync,
                lambda: self.heuristic_service.analyze(note)
            )
            factuality_future = await tg.start_soon(
                anyio.to_thread.run_sync,
                lambda: self.factuality_service.assess(note, transcript, precision=precision)
            )
            
            # Week 2: Run embedding analysis if transcript available
            embedding_future = None
            if transcript.strip():
                embedding_future = await tg.start_soon(
                    self._run_embedding_analysis, note, transcript
                )

        pdqi = await pdqi_future
        heuristics = await heuristic_future
        factuality = await factuality_future
        discrepancy_analysis = await embedding_future if embedding_future else {}

        # Record PDQI metrics
        for dimension, score in pdqi.scores.items():
            record_pdqi_score(dimension, float(score), pdqi.model_provenance)

        hybrid_score = (
            (pdqi.total / 9.0) * self.settings.PDQI_WEIGHT
            + heuristics.composite_score * self.settings.HEURISTIC_WEIGHT
            + factuality.consistency_score * self.settings.FACTUALITY_WEIGHT
        )
        hybrid_score = max(1.0, min(5.0, round(hybrid_score, 2)))

        return HybridResult(
            pdqi=pdqi,
            heuristic=heuristics,
            factuality=factuality,
            hybrid_score=hybrid_score,
            overall_grade=_numeric_grade(hybrid_score),
            weights_used={
                "pdqi": self.settings.PDQI_WEIGHT,
                "heuristic": self.settings.HEURISTIC_WEIGHT,
                "factuality": self.settings.FACTUALITY_WEIGHT,
            },
            discrepancy_analysis=discrepancy_analysis,
        )


# ---------------------------------------------------------------------------
# Legacy compatibility function
# ---------------------------------------------------------------------------

def grade_note_hybrid(
    clinical_note: str,
    encounter_transcript: str | None = None,
    model_precision: str = "medium",
) -> dict[str, Any]:
    """Legacy wrapper around GradingService for backward compatibility.
    
    Returns a dictionary in the old format to maintain API compatibility.
    """
    service = GradingService()
    result = service.grade(
        note=clinical_note,
        transcript=encounter_transcript or "",
        precision=model_precision,
    )
    
    # Convert HybridResult back to dictionary format
    return {
        "pdqi_scores": {
            **result.pdqi.scores,
            "summary": result.pdqi.summary,
            "rationale": result.pdqi.rationale,
            "model_provenance": result.pdqi.model_provenance,
            "dimension_explanations": [
                {
                    "dimension": exp.dimension,
                    "score": exp.score,
                    "narrative": exp.narrative,
                    "evidence_excerpts": exp.evidence_excerpts,
                    "improvement_suggestions": exp.improvement_suggestions,
                }
                for exp in result.pdqi.dimension_explanations
            ],
            "scoring_rationale": result.pdqi.scoring_rationale,
        },
        "pdqi_total": result.pdqi.total,
        "heuristic_analysis": {
            "length_score": result.heuristic.length_score,
            "redundancy_score": result.heuristic.redundancy_score,
            "structure_score": result.heuristic.structure_score,
            "composite_score": result.heuristic.composite_score,
            "word_count": result.heuristic.word_count,
            "character_count": result.heuristic.character_count,
            "length_narrative": result.heuristic.length_narrative,
            "redundancy_narrative": result.heuristic.redundancy_narrative,
            "structure_narrative": result.heuristic.structure_narrative,
            "composite_narrative": result.heuristic.composite_narrative,
        },
        "factuality_analysis": {
            "consistency_score": result.factuality.consistency_score,
            "claims_checked": result.factuality.claims_checked,
            "summary": result.factuality.summary,
            "claims": result.factuality.claims,
            "consistency_narrative": result.factuality.consistency_narrative,
        },
        "hybrid_score": result.hybrid_score,
        "overall_grade": result.overall_grade,
        "weights_used": dict(result.weights_used),
        "chain_of_thought": result.chain_of_thought,
        "reasoning_analysis_log": result.reasoning_analysis_log,
        "discrepancy_analysis": result.discrepancy_analysis,  # Week 2: Include embedding results
    }