"""Flask blueprint containing web + API routes (Milestone 8)."""
from __future__ import annotations

import logging
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, render_template, request, Response

from clinical_note_quality.services import GradingService
from clinical_note_quality.observability import get_metrics
from clinical_note_quality.domain import (
    OpenAIServiceError,
    OpenAIAuthError,
    OpenAIResponseError,
)

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

        if isinstance(exc, (OpenAIServiceError, OpenAIAuthError, OpenAIResponseError)):
            msg = str(exc)
        else:
            msg = "An unexpected error occurred during grading. Please try again."
        return render_template("index.html", error=msg)


@bp.route("/api/grade", methods=["POST"])
def grade_via_api():
    """API endpoint for programmatic access - returns JSON."""
    try:
        # Prefer JSON payload, but gracefully fallback to form-encoded bodies
        data: Dict[str, Any] | None = request.get_json(silent=True) if request.is_json else None

        # For HTMX (and standard form submissions) the body will be x-www-form-urlencoded
        if data is None:
            data = request.form.to_dict(flat=True)

        # If still no data or missing required field, return 400
        if not data or "clinical_note" not in data:
            return jsonify({"error": "clinical_note is required"}), 400

        note = data["clinical_note"]
        transcript = data.get("encounter_transcript")  # None if missing to match legacy tests
        precision = data.get("model_precision", "medium")
        result = _grade_note(note, transcript, precision)
        
        # Check if this is an HTMX request (expects HTML fragment)
        if request.headers.get("HX-Request"):
            return render_template("results_partial.html", result=result)

        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error during /api/grade: %s", exc, exc_info=True)

        if isinstance(exc, (OpenAIServiceError, OpenAIAuthError, OpenAIResponseError)):
            msg = str(exc)
        else:
            msg = "An unexpected error occurred during grading."
        
        # Return error as HTML for HTMX requests
        if request.headers.get('HX-Request'):
            error_html = f'''
            <div class="bg-red-50 border-l-4 border-red-400 p-4 mt-8">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                        </svg>
                    </div>
                    <div class="ml-3">
                        <h3 class="text-sm font-medium text-red-800">Analysis Failed</h3>
                        <p class="text-sm text-red-700 mt-1">{msg}</p>
                        <button onclick="location.reload()" class="mt-3 bg-red-100 hover:bg-red-200 text-red-800 px-3 py-1 rounded text-sm">
                            Try Again
                        </button>
                    </div>
                </div>
            </div>
            '''
            return error_html, 500
        
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

    # Ensure we get the data structure the templates expect
    result = _service.grade(note, transcript or "", precision)
    result_dict = result.as_dict()
    
    # Ensure required fields for UI templates
    if "pdqi_average" not in result_dict:
        pdqi_scores = result_dict.get("pdqi_scores", {})
        numeric_scores = []
        for key, value in pdqi_scores.items():
            if key not in ["summary", "rationale", "model_provenance"]:
                try:
                    numeric_scores.append(float(value))
                except (ValueError, TypeError):
                    pass
        result_dict["pdqi_average"] = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0.0
    
    return result_dict


@bp.route("/metrics", methods=["GET"])
def metrics():
    """Prometheus metrics endpoint."""
    try:
        metrics_data, content_type = get_metrics()
        return Response(metrics_data, content_type=content_type)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error fetching metrics: %s", exc, exc_info=True)
        return Response("# Error fetching metrics\n", content_type="text/plain"), 500 