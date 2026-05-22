"""FastAPI backend for TFE Cycling analysis.

Exposes REST endpoints for running HR/power prediction models on cycling rides.
Orchestrates routes through modular routers for maintainability.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.services.auth as auth_service
import app.services.database as database_service
from app.core.logging import setup_logging
from app.middleware.logging import log_requests

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure structured logging and request-logging middleware
    setup_logging()
    app.middleware("http")(log_requests)
    yield


app = FastAPI(title="TFE Cycling API", version="0.1.0", lifespan=lifespan)


# ── Startup Event: Security Checks ────────────────────────────────────────────
@app.on_event("startup")
async def startup_security_checks() -> None:
    """Fail fast if unsafe password hashes are present in users table."""
    try:
        insecure_users = database_service.get_users_with_non_bcrypt_hashes(limit=10)
    except Exception as exc:
        raise RuntimeError(
            f"Startup security check failed while validating password hashes: {exc}"
        ) from exc

    if insecure_users:
        preview = ", ".join(insecure_users)
        raise RuntimeError(
            "Unsafe users.password_hash values detected (non-bcrypt). "
            f"Update hashes before startup. Sample users: {preview}"
        )


# ── Configure CORS ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Include Routers ───────────────────────────────────────────────────────────
from app.routers import (
    auth,
    strava,
    cyclists,
    rides,
    analysis,
    diagnostic,
    health,
)

app.include_router(diagnostic.router)
app.include_router(auth.router)
app.include_router(strava.router)
app.include_router(cyclists.router)
app.include_router(rides.router)
app.include_router(analysis.router)
app.include_router(health.router)


# ── Serve React SPA ───────────────────────────────────────────────────────────
_PUBLIC = Path(__file__).parent / "public"
_INDEX = _PUBLIC / "index.html"

if _PUBLIC.exists() and _INDEX.exists():
    app.mount("/", StaticFiles(directory=str(_PUBLIC), html=True), name="spa")
