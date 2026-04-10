"""FastAPI backend for TFE Cycling analysis.

Exposes REST endpoints for running HR/power prediction models on cycling rides.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
import pandas as pd
from pydantic import BaseModel, Field

from app.services.notebook import (
    AnalysisConfig,
    run_notebook_analysis,
    extract_donnee_pickle,
    _resolve_data_path,
)


app = FastAPI(title="TFE Cycling API", version="0.1.0")


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


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint returning API status."""
    return {"message": "TFE Cycling backend is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/rides/list")
async def list_rides(
    dir_path: str = Query(..., description="Directory path (relative or absolute)")
) -> dict:
    """List available rides in a directory with basic info."""
    try:
        rides = extract_donnee_pickle(dir_path)
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
async def run_analysis(payload: AnalysisRequest) -> dict:
    """Execute analysis on rides using specified configuration."""
    try:
        config = AnalysisConfig(
            dir_path=payload.dir_path,
            selected_models_plot=payload.selected_models_plot,
            selected_models_stats=payload.selected_models_stats,
            show_rmse_table=payload.show_rmse_table,
            prev_ride=payload.prev_ride,
            nan_ratio=payload.nan_ratio,
            selected_train_ride=payload.selected_train_ride,
            selected_target_rides=payload.selected_target_rides,
        )
        return run_notebook_analysis(config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/pipeline/run")
async def run_pipeline(payload: PipelineRequest) -> dict:
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
        rides = extract_donnee_pickle(payload.dir_path)
        if not rides:
            raise ValueError(f"No valid rides found in {payload.dir_path}")

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
async def test_read_pkl(payload: PklReadRequest) -> dict:
    """Read a PKL file and return a minimal diagnostic payload (POST)."""
    return _read_pkl_diagnostic(payload.file_path)


@app.get("/pkl/test-read")
async def test_read_pkl_get(
    file_path: str = Query(..., description="Path to .pkl file")
) -> dict:
    """Read a PKL file and return a minimal diagnostic payload (GET)."""
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
