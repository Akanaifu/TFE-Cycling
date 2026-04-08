"""FastAPI backend for TFE Cycling analysis.

Exposes REST endpoints for running HR/power prediction models on cycling rides.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.services.notebook_migration import AnalysisConfig, run_notebook_analysis


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


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint returning API status."""
    return {"message": "TFE Cycling backend is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


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
