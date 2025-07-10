"""Thin runner that delegates to the new `create_app` factory (Milestone 8)."""

from clinical_note_quality.http import create_app

# Legacy shim for test suite compatibility ------------------------------------
from clinical_note_quality.services.grading_service import grade_note_hybrid  # noqa: F401 – re-export for tests


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
