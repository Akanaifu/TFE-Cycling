"""PostgreSQL connectivity helpers for the backend."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import os
from pathlib import Path
from typing import Any
import importlib


def get_all_rides() -> list[dict[str, Any]]:
    """Get all rides from the database."""
    psycopg, rows = _get_psycopg_modules()
    query = "SELECT id, user_id, activity_id, file_path FROM rides"
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def _read_env_file() -> dict[str, str]:
    """Read backend .env as fallback if process env is missing."""
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


def get_database_url() -> str:
    """Resolve DB connection URL from env.

    Priority:
    1) DATABASE_URL
    2) PG* parts (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD)
    """
    direct_url = _read_env("DATABASE_URL", "")
    if direct_url:
        return direct_url

    host = _read_env("PGHOST", "localhost")
    port = _read_env("PGPORT", "5432")
    database = _read_env("PGDATABASE", "tfe_cycling")
    user = _read_env("PGUSER", "tfe_user")
    password = _read_env("PGPASSWORD", "")

    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    return f"postgresql://{user}@{host}:{port}/{database}"


def _redact_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds_and_host = rest.split("@", 1)
    if len(creds_and_host) != 2:
        return url
    creds, host_part = creds_and_host
    if ":" in creds:
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{host_part}"
    return f"{scheme}://{creds}@{host_part}"


def get_database_status() -> dict[str, Any]:
    """Return DB connectivity status and seed table counters."""
    url = get_database_url()
    counts: dict[str, int] = {}

    try:
        psycopg = importlib.import_module("psycopg")
        psycopg_sql = getattr(psycopg, "sql")
    except ModuleNotFoundError as exc:
        return {
            "connected": False,
            "database_url": _redact_url(url),
            "error": f"Missing dependency psycopg: {exc}",
        }

    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")

                for table_name in [
                    "users",
                    "strava_accounts",
                    "rides",
                    "sync_jobs",
                    "prediction_runs",
                    "app_config_secrets",
                ]:
                    cur.execute(
                        psycopg_sql.SQL("SELECT COUNT(*) FROM {}").format(
                            psycopg_sql.Identifier(table_name)
                        )
                    )
                    row = cur.fetchone()
                    counts[table_name] = int(row[0]) if row else 0

        return {
            "connected": True,
            "database_url": _redact_url(url),
            "tables": counts,
        }
    except (OSError, RuntimeError, ValueError) as exc:
        return {
            "connected": False,
            "database_url": _redact_url(url),
            "error": str(exc),
        }
    except psycopg.Error as exc:
        return {
            "connected": False,
            "database_url": _redact_url(url),
            "error": str(exc),
        }


def _get_psycopg_modules() -> tuple[Any, Any]:
    try:
        psycopg = importlib.import_module("psycopg")
        rows = importlib.import_module("psycopg.rows")
        return psycopg, rows
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"Missing dependency psycopg: {exc}") from exc


def get_project_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[3]


def build_strava_activity_file_path(
    *,
    user_id: str,
    athlete_id: int,
    activity: dict[str, Any],
) -> tuple[str, Path]:
    """Build the relative and absolute PKL paths for a Strava activity."""
    cyclist_folder = _get_user_default_cyclist(user_id)
    activity_id = int(activity.get("id") or 0)
    start_date_raw = str(activity.get("start_date") or "").strip()

    if start_date_raw:
        try:
            normalized = start_date_raw.replace("Z", "+00:00")
            start_dt = datetime.fromisoformat(normalized)
            file_stem = start_dt.strftime("%Y-%m-%dT%H_%M_%S.000000000")
        except ValueError:
            file_stem = f"activity_{activity_id}"
    else:
        file_stem = f"activity_{activity_id}"

    file_name = f"{file_stem}_{athlete_id}_{activity_id}.pkl"
    relative_path = Path("DB") / "rides" / cyclist_folder / file_name
    absolute_path = get_project_root() / relative_path
    return str(relative_path).replace("\\", "/"), absolute_path


def get_user_by_email(email: str) -> dict[str, Any] | None:
    psycopg, rows = _get_psycopg_modules()
    query = """
        SELECT id, email, display_name, password_hash, role, created_at
        FROM users
        WHERE email = %s
        LIMIT 1
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (email,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    psycopg, rows = _get_psycopg_modules()
    query = """
        SELECT id, email, display_name, password_hash, role, created_at
        FROM users
        WHERE id = %s
        LIMIT 1
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_users_with_non_bcrypt_hashes(limit: int = 20) -> list[str]:
    """Return emails for users that do not have bcrypt password hashes."""
    psycopg, rows = _get_psycopg_modules()
    query = """
        SELECT email
        FROM users
        WHERE COALESCE(password_hash, '') = ''
           OR LEFT(password_hash, 2) <> '$2'
        ORDER BY email ASC
        LIMIT %s
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (int(limit),))
            rows_data = cur.fetchall()
            return [str(row.get("email", "")) for row in rows_data if row.get("email")]


def create_user(
    *,
    email: str,
    password_hash: str,
    display_name: str = "",
    role: str = "user",
) -> dict[str, Any] | None:
    """Create a new user with email, password hash, and optional display name."""
    psycopg, rows = _get_psycopg_modules()

    # Check if user already exists
    existing = get_user_by_email(email.strip().lower())
    if existing:
        return None

    query = """
        INSERT INTO users (email, password_hash, display_name, role)
        VALUES (%s, %s, %s, %s)
        RETURNING id, email, display_name, password_hash, role, created_at
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (email.strip().lower(), password_hash, display_name, role),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_strava_account_for_user(
    *,
    user_id: str,
    athlete_id: int,
    access_token_enc: str,
    refresh_token_enc: str,
    expires_at: int | None,
    scope: str,
) -> dict[str, Any]:
    psycopg, rows = _get_psycopg_modules()
    query = """
        INSERT INTO strava_accounts (
            user_id,
            athlete_id,
            access_token_enc,
            refresh_token_enc,
            expires_at,
            scope
        )
        VALUES (%s, %s, %s, %s, to_timestamp(%s), %s)
        ON CONFLICT (athlete_id) DO UPDATE
        SET
            user_id = EXCLUDED.user_id,
            access_token_enc = EXCLUDED.access_token_enc,
            refresh_token_enc = EXCLUDED.refresh_token_enc,
            expires_at = EXCLUDED.expires_at,
            scope = EXCLUDED.scope,
            updated_at = now()
        RETURNING id, user_id, athlete_id, expires_at, scope
    """
    expires_value = int(expires_at) if expires_at is not None else 0
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    user_id,
                    athlete_id,
                    access_token_enc,
                    refresh_token_enc,
                    expires_value,
                    scope,
                ),
            )
            row = cur.fetchone()
            return dict(row) if row else {}


def get_strava_account_for_user(user_id: str) -> dict[str, Any] | None:
    psycopg, rows = _get_psycopg_modules()
    query = """
        SELECT id, user_id, athlete_id, access_token_enc, refresh_token_enc, expires_at, scope
        FROM strava_accounts
        WHERE user_id = %s
        LIMIT 1
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def update_strava_account_tokens(
    *,
    user_id: str,
    access_token_enc: str,
    refresh_token_enc: str,
    expires_at: int | None,
) -> None:
    psycopg, _ = _get_psycopg_modules()
    query = """
        UPDATE strava_accounts
        SET access_token_enc = %s,
            refresh_token_enc = %s,
            expires_at = to_timestamp(%s),
            updated_at = now()
        WHERE user_id = %s
    """
    expires_value = int(expires_at) if expires_at is not None else 0
    with psycopg.connect(get_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (access_token_enc, refresh_token_enc, expires_value, user_id),
            )


def get_user_rides_dir(user_id: str) -> str | None:
    psycopg, rows = _get_psycopg_modules()
    query = """
        SELECT file_path
        FROM rides
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 100
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            rows_data = cur.fetchall()

    if not rows_data:
        return None

    parent_dirs: list[str] = []
    for row in rows_data:
        raw_path = str(row.get("file_path", "") or "").strip()
        if not raw_path:
            continue
        normalized = raw_path.replace("\\", "/")
        parent = normalized.rsplit("/", 1)[0] if "/" in normalized else ""
        if parent:
            parent_dirs.append(parent)

    if not parent_dirs:
        return None

    most_common = Counter(parent_dirs).most_common(1)
    return most_common[0][0] if most_common else None


def get_user_allowed_cyclists(user_id: str) -> list[str]:
    """Return cyclist folder names visible to the given user based on rides table."""
    psycopg, rows = _get_psycopg_modules()
    query = """
        SELECT file_path
        FROM rides
        WHERE user_id = %s
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            rows_data = cur.fetchall()

    cyclists: set[str] = set()
    for row in rows_data:
        raw_path = str(row.get("file_path", "") or "").strip()
        if not raw_path:
            continue
        normalized = raw_path.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        for i, part in enumerate(parts):
            if part == "rides" and i + 1 < len(parts):
                maybe_cyclist = parts[i + 1]
                if maybe_cyclist.startswith("cyclist"):
                    cyclists.add(maybe_cyclist)
                    break

    return sorted(cyclists)


def _get_user_default_cyclist(user_id: str) -> str:
    """Resolve a cyclist folder for a user from existing rides, fallback to cyclist1."""
    cyclists = get_user_allowed_cyclists(user_id)
    if cyclists:
        return cyclists[0]
    return "cyclist1"


def upsert_rides_from_strava_activities(
    *,
    user_id: str,
    strava_account_id: str,
    athlete_id: int,
    activities: list[dict[str, Any]],
) -> dict[str, int]:
    """Persist Strava activities into rides table.

    This stores metadata rows with deterministic file paths used by existing
    ride authorization logic.
    """
    if not activities:
        return {"saved_count": 0, "skipped_count": 0}

    psycopg, rows = _get_psycopg_modules()

    activity_ids: list[int] = []
    for activity in activities:
        raw_id = activity.get("id")
        if raw_id is None:
            continue
        try:
            activity_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not activity_ids:
        return {"saved_count": 0, "skipped_count": len(activities)}

    existing_query = """
            SELECT activity_id
            FROM rides
            WHERE user_id = %s
                AND activity_id = ANY(%s)
    """
    upsert_query = """
        INSERT INTO rides (
            user_id,
            strava_account_id,
            activity_id,
            start_date_local,
            sport_type,
            distance_m,
            moving_time_s,
            avg_hr,
            avg_watts,
            file_path
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, activity_id) DO UPDATE
        SET
            strava_account_id = EXCLUDED.strava_account_id,
            start_date_local = EXCLUDED.start_date_local,
            sport_type = EXCLUDED.sport_type,
            distance_m = EXCLUDED.distance_m,
            moving_time_s = EXCLUDED.moving_time_s,
            avg_hr = EXCLUDED.avg_hr,
            avg_watts = EXCLUDED.avg_watts,
            file_path = EXCLUDED.file_path
    """

    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(existing_query, (user_id, activity_ids))
            existing_rows = cur.fetchall()
            existing_ids = {
                int(row["activity_id"])
                for row in existing_rows
                if row.get("activity_id")
            }

            created_count = 0
            updated_count = 0
            for activity in activities:
                raw_id = activity.get("id")
                if raw_id is None:
                    continue
                try:
                    activity_id = int(raw_id)
                except (TypeError, ValueError):
                    continue

                start_date_local = activity.get("start_date")
                distance_m = activity.get("distance")
                moving_time_s = activity.get("moving_time")
                avg_hr = activity.get("average_heartrate")
                avg_watts = activity.get("average_watts")
                sport_type = activity.get("sport_type")

                file_path, _ = build_strava_activity_file_path(
                    user_id=user_id,
                    athlete_id=athlete_id,
                    activity=activity,
                )

                cur.execute(
                    upsert_query,
                    (
                        user_id,
                        strava_account_id,
                        activity_id,
                        start_date_local,
                        sport_type,
                        distance_m,
                        moving_time_s,
                        avg_hr,
                        avg_watts,
                        file_path,
                    ),
                )
                if activity_id in existing_ids:
                    updated_count += 1
                else:
                    created_count += 1

    skipped_count = 0
    return {
        "saved_count": created_count + updated_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
    }
