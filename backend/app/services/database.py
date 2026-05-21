"""PostgreSQL connectivity helpers for the backend."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import importlib
from .utils import _read_env

CYCLIST_PATTERN_PREFIX = "cyclist"


def get_all_rides() -> list[dict[str, Any]]:
    """Get all rides from the database."""
    psycopg, rows = _get_psycopg_modules()
    query = "SELECT id, user_id, activity_id, file_path FROM rides"
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


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
                    "verif_mail",
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


def _sorted_cyclists(cyclists: set[str]) -> list[str]:
    return sorted(
        cyclists,
        key=lambda x: (
            int(x.replace(CYCLIST_PATTERN_PREFIX, ""))
            if x.replace(CYCLIST_PATTERN_PREFIX, "").isdigit()
            else 10**9
        ),
    )


def _extract_cyclist_from_file_path_value(file_path: str) -> str | None:
    normalized = str(file_path or "").strip().replace("\\", "/")
    if not normalized:
        return None

    parts = [part for part in normalized.split("/") if part]
    for i, part in enumerate(parts):
        if part == "rides" and i + 1 < len(parts):
            maybe_cyclist = parts[i + 1]
            if maybe_cyclist.startswith(CYCLIST_PATTERN_PREFIX):
                return maybe_cyclist
    return None


def _ensure_user_cyclists_table(cur: Any) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_cyclists (
            user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            cyclist text NOT NULL UNIQUE,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (cyclist ~ '^cyclist[0-9]+$')
        )
        """)


def _get_mapped_cyclist_for_user(cur: Any, user_id: str) -> str | None:
    cur.execute("SELECT cyclist FROM user_cyclists WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    if not row:
        return None
    cyclist = row["cyclist"] if isinstance(row, dict) else row[0]
    return str(cyclist or "").strip()


def _legacy_cyclists_for_user(cur: Any, user_id: str) -> list[str]:
    cur.execute("SELECT file_path FROM rides WHERE user_id = %s", (user_id,))
    rows_data = cur.fetchall()
    cyclists: set[str] = set()
    for row in rows_data:
        raw = row[0] if isinstance(row, tuple) else row.get("file_path")
        cyclist = _extract_cyclist_from_file_path_value(str(raw or ""))
        if cyclist:
            cyclists.add(cyclist)
    return _sorted_cyclists(cyclists)


def _all_used_cyclists(cur: Any) -> set[str]:
    used: set[str] = set()

    cur.execute("SELECT cyclist FROM user_cyclists")
    for row in cur.fetchall():
        value = row[0] if isinstance(row, tuple) else row.get("cyclist")
        cyclist = str(value or "").strip()
        if cyclist:
            used.add(cyclist)

    cur.execute("SELECT file_path FROM rides")
    for row in cur.fetchall():
        value = row[0] if isinstance(row, tuple) else row.get("file_path")
        cyclist = _extract_cyclist_from_file_path_value(str(value or ""))
        if cyclist:
            used.add(cyclist)

    return used


def _insert_user_cyclist_mapping(cur: Any, user_id: str, cyclist: str) -> bool:
    cur.execute(
        """
        INSERT INTO user_cyclists (user_id, cyclist)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id, cyclist),
    )
    return cur.rowcount > 0


def get_or_assign_user_cyclist(user_id: str) -> str:
    """Return the user cyclist mapping, allocating a unique cyclist when missing."""
    psycopg, rows = _get_psycopg_modules()

    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            _ensure_user_cyclists_table(cur)

            mapped = _get_mapped_cyclist_for_user(cur, user_id)
            if mapped:
                return mapped

            legacy = _legacy_cyclists_for_user(cur, user_id)
            for cyclist in legacy:
                if _insert_user_cyclist_mapping(cur, user_id, cyclist):
                    return cyclist
                mapped = _get_mapped_cyclist_for_user(cur, user_id)
                if mapped:
                    return mapped

            used = _all_used_cyclists(cur)
            idx = 0
            while True:
                candidate = f"{CYCLIST_PATTERN_PREFIX}{idx}"
                if candidate not in used:
                    if _insert_user_cyclist_mapping(cur, user_id, candidate):
                        return candidate
                    mapped = _get_mapped_cyclist_for_user(cur, user_id)
                    if mapped:
                        return mapped
                    used = _all_used_cyclists(cur)
                idx += 1


def build_strava_activity_file_path(
    *,
    user_id: str,
    athlete_id: int,
    activity: dict[str, Any],
) -> tuple[str, Path]:
    """Build DB-stored filename and absolute PKL path for a Strava activity."""
    cyclist_folder = get_or_assign_user_cyclist(user_id)
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
    absolute_path = get_project_root() / "DB" / "rides" / cyclist_folder / file_name
    return file_name, absolute_path


def get_user_by_email(email: str) -> dict[str, Any] | None:
    psycopg, rows = _get_psycopg_modules()
    query = """
        SELECT id, email, display_name, password_hash, role, email_verified_at, created_at
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
        SELECT id, email, display_name, password_hash, role, email_verified_at, created_at
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
    email_verified_at: datetime | None = None,
) -> dict[str, Any] | None:
    """Create a new user with email, password hash, and optional display name."""
    psycopg, rows = _get_psycopg_modules()

    # Check if user already exists
    existing = get_user_by_email(email.strip().lower())
    if existing:
        return None

    query = """
        INSERT INTO users (email, password_hash, display_name, role, email_verified_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, email, display_name, password_hash, role, email_verified_at, created_at
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    email.strip().lower(),
                    password_hash,
                    display_name,
                    role,
                    email_verified_at,
                ),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_email_verification_request(
    *,
    user_id: str,
    email: str,
    code_hash: str,
    expires_at: datetime,
    attempts_left: int = 2,
) -> dict[str, Any]:
    psycopg, rows = _get_psycopg_modules()
    query = """
        INSERT INTO verif_mail (
            user_id,
            email,
            code_hash,
            attempts_left,
            expires_at,
            sent_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, now(), now())
        ON CONFLICT (user_id) DO UPDATE SET
            email = EXCLUDED.email,
            code_hash = EXCLUDED.code_hash,
            attempts_left = EXCLUDED.attempts_left,
            expires_at = EXCLUDED.expires_at,
            sent_at = now(),
            verified_at = NULL,
            updated_at = now()
        RETURNING id, user_id, email, code_hash, attempts_left, expires_at, sent_at, verified_at, created_at, updated_at
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    user_id,
                    email.strip().lower(),
                    code_hash,
                    int(attempts_left),
                    expires_at,
                ),
            )
            row = cur.fetchone()
            return dict(row) if row else {}


def get_email_verification_request(user_id: str) -> dict[str, Any] | None:
    psycopg, rows = _get_psycopg_modules()
    query = """
        SELECT id, user_id, email, code_hash, attempts_left, expires_at, sent_at, verified_at, created_at, updated_at
        FROM verif_mail
        WHERE user_id = %s
        LIMIT 1
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def decrement_email_verification_attempt(user_id: str) -> dict[str, Any] | None:
    psycopg, rows = _get_psycopg_modules()
    query = """
        UPDATE verif_mail
        SET attempts_left = GREATEST(attempts_left - 1, 0),
            updated_at = now()
        WHERE user_id = %s
          AND attempts_left > 0
        RETURNING id, user_id, email, code_hash, attempts_left, expires_at, sent_at, verified_at, created_at, updated_at
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def mark_user_email_verified(user_id: str) -> None:
    psycopg, _rows = _get_psycopg_modules()
    with psycopg.connect(get_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET email_verified_at = COALESCE(email_verified_at, now()) WHERE id = %s",
                (user_id,),
            )
            cur.execute("DELETE FROM verif_mail WHERE user_id = %s", (user_id,))
        conn.commit()


def delete_user_by_id(user_id: str) -> None:
    psycopg, _rows = _get_psycopg_modules()
    with psycopg.connect(get_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()


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
        SELECT id, user_id, athlete_id, access_token_enc, refresh_token_enc, expires_at, scope, created_at, updated_at
        FROM strava_accounts
        WHERE user_id = %s
        LIMIT 1
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def delete_strava_account_for_user(user_id: str) -> int:
    """Delete Strava account row for a user and return number of deleted rows."""
    psycopg, _ = _get_psycopg_modules()
    query = "DELETE FROM strava_accounts WHERE user_id = %s"
    with psycopg.connect(get_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            return int(cur.rowcount or 0)


def get_stale_strava_accounts(
    *, updated_before: datetime, limit: int = 200
) -> list[dict[str, Any]]:
    """Return stale Strava account rows based on updated_at threshold."""
    psycopg, rows = _get_psycopg_modules()
    query = """
        SELECT id, user_id, athlete_id, access_token_enc, refresh_token_enc, expires_at, updated_at
        FROM strava_accounts
        WHERE updated_at < %s
        ORDER BY updated_at ASC
        LIMIT %s
    """
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (updated_before, int(limit)))
            return [dict(row) for row in cur.fetchall()]


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
    cyclist = get_or_assign_user_cyclist(user_id)
    return f"DB/rides/{cyclist}"


def _extract_cyclists_from_paths(rows_data: list[dict[str, Any]]) -> list[str]:
    cyclists: set[str] = set()
    for row in rows_data:
        raw_path = str(row.get("file_path", "") or "").strip()
        cyclist = _extract_cyclist_from_file_path_value(raw_path)
        if cyclist:
            cyclists.add(cyclist)

    return _sorted_cyclists(cyclists)


def get_all_cyclists_from_rides() -> list[str]:
    """Return all cyclist folder names from explicit mapping and legacy ride paths."""
    psycopg, rows = _get_psycopg_modules()
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            _ensure_user_cyclists_table(cur)

            cyclists: set[str] = set()

            cur.execute("SELECT cyclist FROM user_cyclists")
            for row in cur.fetchall():
                cyclist = str(row.get("cyclist", "") or "").strip()
                if cyclist:
                    cyclists.add(cyclist)

            cur.execute("SELECT file_path FROM rides")
            rows_data = cur.fetchall()
            cyclists.update(_extract_cyclists_from_paths(rows_data))

    return _sorted_cyclists(cyclists)


def get_admin_cyclist_options() -> list[dict[str, str]]:
    """Return admin-facing cyclist options with display labels when available."""
    psycopg, rows = _get_psycopg_modules()
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            _ensure_user_cyclists_table(cur)

            used_cyclists = _all_used_cyclists(cur)
            display_names: dict[str, str] = {}

            cur.execute("""
                SELECT uc.cyclist, u.display_name
                FROM user_cyclists uc
                LEFT JOIN users u ON u.id = uc.user_id
                """)
            for row in cur.fetchall():
                cyclist = str(row.get("cyclist", "") or "").strip()
                if not cyclist:
                    continue
                display_name = str(row.get("display_name", "") or "").strip()
                display_names[cyclist] = display_name

    return [
        {
            "value": cyclist,
            "label": display_names.get(cyclist) or cyclist,
        }
        for cyclist in _sorted_cyclists(used_cyclists)
    ]


def get_user_allowed_cyclists(user_id: str) -> list[str]:
    """Return cyclist folder names visible to the user.

    Uses explicit user_cyclists mapping when available, with legacy ride-path fallback.
    """
    psycopg, rows = _get_psycopg_modules()
    with psycopg.connect(get_database_url(), row_factory=rows.dict_row) as conn:
        with conn.cursor() as cur:
            _ensure_user_cyclists_table(cur)

            mapped = _get_mapped_cyclist_for_user(cur, user_id)
            if mapped:
                return [mapped]

            legacy = _legacy_cyclists_for_user(cur, user_id)
            return legacy


def _get_user_default_cyclist(user_id: str) -> str:
    """Resolve a unique cyclist folder for a user, allocating one when needed."""
    return get_or_assign_user_cyclist(user_id)


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
