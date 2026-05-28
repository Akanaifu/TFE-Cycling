"""Shared filesystem paths for backend storage."""

from __future__ import annotations

from pathlib import Path


def get_project_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[3]


def get_storage_root() -> Path:
    """Return the top-level storage directory used by the backend."""
    return get_project_root() / "DB"


def get_rides_root() -> Path:
    """Return the shared rides storage directory."""
    return get_storage_root() / "rides"


def get_cyclist_rides_dir(cyclist: str) -> Path:
    """Return the storage directory for a specific cyclist."""
    cyclist_name = str(cyclist or "").strip()
    if not cyclist_name:
        raise ValueError("Cyclist name is required")
    return get_rides_root() / cyclist_name
