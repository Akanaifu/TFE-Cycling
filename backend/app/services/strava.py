"""Strava configuration and OAuth helpers for backend routes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

import pandas as pd

from app.services.security import encrypt_secret_fernet


AUTH_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
API_BASE = "https://www.strava.com/api/v3"


def _format_exchange_error(status_code: int, body: str) -> str:
    raw = f"Strava token exchange failed (HTTP {status_code}): {body}"
    lower = body.lower()

    if status_code == 401 and "authorization error" in lower and "application" in lower:
        return (
            raw
            + "\n\nTroubleshooting:\n"
            + "- STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET are invalid or do not match the same Strava app.\n"
            + "- Re-copy both values from https://www.strava.com/settings/api (same app card).\n"
            + "- Generate a NEW OAuth URL, then a NEW code, and exchange immediately (code is single-use)."
        )

    if status_code == 400 and "invalid" in lower and "code" in lower:
        return (
            raw
            + "\n\nTroubleshooting:\n"
            + "- OAuth code is invalid, expired, or already used.\n"
            + "- Generate a fresh code from /strava/auth-url and retry quickly."
        )

    return raw


def _read_env_file() -> dict[str, str]:
    """Read backend .env as a lightweight fallback when process env is missing."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return {}

    parsed: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        parsed[key] = value
    return parsed


def _read_env(name: str, default: str = "") -> str:
    file_env = _read_env_file()
    if name in file_env and file_env[name] != "":
        value = file_env[name]
    else:
        value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else str(value)


def _read_env_any(names: list[str], default: str = "") -> str:
    for name in names:
        value = _read_env(name, "")
        if value:
            return value
    return default


def get_strava_settings() -> dict[str, str]:
    """Read Strava settings from environment."""
    return {
        "client_id": _read_env_any(["STRAVA_CLIENT_ID"]),
        "client_secret": _read_env_any(["STRAVA_CLIENT_SECRET"]),
        "redirect_uri": _read_env_any(["STRAVA_REDIRECT_URI", "STRAVA_REDIRECT_URL"]),
        "scopes": _read_env_any(["STRAVA_SCOPES"], "read,activity:read_all"),
        "tokens_file": _read_env_any(["STRAVA_TOKENS_FILE"], ".strava_tokens.json"),
    }


def get_strava_status() -> dict[str, object]:
    """Return non-sensitive status information for UI."""
    settings = get_strava_settings()
    return {
        "configured": bool(
            settings["client_id"]
            and settings["client_secret"]
            and settings["redirect_uri"]
        ),
        "has_client_id": bool(settings["client_id"]),
        "has_client_secret": bool(settings["client_secret"]),
        "has_redirect_uri": bool(settings["redirect_uri"]),
        "redirect_uri": settings["redirect_uri"],
        "scopes": settings["scopes"],
        "tokens_file": settings["tokens_file"],
    }


def build_authorization_url(state: str | None = None) -> str:
    """Build Strava OAuth authorization URL using environment settings."""
    settings = get_strava_settings()

    if not settings["client_id"]:
        raise ValueError("Missing STRAVA_CLIENT_ID")
    if not settings["redirect_uri"]:
        raise ValueError("Missing STRAVA_REDIRECT_URI")

    params: dict[str, str] = {
        "client_id": settings["client_id"],
        "response_type": "code",
        "redirect_uri": settings["redirect_uri"],
        "approval_prompt": "auto",
        "scope": settings["scopes"],
    }
    if state:
        params["state"] = state

    return f"{AUTH_URL}?{urlencode(params)}"


def _resolve_tokens_path(tokens_file: str) -> Path:
    path = Path(tokens_file)
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


def _extract_oauth_code(raw_value: str) -> str:
    """Normalize OAuth code input from either plain code or callback URL/query."""
    clean = (raw_value or "").strip().strip('"').strip("'")
    if not clean:
        return ""

    def _code_from_query(query: str) -> str:
        parsed = parse_qs(query, keep_blank_values=False)
        values = parsed.get("code")
        if values and values[0]:
            return values[0].strip()
        return ""

    if clean.startswith("http://") or clean.startswith("https://"):
        parsed_url = urlparse(clean)
        return _code_from_query(parsed_url.query) or _code_from_query(
            parsed_url.fragment
        )

    if clean.startswith("?"):
        return _code_from_query(clean[1:])

    if "code=" in clean and ("&" in clean or "=" in clean):
        return _code_from_query(clean)

    return clean


def _save_tokens(tokens_payload: dict[str, Any], tokens_file: str) -> Path:
    target = _resolve_tokens_path(tokens_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(tokens_payload, indent=2), encoding="utf-8")
    return target


def build_encrypted_tokens_payload(tokens_payload: dict[str, Any]) -> dict[str, Any]:
    """Prepare a Fernet-encrypted payload for future database storage."""
    access_token = str(tokens_payload.get("access_token", "") or "").strip()
    refresh_token = str(tokens_payload.get("refresh_token", "") or "").strip()

    if not access_token or not refresh_token:
        raise ValueError("Missing access_token or refresh_token for encryption")

    return {
        "access_token_enc": encrypt_secret_fernet(access_token),
        "refresh_token_enc": encrypt_secret_fernet(refresh_token),
        "expires_at": tokens_payload.get("expires_at"),
        "scope": tokens_payload.get("scope"),
    }


def exchange_code_for_tokens_payload(code: str) -> dict[str, Any]:
    """Exchange OAuth code for Strava tokens and return raw payload."""
    clean_code = _extract_oauth_code(code)
    if not clean_code:
        raise ValueError(
            "Missing OAuth code. Paste either the raw code or the full callback URL."
        )

    settings = get_strava_settings()
    if not settings["client_id"]:
        raise ValueError("Missing STRAVA_CLIENT_ID")
    if not settings["client_secret"]:
        raise ValueError("Missing STRAVA_CLIENT_SECRET")
    if not settings["redirect_uri"]:
        raise ValueError("Missing STRAVA_REDIRECT_URI")

    payload = {
        "client_id": settings["client_id"],
        "client_secret": settings["client_secret"],
        "code": clean_code,
        "grant_type": "authorization_code",
    }

    request = Request(
        TOKEN_URL,
        data=urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(_format_exchange_error(exc.code, body)) from exc
    except URLError as exc:
        raise ValueError(f"Strava token exchange network error: {exc}") from exc

    try:
        token_payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid token response from Strava") from exc

    if not isinstance(token_payload, dict):
        raise ValueError("Unexpected token payload format")

    if "access_token" not in token_payload:
        raise ValueError(f"Token response missing access_token: {token_payload}")

    return token_payload


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    """Exchange OAuth code for Strava tokens and persist them on disk."""
    settings = get_strava_settings()
    token_payload = exchange_code_for_tokens_payload(code)

    saved_path = _save_tokens(token_payload, settings["tokens_file"])
    athlete = token_payload.get("athlete")
    athlete_id = athlete.get("id") if isinstance(athlete, dict) else None

    return {
        "saved": True,
        "tokens_file": str(saved_path),
        "token_type": token_payload.get("token_type", "Bearer"),
        "expires_at": token_payload.get("expires_at"),
        "athlete_id": athlete_id,
    }


def _load_tokens(tokens_file: str) -> dict[str, Any]:
    """Load tokens from persisted JSON file."""
    tokens_path = _resolve_tokens_path(tokens_file)
    if not tokens_path.exists():
        raise ValueError(f"Tokens file not found: {tokens_path}")

    try:
        with open(tokens_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Invalid tokens format")
        return data
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse tokens JSON: {exc}") from exc


def _is_token_expired(tokens: dict[str, Any], min_valid_seconds: int = 300) -> bool:
    """Check if access token is expired or near expiration."""
    expires_at = tokens.get("expires_at")
    if expires_at is None:
        return True
    try:
        expires_at_i = int(expires_at)
    except (TypeError, ValueError):
        return True
    from time import time

    return time() > (expires_at_i - min_valid_seconds)


def is_token_expired(tokens: dict[str, Any], min_valid_seconds: int = 300) -> bool:
    """Public wrapper for token expiration checks."""
    return _is_token_expired(tokens, min_valid_seconds=min_valid_seconds)


def _refresh_tokens(
    client_id: str, client_secret: str, refresh_token: str
) -> dict[str, Any]:
    """Refresh expired access token using refresh token."""
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    request = Request(
        TOKEN_URL,
        data=urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(f"Token refresh failed (HTTP {exc.code}): {body}") from exc
    except URLError as exc:
        raise ValueError(f"Token refresh network error: {exc}") from exc


def refresh_tokens(
    client_id: str, client_secret: str, refresh_token: str
) -> dict[str, Any]:
    """Public wrapper for Strava token refresh."""
    return _refresh_tokens(client_id, client_secret, refresh_token)


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    """Make GET request and parse JSON response."""
    request = Request(url, headers=headers or {}, method="GET")
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(f"GET {url} failed (HTTP {exc.code}): {body}") from exc
    except URLError as exc:
        raise ValueError(f"GET {url} network error: {exc}") from exc


def get_athlete_activities(
    access_token: str,
    limit: int = 10,
    before: int | None = None,
    after: int | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch recent athlete activities from Strava API.

    Args:
        access_token: Valid Strava access token
        limit: Maximum number of activities to return (default 10)
        before: Unix timestamp to limit to activities before this time
        after: Unix timestamp to limit to activities after this time

    Returns:
        List of activity summaries with id, name, sport_type, distance, duration, etc.
    """
    params: dict[str, Any] = {
        "page": 1,
        "per_page": limit,
    }
    if before is not None:
        params["before"] = before
    if after is not None:
        params["after"] = after

    query_string = urlencode(params)
    url = f"{API_BASE}/athlete/activities?{query_string}"
    headers = {"Authorization": f"Bearer {access_token}"}

    data = _http_get_json(url, headers=headers)
    if not isinstance(data, list):
        raise ValueError("Unexpected response format from Strava activities endpoint")

    # Filter for cycling activities and enrich with display info
    cycling_types = {
        "Ride",
        "MountainBikeRide",
        "GravelRide",
        "EBikeRide",
        "VirtualRide",
        "Bike",
    }

    result = []
    for activity in data:
        sport_type = activity.get("sport_type", "")
        if sport_type not in cycling_types:
            continue

        result.append(
            {
                "id": activity.get("id"),
                "name": activity.get("name", "Untitled"),
                "sport_type": sport_type,
                "distance": activity.get("distance"),  # in meters
                "moving_time": activity.get("moving_time"),  # in seconds
                "elapsed_time": activity.get("elapsed_time"),  # in seconds
                "total_elevation_gain": activity.get("total_elevation_gain"),
                "start_date": activity.get("start_date"),
                "average_speed": activity.get("average_speed"),
                "max_speed": activity.get("max_speed"),
                "average_heartrate": activity.get("average_heartrate"),
                "max_heartrate": activity.get("max_heartrate"),
                "average_watts": activity.get("average_watts"),
                "max_watts": activity.get("max_watts"),
            }
        )

    return result


def get_activity_streams(access_token: str, activity_id: int) -> dict[str, list[Any]]:
    """Fetch activity streams (time, heartrate, watts, distance, etc.) from Strava."""
    url = (
        f"{API_BASE}/activities/{activity_id}/streams"
        "?keys=time,heartrate,watts,distance,velocity_smooth,cadence"
        "&key_by_type=true"
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    data = _http_get_json(url, headers=headers)
    if not isinstance(data, dict):
        raise ValueError("Unexpected response format from Strava streams endpoint")

    streams: dict[str, list[Any]] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            raw_values = value.get("data", [])
        else:
            raw_values = value
        if isinstance(raw_values, list):
            streams[key] = list(raw_values)
        else:
            streams[key] = []
    return streams


def build_activity_dataframe(
    *,
    activity: dict[str, Any],
    streams: dict[str, list[Any]],
) -> pd.DataFrame:
    """Build a ride dataframe compatible with the existing pickle pipeline."""
    time_stream = streams.get("time") or []
    heartrate_stream = streams.get("heartrate") or []
    watts_stream = streams.get("watts") or []
    distance_stream = streams.get("distance") or []
    velocity_stream = streams.get("velocity_smooth") or []
    cadence_stream = streams.get("cadence") or []

    length = max(
        [
            len(time_stream),
            len(heartrate_stream),
            len(watts_stream),
            len(distance_stream),
            len(velocity_stream),
            len(cadence_stream),
        ]
        or [0]
    )

    rows: list[dict[str, Any]] = []
    for index in range(length):
        rows.append(
            {
                "t": time_stream[index] if index < len(time_stream) else index,
                "hr": (
                    heartrate_stream[index] if index < len(heartrate_stream) else None
                ),
                "po": watts_stream[index] if index < len(watts_stream) else None,
                "distance": (
                    distance_stream[index] if index < len(distance_stream) else None
                ),
                "speed": (
                    velocity_stream[index] if index < len(velocity_stream) else None
                ),
                "cadence": (
                    cadence_stream[index] if index < len(cadence_stream) else None
                ),
                "activity_id": activity.get("id"),
                "start_date": activity.get("start_date"),
                "sport_type": activity.get("sport_type"),
                "name": activity.get("name", "Untitled"),
            }
        )

    if not rows:
        rows = [
            {
                "t": 0,
                "hr": activity.get("average_heartrate"),
                "po": activity.get("average_watts"),
                "distance": activity.get("distance"),
                "speed": activity.get("average_speed"),
                "cadence": None,
                "activity_id": activity.get("id"),
                "start_date": activity.get("start_date"),
                "sport_type": activity.get("sport_type"),
                "name": activity.get("name", "Untitled"),
            }
        ]

    frame = pd.DataFrame(rows)
    frame.attrs["ride_datetime_label"] = activity.get("start_date") or "unknown"
    frame.attrs["activity_id"] = activity.get("id")
    frame.attrs["activity_name"] = activity.get("name", "Untitled")
    return frame
