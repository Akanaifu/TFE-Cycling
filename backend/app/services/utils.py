"""Utility functions for environment, configuration, and diagnostic."""

import os


def is_truthy_env(value: str) -> bool:
    """Check if an environment variable value is truthy."""
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
