import asyncio
import logging
import hashlib
from typing import Dict, Any, List

from .constants import PDQI_DIMENSIONS
from .ring_agent import RingAgent
from .citations_agent import CitationsAgent
from .memory_agent import MemoryAgent

logger = logging.getLogger(__name__)


class NineRingsOrchestrator:
    """Lead agent which coordinates nine RingAgents, a CitationsAgent, and MemoryAgent."""

    def __init__(self):
        self._citations_agent = CitationsAgent()
        self._memory_agent = MemoryAgent()

    # ------------------------------------------------------------------
    async def evaluate(self, clinical_note: str) -> Dict[str, Any]:
        """Return PDQI-9 dictionary with summary and rationales."""
        # Build ring agents
        ring_agents: List[RingAgent] = [RingAgent(dim) for dim in PDQI_DIMENSIONS]

        # Launch scoring concurrently
        tasks = [agent.score(clinical_note) for agent in ring_agents]
        ring_results = await asyncio.gather(*tasks)

        # Flatten results
        pdqi_scores: Dict[str, int] = {}
        evidence_map: Dict[str, List[str]] = {}
        rationales: Dict[str, str] = {}
        for res in ring_results:
            dim, payload = next(iter(res.items()))
            pdqi_scores[dim] = payload.get("score", 3)
            evidence_map[dim] = payload.get("evidence", [])
            rationales[dim] = payload.get("rationale", "")

        # Citations validation
        evidence_map = await self._citations_agent.validate(clinical_note, evidence_map)

        # Generate concise summary (rule-based for now)
        summary = self._generate_summary(pdqi_scores)

        # Persist to memory
        note_id = self._hash_note(clinical_note)
        self._memory_agent.save(note_id, pdqi_scores, summary)

        # Assemble response
        pdqi_scores_with_meta: Dict[str, Any] = {**pdqi_scores, "summary": summary, "rationale": self._merge_rationales(rationales)}
        return pdqi_scores_with_meta

    # ------------------------------------------------------------------
    @staticmethod
    def _hash_note(note: str) -> str:
        return hashlib.sha1(note.encode()).hexdigest()[:12]

    @staticmethod
    def _generate_summary(scores: Dict[str, int]) -> str:
        """Generate simple narrative summary from score distribution."""
        strengths = [k for k, v in scores.items() if v >= 4]
        weaknesses = [k for k, v in scores.items() if v <= 2]
        parts = []
        if strengths:
            parts.append("Strong in " + ", ".join(strengths))
        if weaknesses:
            parts.append("Needs improvement in " + ", ".join(weaknesses))
        return "; ".join(parts).capitalize() + "."

    @staticmethod
    def _merge_rationales(rationales: Dict[str, str]) -> str:
        joined = []
        for dim, rat in rationales.items():
            if rat:
                joined.append(f"{dim}: {rat}")
        return "\n".join(joined) 