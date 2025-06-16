import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

_MEMORY_FILE = Path("agents_memory.json")


class MemoryAgent:
    """Persists PDQI-9 score history for longitudinal analytics."""

    def save(self, note_id: str, pdqi_scores: Dict[str, Any], summary: str) -> None:
        record = {
            "note_id": note_id,
            "timestamp": datetime.utcnow().isoformat(),
            "pdqi_scores": pdqi_scores,
            "summary": summary,
        }
        # Load existing
        try:
            if _MEMORY_FILE.exists():
                data = json.loads(_MEMORY_FILE.read_text())
            else:
                data = []
            data.append(record)
            _MEMORY_FILE.write_text(json.dumps(data, indent=2))
            logger.debug("MemoryAgent stored record for %s", note_id)
        except Exception as e:
            logger.error("MemoryAgent failed to store record: %s", e)

    def get_history(self, note_id: str):
        if not _MEMORY_FILE.exists():
            return []
        try:
            data = json.loads(_MEMORY_FILE.read_text())
            return [r for r in data if r["note_id"] == note_id]
        except Exception:  # pragma: no cover
            return [] 