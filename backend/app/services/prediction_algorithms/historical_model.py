from __future__ import annotations

import pandas as pd

from app.services.prediction_algorithms.common import (
    _ml_imports,
    _warn_and_is_invalid_hr_po,
)


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
        ride["pred_prevx"] = pd.NA

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
