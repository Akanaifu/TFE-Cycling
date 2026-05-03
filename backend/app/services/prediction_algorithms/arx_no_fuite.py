from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.prediction_algorithms.common import (
    _ml_imports,
    _warn_and_is_invalid_hr_po,
)


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
