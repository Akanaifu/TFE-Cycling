"""Core analysis and prediction models for TFE cycling analysis.

Provides feature engineering, linear regression, and ARX-based HR prediction models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import os
import warnings

import numpy as np
import pandas as pd


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


def _ml_imports() -> tuple[Any, Any, Any]:
    try:
        from sklearn import linear_model as lm
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing ML dependencies. Install scikit-learn in backend venv."
        ) from exc
    return lm, make_pipeline, StandardScaler


def _scipy_minimize() -> Any:
    try:
        from scipy.optimize import minimize
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing scipy dependency. Install scipy in backend venv."
        ) from exc
    return minimize


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
            ride = pd.read_pickle(fichier)
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


def prediction(
    rides_pickle: list[pd.DataFrame],
    with_work: bool = True,
    lag_start: int = 8,
    max_nan_ratio: float = 0.10,
) -> list[pd.DataFrame]:
    """Predict HR using linear regression trained on individual rides."""
    lm, _, _ = _ml_imports()

    if len(rides_pickle) == 0:
        return []

    rides_feat = [r.copy() for r in rides_pickle]
    po_lag_cols = [c for c in rides_feat[0].columns if c.startswith("po_lag_")]
    po_lag_cols = sorted(po_lag_cols, key=lambda s: int(s.split("_")[-1]))
    po_lag_cols = po_lag_cols[max(0, lag_start - 1) :]

    features = (
        (["po", "work", "work2"] + po_lag_cols) if with_work else (["po"] + po_lag_cols)
    )

    valid_ride_mask = [False] * len(rides_feat)
    for idx, ride in enumerate(rides_feat, start=1):
        if _warn_and_is_invalid_hr_po(ride, idx, "Prediction"):
            continue
        missing = [col for col in features if col not in ride.columns]

        if missing:
            warnings.warn(
                f"[Prediction] ride {idx}: missing regression columns {missing[:5]}. Ride skipped.",
                UserWarning,
            )
            continue
        valid_ride_mask[idx - 1] = True

    valid_train_indices: list[int] = []

    for i, ride_train in enumerate(rides_feat):
        if not valid_ride_mask[i]:
            continue
        x_train = ride_train.loc[:, features]
        y_train = ride_train["hr"]
        valid_mask = x_train.notna().all(axis=1) & y_train.notna()
        invalid_ratio = 1.0 - float(valid_mask.mean())
        if invalid_ratio > max_nan_ratio or valid_mask.sum() < 20:
            continue

        reg = lm.LinearRegression(fit_intercept=True)
        reg.fit(x_train.loc[valid_mask], y_train.loc[valid_mask])
        valid_train_indices.append(i + 1)

        for j, ride_target in enumerate(rides_feat):
            if not valid_ride_mask[j]:
                continue
            x_target = ride_target.loc[:, features]
            pred = pd.Series(np.nan, index=ride_target.index, dtype=float)
            target_valid = x_target.notna().all(axis=1)
            if target_valid.any():
                pred.loc[target_valid] = reg.predict(x_target.loc[target_valid])
            ride_target[f"pred{i + 1}"] = pred

    if len(valid_train_indices) == 0:
        warnings.warn(
            "No exploitable ride found for training (too many NaN or insufficient valid points).",
            UserWarning,
        )

    return rides_feat


def prediction_with_prev_rides(
    rides_feat: list[pd.DataFrame],
    x_prev_rides: int = 3,
    with_work: bool = True,
    lag_start: int = 8,
    max_nan_ratio: float = 0.10,
) -> list[pd.DataFrame]:
    """Predict HR using sliding window over previous rides."""
    lm, _, _ = _ml_imports()

    if len(rides_feat) == 0:
        return []

    po_lag_cols = [c for c in rides_feat[0].columns if c.startswith("po_lag_")]
    po_lag_cols = sorted(po_lag_cols, key=lambda s: int(s.split("_")[-1]))
    po_lag_cols = po_lag_cols[max(0, lag_start - 1) :]

    features = (
        (["po", "work", "work2"] + po_lag_cols) if with_work else (["po"] + po_lag_cols)
    )

    valid_ride_mask = [False] * len(rides_feat)
    for idx, ride in enumerate(rides_feat, start=1):
        if _warn_and_is_invalid_hr_po(ride, idx, "Prediction prev rides"):
            continue
        valid_ride_mask[idx - 1] = True
        ride["pred_prevx"] = np.nan

    for i, _ in enumerate(rides_feat):
        if not valid_ride_mask[i]:
            continue
        start = max(0, i - x_prev_rides)
        train_slice = [rides_feat[j] for j in range(start, i) if valid_ride_mask[j]]

        x_parts, y_parts = [], []
        for r in train_slice:
            xr = r.loc[:, features]
            yr = r["hr"]
            valid = xr.notna().all(axis=1) & yr.notna()

            lag_depth = max(
                [
                    int(c.split("_")[-1])
                    for c in features
                    if c.startswith("po_lag_") or c.startswith("hr_lag_")
                ],
                default=0,
            )
            valid_eval = (
                valid.iloc[lag_depth:] if lag_depth < len(valid) else valid.iloc[0:0]
            )
            if len(valid_eval) == 0:
                continue

            invalid_ratio = 1.0 - float(valid_eval.mean())
            if invalid_ratio <= max_nan_ratio and valid.sum() >= 20:
                x_parts.append(xr.loc[valid])
                y_parts.append(yr.loc[valid])

        if len(x_parts) == 0:
            continue

        x_train = pd.concat(x_parts, axis=0)
        y_train = pd.concat(y_parts, axis=0)

        reg = lm.LinearRegression(fit_intercept=True)
        reg.fit(x_train, y_train)

        x_target = rides_feat[i].loc[:, features]
        valid_target = x_target.notna().all(axis=1)
        if valid_target.any():
            rides_feat[i].loc[valid_target, "pred_prevx"] = reg.predict(
                x_target.loc[valid_target]
            )

    return rides_feat


def prediction_arx_with_prev_rides_no_fuite(
    rides_feat: list[pd.DataFrame],
    x_prev_rides: int = 3,
    n_hr_lags: int = 15,
    with_work: bool = True,
    po_lag_start: int = 8,
    pred_col: str = "arx_pred",
    max_nan_ratio: float = 0.10,
    ridge_alpha: float | None = 1.0,
    init_window: int = 10,
) -> list[pd.DataFrame]:
    """ARX model with HR lags and previous rides, preventing data leakage."""
    lm, make_pipeline, StandardScaler = _ml_imports()

    if len(rides_feat) == 0:
        return []

    valid_ride_mask = [False] * len(rides_feat)

    for idx, ride in enumerate(rides_feat, start=1):
        if _warn_and_is_invalid_hr_po(ride, idx, "Prediction ARX no fuite"):
            continue
        valid_ride_mask[idx - 1] = True
        hr_num = pd.to_numeric(ride["hr"], errors="coerce")
        for k in range(1, n_hr_lags + 1):
            ride[f"hr_lag_{k}"] = hr_num.shift(k)

    po_lag_cols = [c for c in rides_feat[0].columns if c.startswith("po_lag_")]
    po_lag_cols = sorted(po_lag_cols, key=lambda s: int(s.split("_")[-1]))
    po_lag_cols = po_lag_cols[max(0, po_lag_start - 1) :][:120]

    exog_cols = ["po"] + (["work"] if with_work else []) + po_lag_cols
    ar_cols = [f"hr_lag_{k}" for k in range(1, n_hr_lags + 1)]
    feature_cols = exog_cols + ar_cols

    for ride in rides_feat:
        ride[pred_col] = np.nan

    def create_regressor():
        """Create linear regressor or ridge pipeline based on alpha."""
        if ridge_alpha is None:
            return lm.LinearRegression(fit_intercept=True)
        return make_pipeline(
            StandardScaler(),
            lm.Ridge(alpha=float(ridge_alpha), fit_intercept=True, solver="svd"),
        )

    for i, _ in enumerate(rides_feat):
        if not valid_ride_mask[i]:
            continue
        start = max(0, i - x_prev_rides)
        train_slice = [rides_feat[j] for j in range(start, i) if valid_ride_mask[j]]

        x_parts, y_parts, start_hr_vals = [], [], []
        for r in train_slice:
            miss = [c for c in feature_cols + ["hr"] if c not in r.columns]
            if miss:
                continue

            xr = r.loc[:, feature_cols]
            yr = pd.to_numeric(r["hr"], errors="coerce")
            valid = xr.notna().all(axis=1) & yr.notna()

            lag_depth = max(
                [
                    int(c.split("_")[-1])
                    for c in feature_cols
                    if c.startswith("po_lag_") or c.startswith("hr_lag_")
                ],
                default=0,
            )
            valid_eval = (
                valid.iloc[lag_depth:] if lag_depth < len(valid) else valid.iloc[0:0]
            )
            if len(valid_eval) == 0:
                continue

            invalid_ratio = 1.0 - float(valid_eval.mean())
            if invalid_ratio <= max_nan_ratio and valid.sum() >= max(20, n_hr_lags + 5):
                x_parts.append(xr.loc[valid])
                y_parts.append(yr.loc[valid])
                y_start = yr.dropna().iloc[: max(1, int(init_window))]
                if len(y_start) > 0:
                    start_hr_vals.append(
                        float(np.median(y_start.to_numpy(dtype=float)))
                    )

        if len(x_parts) == 0:
            continue

        x_train = pd.concat(x_parts, axis=0)
        y_train = pd.concat(y_parts, axis=0)

        reg = create_regressor()
        reg.fit(x_train, y_train)

        rt = rides_feat[i]
        exog = rt.loc[:, exog_cols].to_numpy(dtype=float)
        y_pred = np.full(len(rt), np.nan, dtype=float)

        if len(start_hr_vals) > 0:
            hr_init = float(np.median(np.array(start_hr_vals, dtype=float)))
        else:
            hr_init = float(np.nanmedian(y_train.to_numpy(dtype=float)))

        if not np.isfinite(hr_init):
            hr_init = 0.0

        seed_n = min(len(rt), max(n_hr_lags, int(init_window)))
        y_pred[:seed_n] = hr_init

        for t in range(seed_n, len(rt)):
            if not np.isfinite(exog[t]).all():
                continue
            hr_lags_vals = y_pred[t - n_hr_lags : t][::-1]
            if len(hr_lags_vals) != n_hr_lags or not np.isfinite(hr_lags_vals).all():
                continue

            x_row = np.concatenate([exog[t], hr_lags_vals]).reshape(1, -1)
            x_pred = pd.DataFrame(x_row, columns=feature_cols)
            y_pred[t] = float(reg.predict(x_pred)[0])

        rt[pred_col] = y_pred

    return rides_feat


def prediction_arx_from_selected_ride(
    rides_feat: list[pd.DataFrame],
    train_ride_index: int,
    target_ride_indices: int | list[int] | None = None,
    n_hr_lags: int = 15,
    with_work: bool = True,
    po_lag_start: int = 8,
    pred_col: str = "arx_pred_selected",
    max_nan_ratio: float = 0.10,
    ridge_alpha: float | None = 1.0,
    init_window: int = 10,
    one_based_index: bool = True,
) -> list[pd.DataFrame]:
    """Train ARX model on single ride and predict on target rides."""
    lm, make_pipeline, StandardScaler = _ml_imports()

    if len(rides_feat) == 0:
        return []

    n_rides = len(rides_feat)

    def to_zero_based(idx: int) -> int:
        i = int(idx) - 1 if one_based_index else int(idx)
        if i < 0 or i >= n_rides:
            raise IndexError(f"Invalid ride index {idx}")
        return i

    train_idx = to_zero_based(train_ride_index)

    if target_ride_indices is None:
        target_indices_zb = [i for i in range(n_rides) if i != train_idx]
    elif isinstance(target_ride_indices, int):
        target_indices_zb = [to_zero_based(target_ride_indices)]
    else:
        target_indices_zb = [to_zero_based(i) for i in target_ride_indices]

    rides_out = [r.copy() for r in rides_feat]
    valid_ride_mask = [False] * len(rides_out)

    for idx, ride in enumerate(rides_out, start=1):
        if _warn_and_is_invalid_hr_po(ride, idx, "Prediction ARX selected"):
            continue
        valid_ride_mask[idx - 1] = True
        hr_num = pd.to_numeric(ride["hr"], errors="coerce")
        for k in range(1, n_hr_lags + 1):
            ride[f"hr_lag_{k}"] = hr_num.shift(k)

    po_lag_cols = [c for c in rides_out[0].columns if c.startswith("po_lag_")]
    po_lag_cols = sorted(po_lag_cols, key=lambda s: int(s.split("_")[-1]))
    po_lag_cols = po_lag_cols[max(0, po_lag_start - 1) :][:120]

    exog_cols = ["po"] + (["work"] if with_work else []) + po_lag_cols
    ar_cols = [f"hr_lag_{k}" for k in range(1, n_hr_lags + 1)]
    feature_cols = exog_cols + ar_cols

    for ride in rides_out:
        ride[pred_col] = np.nan

    if ridge_alpha is None:
        reg = lm.LinearRegression(fit_intercept=True)
    else:
        reg = make_pipeline(
            StandardScaler(),
            lm.Ridge(alpha=float(ridge_alpha), fit_intercept=True, solver="svd"),
        )

    if not valid_ride_mask[train_idx]:
        warnings.warn(
            f"[Prediction ARX selected] train ride {train_idx + 1} is invalid (hr/po). No prediction computed.",
            UserWarning,
        )
        return rides_out

    r_train = rides_out[train_idx]
    miss = [c for c in feature_cols + ["hr"] if c not in r_train.columns]
    if miss:
        warnings.warn(
            f"[Prediction ARX selected] train ride missing columns {miss[:5]}. No prediction computed.",
            UserWarning,
        )
        return rides_out

    x_train = r_train.loc[:, feature_cols]
    y_train = pd.to_numeric(r_train["hr"], errors="coerce")
    valid = x_train.notna().all(axis=1) & y_train.notna()

    lag_depth = max(
        [
            int(c.split("_")[-1])
            for c in feature_cols
            if c.startswith("po_lag_") or c.startswith("hr_lag_")
        ],
        default=0,
    )
    valid_eval = valid.iloc[lag_depth:] if lag_depth < len(valid) else valid.iloc[0:0]
    invalid_ratio = 1.0 - float(valid_eval.mean()) if len(valid_eval) > 0 else 1.0

    if (
        len(valid_eval) == 0
        or invalid_ratio > max_nan_ratio
        or valid.sum() < max(20, n_hr_lags + 5)
    ):
        warnings.warn(
            "[Prediction ARX selected] selected train ride is not exploitable for ARX training.",
            UserWarning,
        )
        return rides_out

    reg.fit(x_train.loc[valid], y_train.loc[valid])

    y_start = y_train.dropna().iloc[: max(1, int(init_window))]
    hr_init = (
        float(np.median(y_start.to_numpy(dtype=float)))
        if len(y_start) > 0
        else float(np.nanmedian(y_train.to_numpy(dtype=float)))
    )
    if not np.isfinite(hr_init):
        hr_init = 0.0

    for i in target_indices_zb:
        if not valid_ride_mask[i]:
            warnings.warn(
                f"[Prediction ARX selected] target ride {i + 1} is invalid (hr/po). Ride skipped.",
                UserWarning,
            )
            continue
        rt = rides_out[i]
        exog = rt.loc[:, exog_cols].to_numpy(dtype=float)
        y_pred = np.full(len(rt), np.nan, dtype=float)

        seed_n = min(len(rt), max(n_hr_lags, int(init_window)))
        y_pred[:seed_n] = hr_init

        for t in range(seed_n, len(rt)):
            if not np.isfinite(exog[t]).all():
                continue
            hr_lags_vals = y_pred[t - n_hr_lags : t][::-1]
            if len(hr_lags_vals) != n_hr_lags or not np.isfinite(hr_lags_vals).all():
                continue

            x_row = np.concatenate([exog[t], hr_lags_vals]).reshape(1, -1)
            x_pred = pd.DataFrame(x_row, columns=feature_cols)
            y_pred[t] = float(reg.predict(x_pred)[0])

        rt[pred_col] = y_pred

    return rides_out


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
    nan_ratio: float = 1.0
    selected_train_ride: int = 1
    selected_target_rides: int | list[int] | None = None


def run_notebook_analysis(config: AnalysisConfig) -> dict[str, Any]:
    """Execute full analysis pipeline with specified configuration."""
    rides = extract_donnee_pickle(config.dir_path)

    selected_models_compute = list(
        dict.fromkeys(config.selected_models_plot + config.selected_models_stats)
    )
    predictions: dict[str, list[pd.DataFrame]] = {}

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

    model_specs = {
        "pred_hist": {"col": "pred_prevx", "label": "pred_hist"},
        "pred_default": {"col": "pred1", "label": "pred_default"},
        "pred_no_fuite": {"col": "arx_pred", "label": "pred_no_fuite"},
        "pred_arx_selected": {"col": "arx_pred_selected", "label": "pred_arx_selected"},
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
