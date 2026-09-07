"""Application entrypoint.

Vercel's Python runtime looks for a top-level `app` in one of a fixed set of
filenames (`main.py` among them) at the project root, so this file must stay
here and must keep exporting `app`.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from nichedocs import __version__
from nichedocs.config import ConfigError, get_settings
from nichedocs.errors import AppError
from nichedocs.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("nichedocs")

app = FastAPI(
    title="NicheDocs AI",
    version=__version__,
    description=(
        "Ask questions about a university student handbook and get answers "
        "grounded in the document, with page and section citations."
    ),
)

# Read config eagerly so a misconfigured deployment fails at import time with a
# clear message, rather than 500-ing on the first real request.
try:
    _settings = get_settings()
    _allowed_origins = _settings.allowed_origins
except ConfigError:
    logger.exception("Configuration error — the API will reject requests")
    _allowed_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    """Turn domain errors into consistent JSON the frontend can render."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(ConfigError)
def handle_config_error(_: Request, exc: ConfigError) -> JSONResponse:
    logger.error("Configuration error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "configuration_error",
                "message": "The server is not configured correctly.",
            }
        },
    )


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "name": "NicheDocs AI",
        "version": __version__,
        "docs": "/docs",
    }


app.include_router(router)
