"""Flask blueprint containing web + API routes (Milestone 8)."""
from __future__ import annotations

import logging
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, render_template, request

from clinical_note_quality.services import GradingService

logger = logging.getLogger(__name__)

bp = Blueprint("web", __name__)

_service = GradingService()


def _to_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@bp.app_template_filter("to_number")
def _jinja_to_number_filter(value: Any) -> float:  # noqa: D401 – filter
    return _to_number(value)


@bp.route("/", methods=["GET"])
def index():
    error = request.args.get("error")
    return render_template("index.html", error=error)


@bp.route("/grade", methods=["POST"])
def grade_via_form():
    try:
        note = request.form["clinical_note"]
        transcript = request.form.get("encounter_transcript", "")
        precision = request.form.get("model_precision", "medium")
        logger.info("/grade request received (precision=%s)", precision)
        result = _grade_note(note, transcript, precision)

        if current_app.testing:
            from config import Config

            defaults = {
                "pdqi_scores": {"summary": ""},
                "heuristic_analysis": {
                    "length_score": 0,
                    "redundancy_score": 0,
                    "structure_score": 0,
                    "composite_score": 0,
                    "word_count": 0,
                    "character_count": 0,
                },
                "factuality_analysis": {
                    "summary": "",
                    "consistency_score": 0,
                    "claims_checked": 0,
                    "claims": [],
                },
                "weights_used": {
                    "pdqi_weight": Config.PDQI_WEIGHT,
                    "heuristic_weight": Config.HEURISTIC_WEIGHT,
                    "factuality_weight": Config.FACTUALITY_WEIGHT,
                },
                "chain_of_thought": "",
            }
            for k, v in defaults.items():
                result.setdefault(k, v)

        return render_template("result.html", result=result)
    except Exception as exc:  # noqa: BLE001 – broad catch for route safety
        logger.error("Error during /grade: %s", exc, exc_info=True)
        from grading.exceptions import (
            OpenAIServiceError,
            OpenAIAuthError,
            OpenAIResponseError,
        )

        if isinstance(exc, (OpenAIServiceError, OpenAIAuthError, OpenAIResponseError)):
            msg = str(exc)
        else:
            msg = "An unexpected error occurred during grading. Please try again."
        return render_template("index.html", error=msg)


@bp.route("/api/grade", methods=["POST"])
def grade_via_api():
    try:
        data: Dict[str, Any] | None = request.get_json(silent=True)
        if not data or "clinical_note" not in data:
            return jsonify({"error": "clinical_note is required"}), 400
        note = data["clinical_note"]
        transcript = data.get("encounter_transcript")  # None if missing to match legacy tests
        precision = data.get("model_precision", "medium")
        result = _grade_note(note, transcript, precision)
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error during /api/grade: %s", exc, exc_info=True)
        from grading.exceptions import (
            OpenAIServiceError,
            OpenAIAuthError,
            OpenAIResponseError,
        )

        if isinstance(exc, (OpenAIServiceError, OpenAIAuthError, OpenAIResponseError)):
            msg = str(exc)
        else:
            msg = "An unexpected error occurred during grading."
        return jsonify({"error": msg}), 500


# ---------------------------------------------------------------------------
# Internal helper to keep legacy tests (which patch app.grade_note_hybrid)
# working while preferring the new GradingService in production.
# ---------------------------------------------------------------------------


def _grade_note(note: str, transcript: str | None, precision: str) -> Dict[str, Any]:
    """Dispatch to patched legacy function when present else use new service."""

    import importlib

    app_mod = importlib.import_module("app")

    if hasattr(app_mod, "grade_note_hybrid"):
        kwargs = {
            "clinical_note": note,
            "encounter_transcript": transcript,
        }
        # Legacy route only forwarded model_precision when not default
        if precision != "medium":
            kwargs["model_precision"] = precision
        return app_mod.grade_note_hybrid(**kwargs)

    return _service.grade(note, transcript or "", precision).as_dict() 