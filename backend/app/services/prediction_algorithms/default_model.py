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
    train_ride_index: int = 1,
    target_ride_indices: int | list[int] | None = None,
    with_work: bool = True,
    lag_start: int = 8,
    max_nan_ratio: float = 0.10,
    one_based_index: bool = True,
    pred_col: str = "pred1",
) -> list[pd.DataFrame]:
    """Predict HR using a linear regression trained on a base ride."""
    lm, _, _ = _ml_imports()

    if len(rides_pickle) == 0:
        return []

    n_rides = len(rides_pickle)

    def to_zero_based(idx: int) -> int:
        ride_idx = int(idx) - 1 if one_based_index else int(idx)
        if ride_idx < 0 or ride_idx >= n_rides:
            raise IndexError(f"Invalid ride index {idx}")
        return ride_idx

    train_idx = to_zero_based(train_ride_index)

    rides_feat = [r.copy() for r in rides_pickle]
    po_lag_cols = [c for c in rides_feat[0].columns if c.startswith("po_lag_")]
    po_lag_cols = sorted(po_lag_cols, key=lambda s: int(s.split("_")[-1]))
    po_lag_cols = po_lag_cols[max(0, lag_start - 1) :]

    features = (
        (["po", "work", "work2"] + po_lag_cols) if with_work else (["po"] + po_lag_cols)
    )

    valid_ride_mask = [False] * len(rides_feat)
    target_indices_zb: list[int]
    if target_ride_indices is None:
        target_indices_zb = [i for i in range(n_rides) if i != train_idx]
    elif isinstance(target_ride_indices, int):
        target_indices_zb = [to_zero_based(target_ride_indices)]
    else:
        target_indices_zb = [to_zero_based(i) for i in target_ride_indices]

    for ride in rides_feat:
        ride[pred_col] = np.nan

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

    if not valid_ride_mask[train_idx]:
        warnings.warn(
            f"[Prediction] ride {train_ride_index}: unavailable or invalid training ride. Ride skipped.",
            UserWarning,
        )

        return rides_feat

    ride_train = rides_feat[train_idx]
    x_train = ride_train.loc[:, features]
    y_train = ride_train["hr"]
    valid_mask = x_train.notna().all(axis=1) & y_train.notna()
    invalid_ratio = 1.0 - float(valid_mask.mean())
    if invalid_ratio > max_nan_ratio or valid_mask.sum() < 20:
        warnings.warn(
            "No exploitable ride found for training (too many NaN or insufficient valid points).",
            UserWarning,
        )
        return rides_feat

    reg = lm.LinearRegression(fit_intercept=True)
    reg.fit(x_train.loc[valid_mask], y_train.loc[valid_mask])

    for j in target_indices_zb:
        if not valid_ride_mask[j]:
            continue
        ride_target = rides_feat[j]
        x_target = ride_target.loc[:, features]
        pred = pd.Series(np.nan, index=ride_target.index, dtype=float)
        target_valid = x_target.notna().all(axis=1)
        if target_valid.any():
            pred.loc[target_valid] = reg.predict(x_target.loc[target_valid])
        ride_target[pred_col] = pred

    return rides_feat
