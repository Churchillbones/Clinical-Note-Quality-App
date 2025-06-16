"""HTTP layer package – provides Flask application factory (Milestone 8)."""
from __future__ import annotations

import logging
from typing import Any

from flask import Flask

from .routes import bp as web_bp

logger = logging.getLogger(__name__)


def create_app(*, debug: bool | None = None) -> Flask:
    """Return a configured Flask application instance."""

    app = Flask(__name__, template_folder="../../templates")

    from config import Config  # late import to avoid circulars

    app.config.from_object(Config)

    if debug is not None:
        app.debug = debug

    # Register blueprint & filters
    app.register_blueprint(web_bp)

    # Logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    logger.info("Flask app created via create_app()")
    return app 