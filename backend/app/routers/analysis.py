"""Analysis and prediction routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import logging

import app.services.auth as auth_service
import app.services.notebook as notebook_service
from app.services.authorization import resolve_authorized_cyclist_and_dir

logger = logging.getLogger(__name__)

router = APIRouter()


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


class CompareModelsRequest(BaseModel):
    """Request to compare two models trained on different rides."""

    dir_path: str = Field(..., description="Directory containing PKL rides")
    train_ride_index_1: int = Field(
        ..., ge=1, description="1-based index for model 1 training ride"
    )
    train_ride_index_2: int = Field(
        ..., ge=1, description="1-based index for model 2 training ride"
    )
    test_ride_index: int = Field(..., ge=1, description="1-based index for test ride")
    apply_to_all_rides: bool = Field(
        default=False, description="Apply both models to all rides and compute diffs"
    )


@router.post("/pipeline/run")
async def run_pipeline(
    payload: PipelineRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Execute full pipeline and return rides with predictions."""
    try:
        _, effective_dir = resolve_authorized_cyclist_and_dir(
            current_user, payload.dir_path
        )

        config = notebook_service.PipelineConfig(
            dir_path=effective_dir,
            selected_models_compute=payload.selected_models_compute,
            prev_ride=payload.prev_ride,
            nan_ratio=payload.nan_ratio,
            selected_train_ride=payload.selected_train_ride,
            selected_target_rides=payload.selected_target_rides,
        )
        return notebook_service.run_pipeline(config)
    except Exception as exc:
        logger.exception("Pipeline run failed")
        raise HTTPException(
            status_code=400,
            detail="Pipeline failed.",
        ) from exc


@router.post("/pipeline/compare-models-trained")
async def compare_models_trained(
    payload: CompareModelsRequest,
    current_user: dict = Depends(auth_service.get_current_user),
) -> dict:
    """Compare two models trained on different rides, tested on a third ride."""
    try:
        _, effective_dir = resolve_authorized_cyclist_and_dir(
            current_user, payload.dir_path
        )

        config = notebook_service.CompareModelsConfig(
            dir_path=effective_dir,
            train_ride_index_1=payload.train_ride_index_1,
            train_ride_index_2=payload.train_ride_index_2,
            test_ride_index=payload.test_ride_index,
            apply_to_all_rides=payload.apply_to_all_rides,
        )
        return notebook_service.compare_models_trained(config)
    except Exception as exc:
        logger.exception("Model comparison failed")
        raise HTTPException(
            status_code=400, detail=f"Model comparison failed: {str(exc)}"
        ) from exc
