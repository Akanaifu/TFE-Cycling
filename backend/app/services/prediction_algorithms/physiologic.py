"""
Basé sur le fichier opti.py de M. de Smet se trouvant dans tfe/notebook/opti.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.prediction_algorithms.common import _warn_and_is_invalid_hr_po


def infer_cyclist_hr_max(rides: list[pd.DataFrame], hr_col: str = "hr") -> float:
    """Return the max observed HR across all rides for the cyclist."""
    maxima: list[float] = []
    for ride in rides:
        if hr_col not in ride.columns:
            continue
        hr_series = pd.to_numeric(ride[hr_col], errors="coerce")
        finite = hr_series.to_numpy(dtype=float)
        finite = finite[np.isfinite(finite)]
        if finite.size > 0:
            maxima.append(float(np.max(finite)))

    if not maxima:
        raise ValueError("Unable to infer cyclist hr_max: no valid HR values found.")

    return float(np.max(maxima))


def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    window = int(round(window))
    if window <= 1:
        return values.astype(float, copy=True)
    series = pd.Series(values, dtype=float)
    return (
        series.rolling(window=window, center=True, min_periods=1)
        .mean()
        .to_numpy(dtype=float)
    )


def prediction_physiologic(
    rides_feat: list[pd.DataFrame],
    hr_min: float = 60.0,
    mp: float = 0.25,
    hr_max: float | None = None,
    k_plus: float = 0.03,
    k_minus: float = 0.02,
    k_e: float = 0.0,
    dt2: int = 15,
    dt3: int = 5,
    pred_col: str = "physio_pred",
) -> list[pd.DataFrame]:
    """Predict HR using a physiologic steady-state model inspired by opti.py."""
    if len(rides_feat) == 0:
        return []

    rides_out = [r.copy() for r in rides_feat]
    if hr_max is None:
        hr_max = infer_cyclist_hr_max(rides_out)

    hr_min = float(hr_min)
    hr_max = float(hr_max)
    print(f"{hr_max = }")
    mp = float(mp)
    k_plus = float(k_plus)
    k_minus = float(k_minus)
    k_e = float(k_e)
    dt2 = max(1, int(round(dt2)))
    dt3 = max(1, int(round(dt3)))

    for ride_idx, ride in enumerate(rides_out, start=1):
        if _warn_and_is_invalid_hr_po(ride, ride_idx, "Prediction physio"):
            continue

        po = (
            pd.to_numeric(ride["po"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        )
        hr = pd.to_numeric(ride["hr"], errors="coerce").to_numpy(dtype=float)

        pof = _rolling_mean(po, dt2)
        hrf = _rolling_mean(np.nan_to_num(hr, nan=float(hr_min)), dt3)
        work = np.cumsum(pof)

        hr_ss = hr_min + (pof * mp) + (k_e * work)
        hr_ss = np.clip(hr_ss, hr_min, hr_max)

        hr_sim = np.full(len(ride), np.nan, dtype=float)
        finite_hr = hr[np.isfinite(hr)]
        hr_init = float(hrf[0]) if len(hrf) > 0 and np.isfinite(hrf[0]) else None
        if hr_init is None and finite_hr.size > 0:
            hr_init = float(finite_hr[0])
        if hr_init is None:
            hr_init = float(hr_min)

        hr_sim[0] = float(np.clip(hr_init, hr_min, hr_max))
        for i in range(len(ride) - 1):
            current = hr_sim[i]
            if not np.isfinite(current):
                break

            target = hr_ss[i]
            if not np.isfinite(target):
                target = current

            gain = k_plus if current < target else k_minus
            next_val = current + gain * (target - current)
            hr_sim[i + 1] = float(np.clip(next_val, hr_min, hr_max))

        ride[pred_col] = hr_sim
        ride["physio_hr_ss"] = hr_ss
        ride["physio_hrf"] = hrf

    return rides_out
