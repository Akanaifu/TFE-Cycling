from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.prediction_algorithms.common import (
    _ml_imports,
    _warn_and_is_invalid_hr_po,
)


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
        return rides_out

    r_train = rides_out[train_idx]
    miss = [c for c in feature_cols + ["hr"] if c not in r_train.columns]
    if miss:
        import warnings
        msg = f"[Prediction ARX selected] Train ride {train_idx + 1}: missing columns {miss}. Predictions skipped."
        warnings.warn(msg, UserWarning)
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
        return rides_out

    reg.fit(x_train.loc[valid], y_train.loc[valid])

    y_start = y_train.dropna().iloc[: max(1, int(init_window))]
    if len(y_start) > 0:
        hr_init = float(np.median(y_start.to_numpy(dtype=float)))
        if not np.isfinite(hr_init):
            hr_init = float(np.nanmedian(y_train.to_numpy(dtype=float)))
    else:
        hr_init = float(np.nanmedian(y_train.to_numpy(dtype=float)))
    if not np.isfinite(hr_init):
        hr_init = 0.0

    for i in target_indices_zb:
        if not valid_ride_mask[i]:
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
