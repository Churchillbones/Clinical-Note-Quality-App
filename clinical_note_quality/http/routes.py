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
        
        # Debug logging for precision selection
        logger.info(f"Form submission - precision selected: '{precision}' (type: {type(precision)})")
        logger.info(f"Available form fields: {list(request.form.keys())}")
        
        # Enforce character limits
        if len(note) > 20000:
            error_msg = f"Clinical note exceeds the maximum limit of 20,000 characters. Your note has {len(note):,} characters. Please reduce the content by {len(note) - 20000:,} characters."
            return render_template("index.html", error=error_msg)
        
        if len(transcript) > 40000:
            error_msg = f"Encounter transcript exceeds the maximum limit of 40,000 characters. Your transcript has {len(transcript):,} characters. Please reduce the content by {len(transcript) - 40000:,} characters."
            return render_template("index.html", error=error_msg)
            
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
        
        # Debug logging for precision selection via API
        logger.info(f"API submission - precision selected: '{precision}' (type: {type(precision)})")
        logger.info(f"Available data fields: {list(data.keys())}")
        
        # Enforce character limits
        if len(note) > 20000:
            error_msg = f"Clinical note exceeds the maximum limit of 20,000 characters. Your note has {len(note):,} characters. Please reduce the content by {len(note) - 20000:,} characters."
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
                            <h3 class="text-sm font-medium text-red-800">Character Limit Exceeded</h3>
                            <p class="text-sm text-red-700 mt-1">{error_msg}</p>
                        </div>
                    </div>
                </div>
                '''
                return error_html, 400
            return jsonify({"error": error_msg}), 400
            
        if transcript and len(transcript) > 40000:
            error_msg = f"Encounter transcript exceeds the maximum limit of 40,000 characters. Your transcript has {len(transcript):,} characters. Please reduce the content by {len(transcript) - 40000:,} characters."
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
                            <h3 class="text-sm font-medium text-red-800">Character Limit Exceeded</h3>
                            <p class="text-sm text-red-700 mt-1">{error_msg}</p>
                        </div>
                    </div>
                </div>
                '''
                return error_html, 400
            return jsonify({"error": error_msg}), 400
            
        result = _grade_note(note, transcript, precision)
        
        # Check if this is an HTMX request (expects HTML fragment)
        if request.headers.get("HX-Request"):
            # Ensure result is a dictionary with pdqi_total for template rendering
            if not isinstance(result, dict):
                result = result.as_dict() if hasattr(result, 'as_dict') else result
            
            # Debug logging to understand the data structure
            logger.info(f"Template data structure - keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            if isinstance(result, dict) and "pdqi_scores" in result:
                logger.info(f"PDQI scores structure: {type(result['pdqi_scores'])} with keys: {list(result['pdqi_scores'].keys()) if isinstance(result['pdqi_scores'], dict) else 'Not a dict'}")
            
            # Ensure pdqi_total exists for template compatibility
            if "pdqi_total" not in result and "pdqi_scores" in result:
                logger.info("pdqi_total missing, attempting to calculate from pdqi_scores")
                pdqi_scores = result["pdqi_scores"]
                if isinstance(pdqi_scores, dict) and "scores" in pdqi_scores:
                    # Extract from nested scores structure
                    scores = pdqi_scores["scores"]
                    numeric_scores = [float(v) for k, v in scores.items() 
                                    if k not in ["summary", "rationale", "model_provenance"] 
                                    and isinstance(v, (int, float))]
                    result["pdqi_total"] = sum(numeric_scores) if numeric_scores else 0.0
                    logger.info(f"Calculated pdqi_total from nested scores: {result['pdqi_total']}")
                elif isinstance(pdqi_scores, dict):
                    # Extract from flat structure
                    numeric_scores = [float(v) for k, v in pdqi_scores.items() 
                                    if k not in ["summary", "rationale", "model_provenance", "scores"] 
                                    and isinstance(v, (int, float))]
                    result["pdqi_total"] = sum(numeric_scores) if numeric_scores else 0.0
                    logger.info(f"Calculated pdqi_total from flat structure: {result['pdqi_total']}")
            else:
                logger.info(f"pdqi_total already present: {result.get('pdqi_total', 'Still missing!')}")
            
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
    
    # Ensure required fields for UI templates - pdqi_total should be at top level
    if "pdqi_total" not in result_dict:
        pdqi_scores = result_dict.get("pdqi_scores", {})
        numeric_scores = []
        
        # Check if scores are in a nested 'scores' dictionary (from PDQIScore.to_dict())
        if isinstance(pdqi_scores, dict) and "scores" in pdqi_scores:
            scores_dict = pdqi_scores["scores"]
            for key, value in scores_dict.items():
                if key not in ["summary", "rationale", "model_provenance"]:
                    try:
                        numeric_scores.append(float(value))
                    except (ValueError, TypeError):
                        pass
        else:
            # Fallback: check top-level pdqi_scores keys
            for key, value in pdqi_scores.items():
                if key not in ["summary", "rationale", "model_provenance", "scores"]:
                    try:
                        numeric_scores.append(float(value))
                    except (ValueError, TypeError):
                        pass
        
        result_dict["pdqi_total"] = sum(numeric_scores) if numeric_scores else 0.0
    
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