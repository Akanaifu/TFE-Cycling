"""Utility functions for environment, configuration, and diagnostic."""

import os
from pathlib import Path


def is_truthy_env(value: str) -> bool:
    """Check if an environment variable value is truthy."""
    return value.strip().lower() in {"1", "true", "yes", "on"}


_is_truthy_env = is_truthy_env


def is_pkl_diagnostic_enabled() -> bool:
    """Check if PKL file diagnostics are enabled via env."""
    return is_truthy_env(os.getenv("ENABLE_PKL_DIAGNOSTIC", ""))


def use_secure_cookie() -> bool:
    """Determine if secure cookies should be used based on environment."""
    explicit = os.getenv("AUTH_COOKIE_SECURE", "").strip()
    if explicit:
        return is_truthy_env(explicit)

    node_env = os.getenv("NODE_ENV", "").strip().lower()
    if node_env in {"development", "dev", "local"}:
        return False

    return True


def trust_forwarded_headers() -> bool:
    """Check if X-Forwarded-For headers should be trusted."""
    return is_truthy_env(os.getenv("TRUST_FORWARDED_HEADERS", "false"))


def get_client_ip(request_headers: dict, client_host: str | None) -> str:
    """Extract client IP from request headers or direct connection."""
    if trust_forwarded_headers():
        forwarded_for = request_headers.get("x-forwarded-for", "").strip()
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
    return client_host or "unknown"


def _read_env_file() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return {}

    parsed: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def _read_env(name: str, default: str = "") -> str:
    file_env = _read_env_file()
    if name in file_env and file_env[name] != "":
        value = file_env[name]
    else:
        value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else str(value)
