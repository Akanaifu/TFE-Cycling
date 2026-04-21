"""FastAPI backend for TFE Cycling analysis.

Exposes REST endpoints for running HR/power prediction models on cycling rides.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pydantic import BaseModel, Field
import app.services.auth as auth_service
import app.services.database as database_service
import app.services.notebook as notebook_service
from app.services.security import decrypt_secret_fernet, encrypt_secret_fernet
from contextlib import asynccontextmanager
import app.services.strava as strava_service
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Backend starting up...")

    yield

    # Shutdown
    print("Backend shutting down...")


app = FastAPI(title="TFE Cycling API", version="0.1.0", lifespan=lifespan)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tfe-cycling.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    """Request payload for analysis endpoint."""

    dir_path: str = Field(..., description="Directory containing PKL rides")
    selected_models_plot: list[str] = Field(
        default_factory=lambda: ["pred_arx_selected"]
    )
    selected_models_stats: list[str] = Field(
        default_factory=lambda: ["pred_arx_selected"]
    )
    show_rmse_table: bool = True
    prev_ride: int = 1
    nan_ratio: float = 1.0
    selected_train_ride: int = 1
    selected_target_rides: int | list[int] | None = None


class PklReadRequest(BaseModel):
    """Request payload for pickle readability test endpoint."""

    file_path: str = Field(..., description="Absolute or relative path to a .pkl file")


class PipelineRequest(BaseModel):
    """Request to run full pipeline with predictions and metadata."""

    dir_path: str = Field(..., description="Directory containing PKL rides")
    selected_models_compute: list[str] = Field(
        default_factory=lambda: ["pred_arx_selected"],
        description="Models to compute and return",
    )
    prev_ride: int = Field(default=1)
    nan_ratio: float = Field(default=1.0)
    selected_train_ride: int = Field(default=1)
    selected_target_rides: int | list[int] | None = Field(default=None)


class StravaExchangeCodeRequest(BaseModel):
    """Request payload to exchange Strava OAuth code."""

    code: str = Field(..., min_length=1, description="Strava OAuth code")


class AuthLoginRequest(BaseModel):
    """Request payload for JWT login endpoint."""

    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class AuthRegisterRequest(BaseModel):
    """Request payload for user registration endpoint."""

    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    display_name: str = Field(default="")


def _is_admin(user: dict) -> bool:
    return str(user.get("role", "")).strip().lower() == "admin"


def _extract_cyclist_from_dir_path(dir_path: str) -> str | None:
    normalized = (dir_path or "").replace("\\", "/")
    match = re.search(r"(cyclist\d+)", normalized)
    return match.group(1) if match else None


@app.get("/api")
async def root() -> dict[str, str]:
    """Root endpoint returning API status."""
    return {"message": "TFE Cycling backend is running"}


@app.get("/health")
async def health() -> dict:
    """Health check endpoint with DB connectivity status."""
    db_state = database_service.get_database_status()
    return {
        "status": "ok",
        "database": {
            "connected": db_state.get("connected", False),
        },
    }


@app.get("/db/status")
async def db_status(
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Detailed DB status for troubleshooting backend/database linkage."""
    _ = current_user
    db_state = database_service.get_database_status()
    if not db_state.get("connected"):
        raise HTTPException(status_code=503, detail=db_state)
    return {"ok": True, "db": db_state}


@app.post("/auth/login")
async def auth_login(payload: AuthLoginRequest) -> dict:
    """Authenticate a user and return a JWT access token."""
    user = auth_service.authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = auth_service.create_access_token(
        user_id=str(user["id"]),
        email=str(user["email"]),
        role=str(user.get("role", "user")),
    )
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user["id"]),
            "email": str(user["email"]),
            "display_name": user.get("display_name"),
            "role": user.get("role", "user"),
        },
    }


@app.post("/auth/register")
async def auth_register(payload: AuthRegisterRequest) -> dict:
    """Register a new user account."""
    email = payload.email.strip().lower()

    # Check if email already exists
    existing = database_service.get_user_by_email(email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Hash password
    try:
        password_hash = auth_service.hash_password(payload.password)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password hashing failed: {exc}",
        ) from exc

    # Create user
    user = database_service.create_user(
        email=email,
        password_hash=password_hash,
        display_name=payload.display_name.strip(),
        role="user",
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )

    # Return token for immediate login
    token = auth_service.create_access_token(
        user_id=str(user["id"]),
        email=str(user["email"]),
        role=str(user.get("role", "user")),
    )

    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user["id"]),
            "email": str(user["email"]),
            "display_name": user.get("display_name"),
            "role": user.get("role", "user"),
        },
    }


@app.get("/auth/me")
async def auth_me(current_user: dict = Depends(auth_service.get_current_user)) -> dict:
    """Return current authenticated user from JWT."""
    return {
        "ok": True,
        "user": {
            "id": str(current_user["id"]),
            "email": str(current_user["email"]),
            "display_name": current_user.get("display_name"),
            "role": current_user.get("role", "user"),
        },
    }


@app.get("/strava/status")
async def strava_status(
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Expose Strava env readiness and user-level Strava account status."""
    base_status = strava_service.get_strava_status()
    account = database_service.get_strava_account_for_user(str(current_user["id"]))

    athlete_id = account.get("athlete_id") if account else None
    expires_at = account.get("expires_at") if account else None
    has_db_tokens = bool(account and account.get("access_token_enc"))

    return {
        "ok": True,
        "status": {
            **base_status,
            "connected": has_db_tokens,
            "athlete_id": athlete_id,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    }


@app.get("/strava/auth-url")
async def strava_auth_url(
    state: str | None = Query(None),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Build Strava OAuth authorization URL from env settings."""
    _ = current_user
    try:
        url = strava_service.build_authorization_url(state=state)
        return {"ok": True, "auth_url": url}
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Unable to build Strava auth URL: {exc}"
        ) from exc


@app.post("/strava/exchange-code")
async def strava_exchange_code(
    payload: StravaExchangeCodeRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Exchange OAuth code and persist encrypted tokens in PostgreSQL."""
    try:
        raw_payload = strava_service.exchange_code_for_tokens_payload(payload.code)
        encrypted = strava_service.build_encrypted_tokens_payload(raw_payload)

        athlete = raw_payload.get("athlete") if isinstance(raw_payload, dict) else None
        athlete_id = athlete.get("id") if isinstance(athlete, dict) else None
        if athlete_id is None:
            raise ValueError("Token payload missing athlete.id")

        settings = strava_service.get_strava_settings()
        scope = str(raw_payload.get("scope") or settings.get("scopes") or "")

        database_service.upsert_strava_account_for_user(
            user_id=str(current_user["id"]),
            athlete_id=int(athlete_id),
            access_token_enc=str(encrypted["access_token_enc"]),
            refresh_token_enc=str(encrypted["refresh_token_enc"]),
            expires_at=(
                int(raw_payload.get("expires_at"))
                if raw_payload.get("expires_at") is not None
                else None
            ),
            scope=scope,
        )

        return {
            "ok": True,
            "result": {
                "saved": True,
                "storage": "database",
                "token_type": raw_payload.get("token_type", "Bearer"),
                "expires_at": raw_payload.get("expires_at"),
                "athlete_id": athlete_id,
            },
        }
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Unable to exchange Strava code: {exc}"
        ) from exc


@app.get("/strava/activities")
async def strava_get_activities(
    limit: int = Query(10, ge=1, le=100, description="Number of activities to fetch"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Fetch recent athlete activities from Strava API.

    Requires valid tokens persisted in PostgreSQL from exchange-code endpoint.
    Token refresh happens automatically if expired.
    """
    try:
        settings = strava_service.get_strava_settings()
        account = database_service.get_strava_account_for_user(str(current_user["id"]))
        if not account:
            raise ValueError("No Strava account connected for current user")

        tokens = {
            "access_token": decrypt_secret_fernet(str(account["access_token_enc"])),
            "refresh_token": decrypt_secret_fernet(str(account["refresh_token_enc"])),
            "expires_at": (
                int(account["expires_at"].replace(tzinfo=timezone.utc).timestamp())
                if isinstance(account.get("expires_at"), datetime)
                else None
            ),
            "athlete": {"id": account.get("athlete_id")},
        }

        # Check and refresh if needed
        if strava_service.is_token_expired(tokens):
            new_tokens = strava_service.refresh_tokens(
                settings["client_id"],
                settings["client_secret"],
                tokens.get("refresh_token", ""),
            )
            # Preserve athlete data and update encrypted DB tokens
            new_tokens["athlete"] = tokens.get("athlete", {})

            database_service.update_strava_account_tokens(
                user_id=str(current_user["id"]),
                access_token_enc=encrypt_secret_fernet(
                    str(new_tokens.get("access_token", ""))
                ),
                refresh_token_enc=encrypt_secret_fernet(
                    str(new_tokens.get("refresh_token", ""))
                ),
                expires_at=(
                    int(new_tokens.get("expires_at"))
                    if new_tokens.get("expires_at") is not None
                    else None
                ),
            )
            tokens = new_tokens

        access_token = tokens.get("access_token")
        if not access_token:
            raise ValueError("No access token in persisted tokens")

        activities = strava_service.get_athlete_activities(
            access_token=access_token, limit=limit
        )

        persisted_activities: list[dict[str, object]] = []
        failed_activities = 0
        athlete_id = int(account.get("athlete_id") or 0)
        if athlete_id <= 0:
            raise ValueError("No athlete_id available for current Strava account")

        for activity in activities:
            try:
                activity_id = int(activity.get("id") or 0)
                if activity_id <= 0:
                    raise ValueError("Missing activity id")

                relative_path, absolute_path = (
                    database_service.build_strava_activity_file_path(
                        user_id=str(current_user["id"]),
                        athlete_id=athlete_id,
                        activity=activity,
                    )
                )

                streams = strava_service.get_activity_streams(
                    access_token=access_token,
                    activity_id=activity_id,
                )
                ride_df = strava_service.build_activity_dataframe(
                    activity=activity,
                    streams=streams,
                )

                absolute_path.parent.mkdir(parents=True, exist_ok=True)
                ride_df.to_pickle(absolute_path)

                activity_with_path = dict(activity)
                activity_with_path["file_path"] = relative_path
                persisted_activities.append(activity_with_path)
            except Exception:
                failed_activities += 1

        if not persisted_activities:
            raise ValueError("Unable to persist any Strava activities")

        persistence = database_service.upsert_rides_from_strava_activities(
            user_id=str(current_user["id"]),
            strava_account_id=str(account["id"]),
            athlete_id=athlete_id,
            activities=persisted_activities,
        )

        return {
            "ok": True,
            "n_activities": len(activities),
            "activities": activities,
            "written_count": len(persisted_activities),
            "saved_count": int(persistence.get("saved_count", 0)),
            "created_count": int(persistence.get("created_count", 0)),
            "updated_count": int(persistence.get("updated_count", 0)),
            "skipped_count": int(persistence.get("skipped_count", 0)),
            "failed_count": failed_activities,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Unable to fetch Strava activities: {exc}"
        ) from exc


@app.get("/cyclists/list")
async def get_cyclists_list(
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """List all available cyclists."""
    try:
        if _is_admin(current_user):
            cyclists = notebook_service.list_cyclists()
        else:
            cyclists = database_service.get_user_allowed_cyclists(
                str(current_user["id"])
            )
        return {
            "ok": True,
            "cyclists": cyclists,
            "n_cyclists": len(cyclists),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to list cyclists: {exc}"
        ) from exc


@app.get("/rides/training-ride")
async def get_training_ride(
    cyclist: str = Query(..., description="Cyclist name (e.g., cyclist9)"),
    ride_index: int = Query(1, description="Ride index (1-based)"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Get a single training ride data."""
    try:
        if not _is_admin(current_user):
            allowed = set(
                database_service.get_user_allowed_cyclists(str(current_user["id"]))
            )
            if cyclist not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied for this cyclist",
                )

        get_single_ride_fn = getattr(notebook_service, "get_single_ride")
        return get_single_ride_fn(cyclist, ride_index)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to get ride: {exc}"
        ) from exc


@app.get("/rides/list")
async def list_rides(
    dir_path: str = Query(..., description="Directory path (relative or absolute)"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """List available rides in a directory with basic info."""
    try:
        if not _is_admin(current_user):
            requested_cyclist = _extract_cyclist_from_dir_path(dir_path)
            allowed = set(
                database_service.get_user_allowed_cyclists(str(current_user["id"]))
            )
            if requested_cyclist is None or requested_cyclist not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied for requested rides directory",
                )

        rides = notebook_service.extract_donnee_pickle(dir_path)
        ride_list = []
        for i, ride in enumerate(rides, start=1):
            datetime_label = ride.attrs.get("ride_datetime_label", "unknown")
            ride_list.append(
                {
                    "index": i,
                    "datetime": datetime_label,
                    "points": int(ride.shape[0]),
                    "columns": [str(c) for c in ride.columns.tolist()],
                }
            )
        return {
            "ok": True,
            "dir_path": str(dir_path),
            "n_rides": len(rides),
            "rides": ride_list,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to list rides: {exc}"
        ) from exc


@app.post("/analysis/run")
async def run_analysis(
    payload: AnalysisRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Execute analysis on rides using specified configuration."""
    _ = current_user
    try:
        config = notebook_service.AnalysisConfig(
            dir_path=payload.dir_path,
            selected_models_plot=payload.selected_models_plot,
            selected_models_stats=payload.selected_models_stats,
            show_rmse_table=payload.show_rmse_table,
            prev_ride=payload.prev_ride,
            nan_ratio=payload.nan_ratio,
            selected_train_ride=payload.selected_train_ride,
            selected_target_rides=payload.selected_target_rides,
        )
        return notebook_service.run_notebook_analysis(config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/pipeline/run")
async def run_pipeline(
    payload: PipelineRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Execute full pipeline and return rides with predictions.

    Returns:
        dict with:
            - ok: bool
            - n_rides: number of rides in result
            - models_requested: list of models requested
            - models_computed: list of models actually computed
            - rides: list of rides with columns including predictions
                   Each ride includes: t, hr, po, t_min, work, work2, work3, work4, po_lag_*,
                   ride_datetime, and prediction columns
    """
    try:
        effective_dir = payload.dir_path
        if not _is_admin(current_user):
            requested_cyclist = _extract_cyclist_from_dir_path(payload.dir_path)
            allowed = set(
                database_service.get_user_allowed_cyclists(str(current_user["id"]))
            )
            if requested_cyclist is None or requested_cyclist not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied for requested pipeline directory",
                )

        rides = notebook_service.extract_donnee_pickle(effective_dir)
        if not rides:
            raise ValueError(f"No valid rides found in {effective_dir}")

        selected_models_compute = payload.selected_models_compute
        predictions: dict[str, list[pd.DataFrame]] = {}

        # Import prediction functions
        from app.services.notebook import (
            prediction_with_prev_rides,
            prediction,
            prediction_arx_with_prev_rides_no_fuite,
            prediction_arx_from_selected_ride,
        )

        # Compute requested models
        if "pred_hist" in selected_models_compute:
            predictions["pred_hist"] = prediction_with_prev_rides(
                [r.copy(deep=True) for r in rides],
                x_prev_rides=payload.prev_ride,
                max_nan_ratio=payload.nan_ratio,
            )

        if "pred_default" in selected_models_compute:
            predictions["pred_default"] = prediction([r.copy(deep=True) for r in rides])

        if "pred_no_fuite" in selected_models_compute:
            predictions["pred_no_fuite"] = prediction_arx_with_prev_rides_no_fuite(
                [r.copy(deep=True) for r in rides],
                x_prev_rides=payload.prev_ride,
                max_nan_ratio=payload.nan_ratio,
                init_window=5,
                n_hr_lags=1,
                ridge_alpha=5,
                po_lag_start=5,
            )

        if "pred_arx_selected" in selected_models_compute:
            predictions["pred_arx_selected"] = prediction_arx_from_selected_ride(
                [r.copy(deep=True) for r in rides],
                train_ride_index=payload.selected_train_ride,
                target_ride_indices=payload.selected_target_rides,
                n_hr_lags=1,
                ridge_alpha=5,
                po_lag_start=5,
                pred_col="arx_pred_selected",
                max_nan_ratio=payload.nan_ratio,
                init_window=5,
                one_based_index=True,
            )

        # Model specifications
        model_specs = {
            "pred_hist": {"col": "pred_prevx", "label": "pred_hist"},
            "pred_default": {"col": "pred1", "label": "pred_default"},
            "pred_no_fuite": {"col": "arx_pred", "label": "pred_no_fuite"},
            "pred_arx_selected": {
                "col": "arx_pred_selected",
                "label": "pred_arx_selected",
            },
        }

        # Check for unknown or missing models
        unknown = [m for m in selected_models_compute if m not in model_specs]
        if unknown:
            raise ValueError(f"Unknown models: {unknown}")

        missing = [m for m in selected_models_compute if m not in predictions]
        if missing:
            raise ValueError(f"Models not computed: {missing}")

        # Build combined rides with predictions
        rides_combined = []
        for i, ride in enumerate(rides):
            base = ride.copy()
            if "t_min" not in base.columns and "t" in base.columns:
                base["t_min"] = base["t"] / 60.0

            for model_key in selected_models_compute:
                spec = model_specs[model_key]
                src_ride = predictions[model_key][i]
                base[model_key] = src_ride[spec["col"]]

            rides_combined.append(base)

        # Convert rides to serializable format
        rides_serialized = []
        for ride in rides_combined:
            ride_dict = {
                "datetime": ride.attrs.get("ride_datetime_label", "unknown"),
                "n_points": int(ride.shape[0]),
                "columns": [str(c) for c in ride.columns.tolist()],
                "data": ride.to_dict(orient="records"),
            }
            rides_serialized.append(ride_dict)

        return {
            "ok": True,
            "n_rides": len(rides_combined),
            "models_requested": selected_models_compute,
            "models_computed": list(predictions.keys()),
            "rides": rides_serialized,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Pipeline failed: {str(exc)}"
        ) from exc


@app.post("/pkl/test-read")
async def test_read_pkl(
    payload: PklReadRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Read a PKL file and return a minimal diagnostic payload (POST)."""
    _ = current_user
    return _read_pkl_diagnostic(payload.file_path)


@app.get("/pkl/test-read")
async def test_read_pkl_get(
    file_path: str = Query(..., description="Path to .pkl file"),
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Read a PKL file and return a minimal diagnostic payload (GET)."""
    _ = current_user
    return _read_pkl_diagnostic(file_path)


def _read_pkl_diagnostic(file_path: str) -> dict:
    """Shared PKL readability check used by GET and POST endpoints."""
    try:
        pkl_path = Path(file_path).expanduser()
        if not pkl_path.is_absolute():
            pkl_path = Path.cwd() / pkl_path
        pkl_path = pkl_path.resolve()

        if not pkl_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {pkl_path}")

        if pkl_path.suffix.lower() != ".pkl":
            raise HTTPException(status_code=400, detail="Provided file is not a .pkl")

        data = pd.read_pickle(pkl_path)

        if isinstance(data, pd.DataFrame):
            return {
                "ok": True,
                "file_path": str(pkl_path),
                "type": "DataFrame",
                "rows": int(data.shape[0]),
                "columns": [str(c) for c in data.columns.tolist()],
            }

        return {
            "ok": True,
            "file_path": str(pkl_path),
            "type": type(data).__name__,
            "repr": repr(data)[:300],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PKL read failed: {exc}") from exc


# ── Serve React SPA ───────────────────────────────────────────────────────────
_PUBLIC = Path(__file__).parent / "public"
_INDEX = _PUBLIC / "index.html"

if _PUBLIC.exists() and _INDEX.exists():
    app.mount("/", StaticFiles(directory=str(_PUBLIC), html=True), name="spa")
