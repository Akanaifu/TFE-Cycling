from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from app.services.prediction_algorithms.common import (
    _ml_imports,
    _warn_and_is_invalid_hr_po,
)


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
