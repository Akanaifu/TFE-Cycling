"""Core analysis and prediction models for TFE cycling analysis.

Provides feature engineering, linear regression, and ARX-based HR prediction models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
from pathlib import Path
from typing import Any
import os
import warnings

import numpy as np
import pandas as pd


def _is_truthy_env(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_pickle_signing_secret() -> str:
    return str(os.getenv("PKL_SIGNING_SECRET", "")).strip()


def _allow_unsigned_pickles() -> bool:
    raw = os.getenv("PKL_ALLOW_UNSIGNED_PICKLES", "true")
    return _is_truthy_env(str(raw))


def _max_pickle_size_bytes() -> int:
    raw = str(os.getenv("PKL_MAX_BYTES", "52428800")).strip()
    try:
        value = int(raw)
    except ValueError:
        return 52_428_800
    return max(1_048_576, value)


def _pickle_signature_path(file_path: Path) -> Path:
    return file_path.with_name(f"{file_path.name}.sig")


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compute_pickle_signature(file_path: Path, secret: str) -> str:
    file_hash = _sha256_file(file_path)
    return hmac.new(
        secret.encode("utf-8"), file_hash.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def write_pickle_secure(df: pd.DataFrame, file_path: str | os.PathLike) -> None:
    """Write pickle and optional detached signature sidecar when secret is set."""
    target = Path(file_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(target)

    secret = _get_pickle_signing_secret()
    if not secret:
        return

    sig_path = _pickle_signature_path(target)
    signature = _compute_pickle_signature(target, secret)
    sig_path.write_text(f"v1:{signature}\n", encoding="utf-8")


def load_pickle_secure(file_path: str | os.PathLike) -> Any:
    """Load pickle with hardening checks (size, symlink, optional signature)."""
    target = Path(file_path)

    if target.is_symlink():
        raise RuntimeError(f"Refusing to read symlinked pickle: {target}")

    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"Pickle not found: {target}")

    if target.suffix.lower() != ".pkl":
        raise RuntimeError(f"Unsupported pickle extension: {target.suffix}")

    max_size = _max_pickle_size_bytes()
    size_bytes = target.stat().st_size
    if size_bytes > max_size:
        raise RuntimeError(
            f"Pickle too large ({size_bytes} bytes), limit is {max_size} bytes"
        )

    secret = _get_pickle_signing_secret()
    sig_path = _pickle_signature_path(target)
    has_signature = sig_path.exists() and sig_path.is_file()

    if secret:
        if not has_signature:
            raise RuntimeError(f"Missing signature for pickle: {target.name}")
        raw = sig_path.read_text(encoding="utf-8").strip()
        if not raw.startswith("v1:"):
            raise RuntimeError(f"Invalid signature format for pickle: {target.name}")
        expected = raw.split(":", 1)[1].strip()
        actual = _compute_pickle_signature(target, secret)
        if not hmac.compare_digest(expected, actual):
            raise RuntimeError(f"Signature mismatch for pickle: {target.name}")
    elif not _allow_unsigned_pickles() and not has_signature:
        raise RuntimeError(
            "Unsigned pickle blocked. Set PKL_ALLOW_UNSIGNED_PICKLES=true for migration."
        )

    return pd.read_pickle(target)


def _warn_and_is_invalid_hr_po(ride: pd.DataFrame, ride_idx: int, context: str) -> bool:
    """Warn and return True when ride misses hr/po or contains only NaN values."""
    issues: list[str] = []
    col_miss = ("po", "hr") if context.find("prediction") == -1 else ("hr")
    for col in col_miss:
        if col not in ride.columns:
            issues.append(f"missing '{col}' column")
            continue
        values = pd.to_numeric(ride[col], errors="coerce")
        if int(values.notna().sum()) == 0:
            issues.append(f"'{col}' column is empty (100% NaN)")

    if issues:
        msg = f"[{context}] ride {ride_idx}: {'; '.join(issues)}. Ride skipped."
        warnings.warn(msg, UserWarning)
        return True
    return False


def ajouter_colonnes_decalees(
    df: pd.DataFrame, target_col: str, n_lags: int
) -> pd.DataFrame:
    """Add lagged columns for time-series features."""
    df_result = df.copy()
    new_columns = {}
    for i in range(1, n_lags + 1):
        col_name = f"{target_col}_lag_{i}"
        new_columns[col_name] = df[target_col].shift(i, fill_value=0)
    df_new_cols = pd.DataFrame(new_columns, index=df.index)
    return pd.concat([df_result, df_new_cols], axis=1)


def add_features(ride: pd.DataFrame) -> pd.DataFrame:
    """Enrich ride with computed features (t_min, work, power lags)."""
    ride = ride.copy()
    ride["t"] = pd.to_numeric(ride["t"], errors="coerce")
    ride["hr"] = pd.to_numeric(ride["hr"], errors="coerce")
    ride["po"] = pd.to_numeric(ride["po"], errors="coerce").fillna(0.0)
    ride["t_min"] = ride["t"] / 60.0
    ride["work"] = ride["po"].cumsum()
    ride["work2"] = ride["work"] ** 2
    ride["work3"] = ride["work"] ** 3
    ride["work4"] = ride["work"] ** 4
    return ajouter_colonnes_decalees(ride, "po", 600)


def add_features_to_rides(rides: list[pd.DataFrame]) -> list[pd.DataFrame]:
    """Apply feature enrichment to multiple rides."""
    rides_features: list[pd.DataFrame] = []
    for idx, ride in enumerate(rides, start=1):
        if not isinstance(ride, pd.DataFrame):
            raise TypeError(
                f"ride {idx}: unsupported type ({type(ride).__name__}), expected pd.DataFrame"
            )
        if _warn_and_is_invalid_hr_po(ride, idx, "Preparation"):
            continue
        rides_features.append(add_features(ride))
    return rides_features


def list_files(directory: str | os.PathLike) -> list[str]:
    """List files in directory with error handling."""
    try:
        return os.listdir(directory)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Directory not found: {directory}") from exc
    except PermissionError as exc:
        raise PermissionError(f"Access denied to directory: {directory}") from exc


def parse_datetime_from_ride_filename(filename: str) -> datetime:
    """Extract datetime from ride filename."""
    name = Path(filename).name
    stem = Path(name).stem
    if stem.endswith(".pkl"):
        stem = Path(stem).stem
    date_part, time_part = stem.split("T", 1)
    hms = time_part.split(".", 1)[0].replace("_", ":")
    return datetime.strptime(f"{date_part} {hms}", "%Y-%m-%d %H:%M:%S")


def format_datetime_for_title(dt: datetime) -> str:
    """Format datetime for display in titles."""
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def _resolve_data_path(dir_path: str | os.PathLike) -> Path:
    """Resolve relative paths from backend directory."""
    p = Path(dir_path)
    if p.is_absolute():
        return p
    # Resolve relative to backend directory
    backend_dir = Path(__file__).parent.parent.parent
    resolved = (backend_dir / p).resolve()
    return resolved


def list_cyclists() -> list[str]:
    """List all available cyclists from notebook/rides/ directory.

    Returns:
        List of cyclist names sorted numerically (cyclist0, cyclist1, etc.)
    """
    rides_dir = _resolve_data_path("../DB/rides")
    if not rides_dir.exists():
        raise FileNotFoundError(f"Rides directory not found: {rides_dir}")

    cyclists = []
    try:
        for entry in rides_dir.iterdir():
            if entry.is_dir() and entry.name.startswith("cyclist"):
                cyclists.append(entry.name)
    except Exception as exc:
        raise RuntimeError(f"Failed to list cyclists: {exc}") from exc

    # Sort numerically: cyclist0, cyclist1, ...
    cyclists.sort(
        key=lambda x: (
            int(x.replace("cyclist", "")) if x.replace("cyclist", "").isdigit() else 0
        )
    )
    return cyclists


def get_single_ride(cyclist: str, ride_index: int) -> dict[str, Any]:
    """Return one ride with metadata and summary stats.

    Args:
        cyclist: Cyclist folder name (e.g. cyclist9).
        ride_index: 1-based ride index.
    """
    if ride_index < 1:
        raise ValueError("ride_index must be >= 1")

    rides_dir = _resolve_data_path(f"../DB/rides/{cyclist}")
    if not rides_dir.exists() or not rides_dir.is_dir():
        raise FileNotFoundError(f"Cyclist directory not found: {rides_dir}")

    rides = extract_donnee_pickle(rides_dir)
    if not rides:
        raise ValueError(f"No valid rides found for {cyclist}")

    if ride_index > len(rides):
        raise IndexError(
            f"ride_index out of range: {ride_index} (available: 1..{len(rides)})"
        )

    ride = rides[ride_index - 1].copy()
    ride = ride.replace({np.nan: None})

    # Convert numpy scalar values to native Python for JSON serialization.
    records = ride.to_dict(orient="records")
    clean_records: list[dict[str, Any]] = []
    for row in records:
        clean_row: dict[str, Any] = {}
        for key, value in row.items():
            clean_row[key] = value.item() if isinstance(value, np.generic) else value
        clean_records.append(clean_row)

    hr_series = (
        pd.to_numeric(ride["hr"], errors="coerce")
        if "hr" in ride.columns
        else pd.Series(dtype=float)
    )
    po_series = (
        pd.to_numeric(ride["po"], errors="coerce")
        if "po" in ride.columns
        else pd.Series(dtype=float)
    )

    def _safe_stat(series: pd.Series, name: str) -> float | None:
        val = getattr(series, name)()
        return float(val) if pd.notna(val) else None

    return {
        "cyclist": cyclist,
        "ride_index": ride_index,
        "datetime": ride.attrs.get("ride_datetime_label", "unknown"),
        "n_points": int(ride.shape[0]),
        "columns": [str(c) for c in ride.columns.tolist()],
        "data": clean_records,
        "stats": {
            "hr_mean": _safe_stat(hr_series, "mean"),
            "hr_min": _safe_stat(hr_series, "min"),
            "hr_max": _safe_stat(hr_series, "max"),
            "po_mean": _safe_stat(po_series, "mean"),
            "po_max": _safe_stat(po_series, "max"),
        },
    }


def extract_donnee_pickle(dir_path: str | os.PathLike) -> list[pd.DataFrame]:
    """Load and enrich ride data from pickle files in directory.

    Args:
        dir_path: Directory path (relative from backend or absolute).
                 Relative paths resolve from backend root directory.
                 Example: "../DB/rides/cyclist9"
    """
    resolved_dir = _resolve_data_path(dir_path)
    sorties = list_files(resolved_dir)

    rides = []
    ride_datetimes = []
    skipped_files: list[str] = []
    for sortie in sorted(
        [s for s in sorties if ".pkl" in s], key=parse_datetime_from_ride_filename
    ):
        fichier = resolved_dir / sortie
        try:
            ride = load_pickle_secure(fichier)
        except Exception as exc:
            skipped_files.append(f"{sortie}: {exc}")
            warnings.warn(
                f"Skipping incompatible pickle file {fichier.name}: {exc}",
                UserWarning,
            )
            continue

        dt = parse_datetime_from_ride_filename(sortie)
        rides.append(ride)
        ride_datetimes.append(dt)

    if len(rides) == 0:
        details = "; ".join(skipped_files[:5])
        raise RuntimeError(
            f"No readable pickle files found in {resolved_dir}."
            + (f" Examples: {details}" if details else "")
        )

    rides_feat = add_features_to_rides(rides)
    for ride, dt in zip(rides_feat, ride_datetimes):
        ride.attrs["ride_datetime"] = dt
        ride.attrs["ride_datetime_label"] = format_datetime_for_title(dt)

    return rides_feat


from app.services.prediction_algorithms.arx_no_fuite import (
    prediction_arx_with_prev_rides_no_fuite,
)
from app.services.prediction_algorithms.arx_selected import (
    prediction_arx_from_selected_ride,
)
from app.services.prediction_algorithms.default_model import prediction
from app.services.prediction_algorithms.historical_model import (
    prediction_with_prev_rides,
)
from app.services.prediction_algorithms.physiologic import prediction_physiologic


def compute_rmse_per_ride(
    rides: list[pd.DataFrame], pred_cols: list[str], labels: list[str]
) -> pd.DataFrame:
    """Compute RMSE for each ride and prediction column."""
    rows: list[dict[str, Any]] = []
    for ride_idx, ride in enumerate(rides, start=1):
        row: dict[str, Any] = {"ride": ride_idx}
        for pred_col, label in zip(pred_cols, labels):
            mask = ride["hr"].notna() & ride[pred_col].notna()
            if mask.sum() == 0:
                row[label] = float("nan")
            else:
                err = ride.loc[mask, "hr"] - ride.loc[mask, pred_col]
                row[label] = float(np.sqrt(np.mean(err**2)))
        rows.append(row)
    return pd.DataFrame(rows)


@dataclass
class AnalysisConfig:
    """Configuration for analysis execution."""

    dir_path: str
    selected_models_plot: list[str]
    selected_models_stats: list[str]
    show_rmse_table: bool = True
    prev_ride: int = 1
    nan_ratio: float = 0.1
    selected_train_ride: int = 1
    selected_target_rides: int | list[int] | None = None


def run_notebook_analysis(config: AnalysisConfig) -> dict[str, Any]:
    """Execute full analysis pipeline with specified configuration."""
    rides = extract_donnee_pickle(config.dir_path)

    selected_models_compute = list(
        dict.fromkeys(config.selected_models_plot + config.selected_models_stats)
    )
    predictions: dict[str, list[pd.DataFrame]] = {}

    if "pred_default" in selected_models_compute:
        predictions["pred_default"] = prediction(
            [r.copy(deep=True) for r in rides],
            lag_start=5,
            max_nan_ratio=config.nan_ratio,
        )

    if "pred_arx_selected" in selected_models_compute:
        predictions["pred_arx_selected"] = prediction_arx_from_selected_ride(
            [r.copy(deep=True) for r in rides],
            train_ride_index=config.selected_train_ride,
            target_ride_indices=config.selected_target_rides,
            n_hr_lags=1,
            ridge_alpha=1,
            po_lag_start=5,
            pred_col="arx_pred_selected",
            max_nan_ratio=config.nan_ratio,
            init_window=3,
            one_based_index=True,
        )
    if "pred_physio" in selected_models_compute:
        predictions["pred_physio"] = prediction_physiologic(
            [r.copy(deep=True) for r in rides]
        )

    model_specs = {
        "pred_default": {"col": "pred1", "label": "pred_default"},
        "pred_arx_selected": {"col": "arx_pred_selected", "label": "pred_arx_selected"},
        "pred_physio": {"col": "physio_pred", "label": "pred_physio"},
    }

    unknown = [m for m in selected_models_compute if m not in model_specs]
    if unknown:
        raise ValueError(f"Unknown models in selection: {unknown}")

    missing = [m for m in selected_models_compute if m not in predictions]
    if missing:
        raise ValueError(f"Models not computed: {missing}")

    rides_combined: list[pd.DataFrame] = []
    for i, ride in enumerate(rides):
        base = ride.copy()
        if "t_min" not in base.columns and "t" in base.columns:
            base["t_min"] = base["t"] / 60.0

        for model_key in selected_models_compute:
            spec = model_specs[model_key]
            src_ride = predictions[model_key][i]
            base[model_key] = src_ride[spec["col"]]

        rides_combined.append(base)

    pred_cols_stats = config.selected_models_stats
    labels_stats = [model_specs[m]["label"] for m in config.selected_models_stats]

    rmse_df = (
        compute_rmse_per_ride(rides_combined, pred_cols_stats, labels_stats)
        if len(pred_cols_stats) > 0
        else pd.DataFrame()
    )

    model_data_summary = pd.DataFrame(
        {
            "model": selected_models_compute,
            "valid_points": [
                int(
                    sum(
                        (df["hr"].notna() & df[m].notna()).sum()
                        for df in rides_combined
                    )
                )
                for m in selected_models_compute
            ],
        }
    )

    return {
        "n_rides": len(rides_combined),
        "selected_models_compute": selected_models_compute,
        "rmse_table": rmse_df.to_dict(orient="records"),
        "model_data_summary": model_data_summary.to_dict(orient="records"),
    }


def compute_metrics(actual: list[float], predicted: list[float]) -> dict[str, float]:
    """Compute RMSE, MAE, R² for predictions.

    Args:
        actual: List of actual values (or numpy array)
        predicted: List of predicted values

    Returns:
        Dict with 'rmse', 'mae', 'r2' keys
    """
    actual_arr = np.array(actual, dtype=float)
    pred_arr = np.array(predicted, dtype=float)

    # Mask out NaN values
    mask = ~(np.isnan(actual_arr) | np.isnan(pred_arr))
    if not mask.any():
        return {"rmse": float("nan"), "mae": float("nan"), "r2": float("nan")}

    actual_clean = actual_arr[mask]
    pred_clean = pred_arr[mask]

    # RMSE
    rmse = float(np.sqrt(np.mean((actual_clean - pred_clean) ** 2)))

    # MAE
    mae = float(np.mean(np.abs(actual_clean - pred_clean)))

    # R²
    ss_res = np.sum((actual_clean - pred_clean) ** 2)
    ss_tot = np.sum((actual_clean - np.mean(actual_clean)) ** 2)
    r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else float("nan")

    return {"rmse": rmse, "mae": mae, "r2": r2}


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""

    dir_path: str
    selected_models_compute: list[str]
    prev_ride: int = 1
    nan_ratio: float = 1.0
    selected_train_ride: int = 1
    selected_target_rides: int | list[int] | None = None


def run_pipeline(config: PipelineConfig) -> dict[str, Any]:
    """Execute full pipeline and return rides with predictions."""
    rides = extract_donnee_pickle(config.dir_path)
    if not rides:
        raise ValueError(f"No valid rides found in {config.dir_path}")

    selected_models_compute = config.selected_models_compute
    predictions: dict[str, list[pd.DataFrame]] = {}

    # Compute requested models
    if "pred_hist" in selected_models_compute:
        predictions["pred_hist"] = prediction_with_prev_rides(
            [r.copy(deep=True) for r in rides],
            x_prev_rides=config.prev_ride,
            max_nan_ratio=config.nan_ratio,
        )

    if "pred_default" in selected_models_compute:
        predictions["pred_default"] = prediction([r.copy(deep=True) for r in rides])

    if "pred_no_fuite" in selected_models_compute:
        predictions["pred_no_fuite"] = prediction_arx_with_prev_rides_no_fuite(
            [r.copy(deep=True) for r in rides],
            x_prev_rides=config.prev_ride,
            max_nan_ratio=config.nan_ratio,
            init_window=5,
            n_hr_lags=1,
            ridge_alpha=5,
            po_lag_start=5,
        )

    if "pred_arx_selected" in selected_models_compute:
        predictions["pred_arx_selected"] = prediction_arx_from_selected_ride(
            [r.copy(deep=True) for r in rides],
            train_ride_index=config.selected_train_ride,
            target_ride_indices=config.selected_target_rides,
            n_hr_lags=1,
            ridge_alpha=5,
            po_lag_start=5,
            pred_col="arx_pred_selected",
            max_nan_ratio=config.nan_ratio,
            init_window=5,
            one_based_index=True,
        )
    if "pred_physio" in selected_models_compute:
        predictions["pred_physio"] = prediction_physiologic(
            [r.copy(deep=True) for r in rides],
        )

    # Model specifications
    model_specs = {
        "pred_default": {"col": "pred1", "label": "pred_default"},
        "pred_hist": {"col": "pred_prev", "label": "pred_hist"},
        "pred_no_fuite": {"col": "arx_pred_no_fuite", "label": "pred_no_fuite"},
        "pred_arx_selected": {"col": "arx_pred_selected", "label": "pred_arx_selected"},
        "pred_physio": {"col": "physio_pred", "label": "pred_physio"},
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


@dataclass
class CompareModelsConfig:
    """Configuration for model comparison."""

    dir_path: str
    train_ride_index_1: int
    train_ride_index_2: int
    test_ride_index: int
    apply_to_all_rides: bool = False


def compare_models_trained(config: CompareModelsConfig) -> dict[str, Any]:
    """Compare two models trained on different rides, tested on a third ride."""
    rides = extract_donnee_pickle(config.dir_path)
    if not rides:
        raise ValueError(f"No valid rides found in {config.dir_path}")

    n_rides = len(rides)

    # Validate indices
    if config.train_ride_index_1 < 1 or config.train_ride_index_1 > n_rides:
        raise ValueError(
            f"train_ride_index_1 out of range: {config.train_ride_index_1} (available: 1..{n_rides})"
        )
    if config.train_ride_index_2 < 1 or config.train_ride_index_2 > n_rides:
        raise ValueError(
            f"train_ride_index_2 out of range: {config.train_ride_index_2} (available: 1..{n_rides})"
        )
    if config.test_ride_index < 1 or config.test_ride_index > n_rides:
        raise ValueError(
            f"test_ride_index out of range: {config.test_ride_index} (available: 1..{n_rides})"
        )
    if config.train_ride_index_1 == config.train_ride_index_2:
        raise ValueError("train_ride_index_1 and train_ride_index_2 must be different")

    # Train model 1 on ride 1, test on test_ride
    rides_copy_1 = [r.copy(deep=True) for r in rides]
    pred_1_all = prediction_arx_from_selected_ride(
        rides_copy_1,
        train_ride_index=config.train_ride_index_1,
        target_ride_indices=config.test_ride_index,
        n_hr_lags=1,
        ridge_alpha=5,
        po_lag_start=5,
        pred_col="model_1_pred",
        max_nan_ratio=0.10,
        init_window=5,
        one_based_index=True,
    )

    # Train model 2 on ride 2, test on test_ride
    rides_copy_2 = [r.copy(deep=True) for r in rides]
    pred_2_all = prediction_arx_from_selected_ride(
        rides_copy_2,
        train_ride_index=config.train_ride_index_2,
        target_ride_indices=config.test_ride_index,
        n_hr_lags=1,
        ridge_alpha=5,
        po_lag_start=5,
        pred_col="model_2_pred",
        max_nan_ratio=0.10,
        init_window=5,
        one_based_index=True,
    )

    # Get test ride predictions (1-based index means we need index-1 for 0-based array)
    test_ride_zero_idx = config.test_ride_index - 1
    test_ride_1 = pred_1_all[test_ride_zero_idx]
    test_ride_2 = pred_2_all[test_ride_zero_idx]

    # Extract predictions
    model1_preds = test_ride_1["model_1_pred"].tolist()
    model2_preds = test_ride_2["model_2_pred"].tolist()

    # Compute metrics on test ride
    actual_hr = test_ride_1["hr"].tolist()
    metrics_1 = compute_metrics(actual_hr, model1_preds)
    metrics_2 = compute_metrics(actual_hr, model2_preds)

    # Prepare ride data response
    ride_data = {
        "datetime": test_ride_1.attrs.get("ride_datetime_label", "unknown"),
        "n_points": int(test_ride_1.shape[0]),
        "columns": [str(c) for c in test_ride_1.columns.tolist()],
        "data": test_ride_1.to_dict(orient="records"),
    }

    # If requested, apply both models to all rides and compute diffs
    all_rides_diffs = None
    if config.apply_to_all_rides:
        # Train both models on all rides
        rides_copy_all_1 = [r.copy(deep=True) for r in rides]
        pred_all_1 = prediction_arx_from_selected_ride(
            rides_copy_all_1,
            train_ride_index=config.train_ride_index_1,
            target_ride_indices=None,  # Apply to all
            n_hr_lags=1,
            ridge_alpha=5,
            po_lag_start=5,
            pred_col="model_1_pred",
            max_nan_ratio=0.10,
            init_window=5,
            one_based_index=True,
        )

        rides_copy_all_2 = [r.copy(deep=True) for r in rides]
        pred_all_2 = prediction_arx_from_selected_ride(
            rides_copy_all_2,
            train_ride_index=config.train_ride_index_2,
            target_ride_indices=None,  # Apply to all
            n_hr_lags=1,
            ridge_alpha=5,
            po_lag_start=5,
            pred_col="model_2_pred",
            max_nan_ratio=0.10,
            init_window=5,
            one_based_index=True,
        )

        # Compute diffs for each ride
        all_rides_diffs = []
        for i, (r1, r2) in enumerate(zip(pred_all_1, pred_all_2), start=1):
            m1_preds_arr = r1["model_1_pred"].to_numpy(dtype=float)
            m2_preds_arr = r2["model_2_pred"].to_numpy(dtype=float)

            # Compute mean diff: sum(modeleA - modeleB) / nb_points
            valid_mask = ~(np.isnan(m1_preds_arr) | np.isnan(m2_preds_arr))
            if valid_mask.any():
                diffs = m1_preds_arr[valid_mask] - m2_preds_arr[valid_mask]
                mean_diff = float(np.mean(diffs))
            else:
                mean_diff = 0.0

            all_rides_diffs.append(
                {
                    "ride_index": i,
                    "datetime": r1.attrs.get("ride_datetime_label", "unknown"),
                    "n_points": int(r1.shape[0]),
                    "mean_bpm_diff": mean_diff,
                    "predictions": [
                        {
                            "model_1": (
                                float(m1_preds_arr[j])
                                if np.isfinite(m1_preds_arr[j])
                                else None
                            ),
                            "model_2": (
                                float(m2_preds_arr[j])
                                if np.isfinite(m2_preds_arr[j])
                                else None
                            ),
                            "diff": (
                                float(m1_preds_arr[j] - m2_preds_arr[j])
                                if np.isfinite(m1_preds_arr[j])
                                and np.isfinite(m2_preds_arr[j])
                                else None
                            ),
                        }
                        for j in range(len(m1_preds_arr))
                    ],
                }
            )

    return {
        "ok": True,
        "train_ride_1": config.train_ride_index_1,
        "train_ride_2": config.train_ride_index_2,
        "test_ride": config.test_ride_index,
        "ride_data": ride_data,
        "model1_predictions": model1_preds,
        "model2_predictions": model2_preds,
        "metrics": {
            "rmse_model1": metrics_1["rmse"],
            "rmse_model2": metrics_2["rmse"],
            "mae_model1": metrics_1["mae"],
            "mae_model2": metrics_2["mae"],
            "r2_model1": metrics_1["r2"],
            "r2_model2": metrics_2["r2"],
        },
        "all_rides_diffs": all_rides_diffs,
    }
