import asyncio
import logging
import json
from typing import Dict, Any

try:
    from openai import AzureOpenAI, APIError
except ModuleNotFoundError:  # For unit-test environments without SDK
    AzureOpenAI = None  # type: ignore
    APIError = Exception  # type: ignore

from config import Config
from .constants import DIMENSION_DESCRIPTIONS

logger = logging.getLogger(__name__)


class RingAgent:
    """A lightweight sub-agent that focuses on a single PDQI-9 dimension."""

    def __init__(self, dimension: str):
        if dimension not in DIMENSION_DESCRIPTIONS:
            raise ValueError(f"Unknown PDQI dimension: {dimension}")
        self.dimension = dimension
        self.description = DIMENSION_DESCRIPTIONS[dimension]

        # Delay SDK client construction until we know credentials exist
        self._client = None
        if AzureOpenAI and Config.AZURE_OPENAI_KEY and Config.AZURE_OPENAI_ENDPOINT:
            try:
                self._client = AzureOpenAI(
                    azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
                    api_key=Config.AZURE_OPENAI_KEY,
                    api_version=Config.AZURE_O3_API_VERSION,
                )
            except Exception as e:
                logger.warning("Failed to instantiate AzureOpenAI in RingAgent; falling back to stub: %s", e)

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    async def score(self, clinical_note: str) -> Dict[str, Any]:
        """Return a mapping like {dimension: {score, evidence, rationale}}."""
        if self._client is None:
            # Deterministic stub (score 3) for offline / unit-test mode
            logger.debug("RingAgent stub scoring for %s", self.dimension)
            return {self.dimension: {"score": 3, "evidence": [], "rationale": "stub"}}

        system_prompt = (
            "You are an expert clinical documentation reviewer specialised in the PDQI-9 dimension "
            f"'{self.dimension}'. This dimension refers to: {self.description}.\n"
            "Given the following clinical note, assign an integer score from 1 (poor) to 5 (excellent) "
            "ONLY for this dimension. Also provide up to three short evidence excerpts (≤30 words each) "
            "from the note that justify your score and a terse rationale ≤25 words.\n\n"
            "Return ONLY a JSON object with keys 'score', 'evidence' (list of strings), and 'rationale'."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": clinical_note},
        ]

        kwargs = {
            "model": Config.AZURE_O3_DEPLOYMENT,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if hasattr(Config, "MAX_COMPLETION_TOKENS") and Config.MAX_COMPLETION_TOKENS:
            kwargs["max_completion_tokens"] = Config.MAX_COMPLETION_TOKENS

        loop = asyncio.get_event_loop()
        response_content = await loop.run_in_executor(None, self._chat_completion, kwargs)
        try:
            payload = json.loads(response_content)
            score = int(payload.get("score", 0))
            evidence = payload.get("evidence", []) or []
            rationale = payload.get("rationale", "")
            return {self.dimension: {"score": score, "evidence": evidence, "rationale": rationale}}
        except Exception as e:
            logger.error("RingAgent failed to parse response for %s: %s", self.dimension, e)
            return {self.dimension: {"score": 3, "evidence": [], "rationale": "fallback"}}

    # ------------------------------------------------------------------
    def _chat_completion(self, kwargs: Dict[str, Any]) -> str:
        """Blocking call to Azure chat completion; isolated for executor."""
        try:
            response = self._client.chat.completions.create(**kwargs)  # type: ignore
            return response.choices[0].message.content.strip()
        except APIError as e:  # type: ignore
            logger.error("AzureOpenAI error in RingAgent: %s", e)
            return "{""score"":3}" 