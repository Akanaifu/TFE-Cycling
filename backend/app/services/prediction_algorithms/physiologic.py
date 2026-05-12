"""
Basé sur le fichier opti.py de M. de Smet se trouvant dans tfe/notebook/opti.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.linalg import inv
from scipy.optimize import minimize
from sklearn.linear_model import LinearRegression

from app.services.prediction_algorithms.common import _warn_and_is_invalid_hr_po

# Constants from opti.py
WARM_UP_MIN = 15
MIN_INC = 0.1
MIN_DEC = MIN_INC
MIN_PO = 50
MAX_PO = 450

HR_MIN_BOUNDS = (35.0, 120.0)
MP_BOUNDS = (0.0, 2.0)
K_E_BOUNDS = (0.0, 0.02)
K_GAIN_BOUNDS = (1e-4, 1.0)


def _clip_physio_params(
    hr_min: float,
    m: float,
    k_e: float,
    k_plus: float,
    k_minus: float,
) -> tuple[float, float, float, float, float]:
    """Clamp fitted parameters to stable, physically plausible ranges."""
    hr_min = float(np.clip(hr_min, *HR_MIN_BOUNDS))
    m = float(np.clip(m, *MP_BOUNDS))
    k_e = float(np.clip(k_e, *K_E_BOUNDS))
    k_plus = float(np.clip(k_plus, *K_GAIN_BOUNDS))
    k_minus = float(np.clip(k_minus, *K_GAIN_BOUNDS))
    return hr_min, m, k_e, k_plus, k_minus


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


def _add_pof(df: pd.DataFrame, dt2: int) -> None:
    """Add smoothed power output (pof) to dataframe."""
    dt2 = int(round(dt2))
    if dt2 < 1:
        dt2 = 1
    df["pof"] = df["po"].rolling(window=dt2, center=True).mean()
    df.loc[df["pof"].isna(), "pof"] = df.loc[df["pof"].isna(), "po"]


def _add_hrf(df: pd.DataFrame, dt3: int) -> None:
    """Add smoothed heart rate (hrf) to dataframe."""
    dt3 = int(round(dt3))
    if dt3 > 0:
        df["hrf"] = df["hr"].rolling(window=dt3 * 2, center=True).mean()
        df.loc[df["hrf"].isna(), "hrf"] = df.loc[df["hrf"].isna(), "hr"]
    else:
        df["hrf"] = df["hr"].copy()


def _add_grad_hr(df: pd.DataFrame, dt1: int) -> None:
    """Add HR gradient to dataframe."""
    dt1 = int(round(dt1))
    if dt1 < 0:
        dt1 = 0
    hr = df["hr"]
    diff = np.array(list(hr[1:]) + list(hr.iloc[-1:])) - hr.values
    df["grad_hr"] = pd.Series(diff).rolling(window=dt1 * 2, center=True).mean()
    df.loc[df["grad_hr"].isna(), "grad_hr"] = 0.0


def _fit_simple_reg(
    df: pd.DataFrame, ke_opti: int = 1
) -> tuple[float, float, float, float, float]:
    """
    Fit simple regression model to estimate parameters.
    Returns: hr_min, m, k_e, k_plus, k_minus
    """
    grad_hr = df["grad_hr"][WARM_UP_MIN * 60 :].values.copy()
    hr = df["hrf"][WARM_UP_MIN * 60 :].values.copy()
    pof = df["pof"][WARM_UP_MIN * 60 :].values.copy()
    e = np.cumsum(df["pof"][WARM_UP_MIN * 60 :].values).copy()

    active = (pof > MIN_PO) & (grad_hr != 0) & (pof < MAX_PO)
    grad_hr = grad_hr[active]
    hr = hr[active]
    pof = pof[active]
    e = e[active]
    Y = grad_hr.reshape(-1, 1)[:, 0]

    if ke_opti == 1:
        X = np.concatenate(
            [
                np.ones([len(hr), 1]),
                pof.reshape(-1, 1),
                hr.reshape(-1, 1),
                e.reshape(-1, 1),
            ],
            axis=1,
        )
    elif ke_opti == 0:
        X = np.concatenate(
            [np.ones([len(hr), 1]), pof.reshape(-1, 1), hr.reshape(-1, 1)], axis=1
        )
    else:
        raise ValueError("ke_opti must be 0, 1, or a float value")

    W = inv(X.T @ X) @ X.T @ Y

    k = -W[2]
    hr_min = W[0] / k
    m = W[1] / k
    if ke_opti == 1:
        k_e = W[3] / k
    elif ke_opti == 0:
        k_e = 0
    else:
        k_e = ke_opti

    k_plus, k_minus = k, k
    return hr_min, m, k_e, k_plus, k_minus


def _fit_simple_reg_fixed_k(
    df: pd.DataFrame, ke_opti: int = 1, k_minus: float = 0.01, k_plus: float = 0.012
) -> tuple[float, float, float]:
    """
    Fit simple regression with fixed k_plus/k_minus.
    Returns: hr_min, m, k_e
    """
    grad_hr = df["grad_hr"][WARM_UP_MIN * 60 :].values.copy()
    hr = df["hrf"][WARM_UP_MIN * 60 :].values.copy()
    pof = df["pof"][WARM_UP_MIN * 60 :].values.copy()
    e = np.cumsum(df["pof"][WARM_UP_MIN * 60 :].values).copy()

    active = (pof > MIN_PO) & (grad_hr != 0)
    grad_hr_active = grad_hr[active]
    hr_active = hr[active]
    pof_active = pof[active]
    e_active = e[active]

    increasing = (pof_active > MIN_PO) & (grad_hr_active > MIN_INC)
    decreasing = (pof_active > MIN_PO) & (grad_hr_active < -MIN_DEC)

    grad_hr_inc = grad_hr_active[increasing].copy()
    hr_inc = hr_active[increasing].copy()
    pof_inc = pof_active[increasing].copy()
    e_inc = e_active[increasing].copy()

    grad_hr_dec = grad_hr_active[decreasing].copy()
    hr_dec = hr_active[decreasing].copy()
    pof_dec = pof_active[decreasing].copy()
    e_dec = e_active[decreasing].copy()

    Y_dec = (grad_hr_dec / k_minus + hr_dec).reshape(-1, 1)[:, 0]
    Y_inc = (grad_hr_inc / k_plus + hr_inc).reshape(-1, 1)[:, 0]
    Y = np.concatenate([Y_dec, Y_inc])

    if ke_opti == 1:
        X_inc = np.concatenate(
            [np.ones([len(hr_inc), 1]), pof_inc.reshape(-1, 1), e_inc.reshape(-1, 1)],
            axis=1,
        )
        X_dec = np.concatenate(
            [np.ones([len(hr_dec), 1]), pof_dec.reshape(-1, 1), e_dec.reshape(-1, 1)],
            axis=1,
        )
    elif ke_opti == 0:
        X_inc = np.concatenate(
            [np.ones([len(hr_inc), 1]), pof_inc.reshape(-1, 1)], axis=1
        )
        X_dec = np.concatenate(
            [np.ones([len(hr_dec), 1]), pof_dec.reshape(-1, 1)], axis=1
        )
    else:
        raise ValueError("ke_opti must be 0 or 1 for this function")

    X = np.concatenate([X_dec, X_inc])
    W = inv(X.T @ X) @ X.T @ Y

    hr_min = float(W[0])
    m = float(W[1])
    if ke_opti == 1:
        k_e = float(W[2])
    elif ke_opti == 0:
        k_e = 0.0
    else:
        k_e = float(ke_opti)

    return hr_min, m, k_e


def _get_k_minus_and_plus(
    df: pd.DataFrame, hr_min: float, m: float, k_e: float
) -> tuple[float, float]:
    """
    Calculate k_minus and k_plus from fitted parameters.
    Returns: k_minus, k_plus
    """
    grad_hr = df["grad_hr"][WARM_UP_MIN * 60 :].values.copy()
    hr = df["hrf"][WARM_UP_MIN * 60 :].values.copy()
    pof = df["pof"][WARM_UP_MIN * 60 :].values.copy()
    e = np.cumsum(df["pof"][WARM_UP_MIN * 60 :].values).copy()

    model = LinearRegression(fit_intercept=False)

    # Increasing phase
    increasing = (pof > MIN_PO) & (grad_hr > MIN_INC) & (pof < MAX_PO)
    grad_hr_inc = grad_hr[increasing].copy()
    hr_inc = hr[increasing].copy()
    pof_inc = pof[increasing].copy()
    e_inc = e[increasing].copy()

    y = grad_hr_inc
    x = (hr_min + pof_inc * m + k_e * e_inc - hr_inc).reshape(-1, 1)
    model.fit(x, y)
    k_plus = float(model.coef_[0])

    # Decreasing phase
    decreasing = (pof > MIN_PO) & (grad_hr < -MIN_DEC)
    grad_hr_dec = grad_hr[decreasing].copy()
    hr_dec = hr[decreasing].copy()
    pof_dec = pof[decreasing].copy()
    e_dec = e[decreasing].copy()

    y = grad_hr_dec
    x = (hr_min + pof_dec * m + k_e * e_dec - hr_dec).reshape(-1, 1)
    model.fit(x, y)
    k_minus = float(model.coef_[0])

    k_minus = float(np.clip(k_minus, *K_GAIN_BOUNDS))
    k_plus = float(np.clip(k_plus, *K_GAIN_BOUNDS))
    return k_minus, k_plus


def _fit_parameters_alt_fitting(
    df: pd.DataFrame, ke_opti: int = 1
) -> tuple[float, float, float, float, float]:
    """
    Iteratively fit parameters using alt_fitting approach.
    Alternates between fitting hr_min, m, k_e and fitting k_plus, k_minus.
    Returns: hr_min, m, k_e, k_plus, k_minus
    """
    # Initial estimation
    hr_min, m, k_e, k_plus, k_minus = _fit_simple_reg(df, ke_opti)

    # Iterate to refine k_plus and k_minus
    for _ in range(25):
        k_minus, k_plus = _get_k_minus_and_plus(df, hr_min, m, k_e)
        hr_min, m, k_e = _fit_simple_reg_fixed_k(df, ke_opti, k_minus, k_plus)

    return hr_min, m, k_e, k_plus, k_minus


def _fit_parameters_nelder(
    df: pd.DataFrame, ke_opti: int = 1
) -> tuple[float, float, float, float, float]:
    """Fit physiologic parameters with Nelder-Mead over the ride RMSE."""
    try:
        hr_min_0, m_0, k_e_0, k_plus_0, k_minus_0 = _fit_simple_reg(df, ke_opti)
        for _ in range(25):
            k_minus, k_plus = _get_k_minus_and_plus(df, hr_min, m, k_e)
            hr_min, m, k_e = _fit_simple_reg_fixed_k(df, ke_opti, k_minus, k_plus)
    except Exception:
        hr_min_0, m_0, k_e_0, k_plus_0, k_minus_0 = 62.0, 0.25, 0.0, 0.03, 0.02

    x0 = np.array([hr_min_0, m_0, k_plus_0, k_minus_0, k_e_0], dtype=float)

    def objective(x: np.ndarray) -> float:
        hr_min, m, k_plus, k_minus, k_e = map(float, x)
        try:
            predicted = _predict_with_params(
                [df],
                hr_min=hr_min,
                mp=m,
                k_plus=k_plus,
                k_minus=k_minus,
                k_e=k_e,
                hr_max=float(np.nanmax(pd.to_numeric(df["hr"], errors="coerce"))),
                dt2=6,
                dt3=3,
                pred_col="__physio_nelder__",
            )[0]
        except Exception:
            return float("inf")

        y_true = pd.to_numeric(df["hr"], errors="coerce").to_numpy(dtype=float)
        y_pred = pd.to_numeric(
            predicted["__physio_nelder__"], errors="coerce"
        ).to_numpy(dtype=float)
        valid = np.isfinite(y_true) & np.isfinite(y_pred)
        if valid.sum() == 0:
            return float("inf")
        return float(np.sqrt(np.mean((y_true[valid] - y_pred[valid]) ** 2)))

    res = minimize(
        objective,
        x0=x0,
        method="Nelder-Mead",
        options={"maxiter": 120, "xatol": 1e-3, "fatol": 1e-3},
    )
    best = res.x if res.success else x0
    hr_min, m, k_plus, k_minus, k_e = map(float, best)
    return hr_min, m, k_e, k_plus, k_minus


def _prepare_rides_for_fitting(
    rides: list[pd.DataFrame], dt1: int = 5, dt2: int = 16, dt3: int = 5
) -> list[pd.DataFrame]:
    """
    Prepare rides by adding necessary columns (pof, hrf, grad_hr).
    Returns a list of prepared dataframes.
    """
    rides_prepared = []
    for ride in rides:
        ride_copy = ride.copy()
        if "po" not in ride_copy.columns or "hr" not in ride_copy.columns:
            continue

        _add_pof(ride_copy, dt2)
        _add_hrf(ride_copy, dt3)
        _add_grad_hr(ride_copy, dt1)
        rides_prepared.append(ride_copy)

    return rides_prepared


def _get_calibration_ride(
    rides_train: list[pd.DataFrame] | None,
    rides_feat: list[pd.DataFrame],
    calibration_ride_index: int = 0,
) -> pd.DataFrame:
    """Return the single ride used to fit physiologic parameters."""
    source_rides = rides_train if rides_train is not None else rides_feat
    if len(source_rides) == 0:
        raise ValueError("No training rides available for parameter fitting")

    if calibration_ride_index < 0 or calibration_ride_index >= len(source_rides):
        raise IndexError(
            f"calibration_ride_index out of range: {calibration_ride_index} (available: 0..{len(source_rides) - 1})"
        )
    return source_rides[calibration_ride_index]


def _fit_parameters_from_ride(
    ride: pd.DataFrame,
    dt1: int,
    dt2: int,
    dt3: int,
    ke_opti: int,
    method: str,
) -> tuple[float, float, float, float, float]:
    """Fit physiologic parameters from one calibration ride."""
    ride_prepared = _prepare_rides_for_fitting([ride], dt1, dt2, dt3)
    if len(ride_prepared) == 0:
        raise ValueError("Calibration ride has no valid data after preparation")

    calibration_df = ride_prepared[0]
    if method == "alt_fitting":
        return _fit_parameters_alt_fitting(calibration_df, ke_opti)
    if method == "fit_nelder":
        return _fit_parameters_nelder(calibration_df, ke_opti)
    raise ValueError(f"Unknown fitting method: {method}")


def _predict_with_params(
    rides: list[pd.DataFrame],
    hr_min: float,
    mp: float,
    k_plus: float,
    k_minus: float,
    k_e: float,
    hr_max: float,
    dt2: int = 16,
    dt3: int = 5,
    pred_col: str = "physio_pred",
) -> list[pd.DataFrame]:
    """
    Apply physiologic prediction with given parameters.
    Returns: list of dataframes with predictions added.
    """
    rides_out = [r.copy() for r in rides]

    for ride_idx, ride in enumerate(rides_out, start=1):
        if _warn_and_is_invalid_hr_po(
            ride, ride_idx, f"Prediction physio ({pred_col})"
        ):
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

    return rides_out


def prediction_physiologic(
    rides_feat: list[pd.DataFrame],
    rides_train: list[pd.DataFrame] | None = None,
    hr_max: float | None = None,
    dt1: int = 10,
    dt2: int = 16,
    dt3: int = 5,
    ke_opti: int = 1,
    method: str = "alt_fitting",
    calibration_ride_index: int = 0,
) -> list[pd.DataFrame]:
    """
    Predict HR using physiologic steady-state model with parameters learned from one calibration ride.

    Args:
        rides_feat: List of rides to make predictions on
        rides_train: List of training rides to learn parameters from. If None, uses rides_feat for fitting.
        hr_max: Maximum HR. If None, inferred from training data.
        dt1: Window for HR gradient smoothing
        dt2: Window for power output smoothing
        dt3: Window for HR smoothing
        ke_opti: Whether to optimize k_e (1=yes, 0=no)
        method: Which fitting method to use ('alt_fitting', 'fit_nelder')

    Returns:
        List of dataframes with predictions added for each method used
    """
    if len(rides_feat) == 0:
        return []

    calibration_ride = _get_calibration_ride(
        rides_train, rides_feat, calibration_ride_index=calibration_ride_index
    )

    # Infer hr_max if not provided
    if hr_max is None:
        hr_max = infer_cyclist_hr_max([calibration_ride])

    hr_min, mp, k_e, k_plus, k_minus = _fit_parameters_from_ride(
        calibration_ride,
        dt1=dt1,
        dt2=dt2,
        dt3=dt3,
        ke_opti=ke_opti,
        method=method,
    )
    param_source = method

    # Add predictions using calculated parameters
    rides_with_pred = _predict_with_params(
        rides_feat,
        hr_min=hr_min,
        mp=mp,
        k_plus=k_plus,
        k_minus=k_minus,
        k_e=k_e,
        hr_max=hr_max,
        dt2=dt2,
        dt3=dt3,
        pred_col=f"physio_pred_{param_source}",
    )

    return rides_with_pred


def prediction_physiologic_all_methods(
    rides_feat: list[pd.DataFrame],
    rides_train: list[pd.DataFrame] | None = None,
    hr_max: float | None = None,
    dt1: int = 10,
    dt2: int = 16,
    dt3: int = 5,
    ke_opti: int = 1,
    calibration_ride_index: int = 0,
) -> list[pd.DataFrame]:
    """
    Predict HR using all available physiologic methods.

    Args:
        rides_feat: List of rides to make predictions on
        rides_train: List of training rides to learn parameters from. If None, uses rides_feat.
        hr_max: Maximum HR. If None, inferred from training data.
        dt1: Window for HR gradient smoothing
        dt2: Window for power output smoothing
        dt3: Window for HR smoothing
        ke_opti: Whether to optimize k_e (1=yes, 0=no)

    Returns:
        List of dataframes with predictions added for all methods:
        - physio_pred_simple_reg
        - physio_pred_alt_fitting
    """
    if len(rides_feat) == 0:
        return []

    results = [r.copy() for r in rides_feat]

    calibration_ride = _get_calibration_ride(
        rides_train, rides_feat, calibration_ride_index=calibration_ride_index
    )

    # Infer hr_max if not provided
    if hr_max is None:
        hr_max = infer_cyclist_hr_max([calibration_ride])

    calibration_prepared = _prepare_rides_for_fitting([calibration_ride], dt1, dt2, dt3)

    if len(calibration_prepared) == 0:
        raise ValueError("No valid calibration ride after preparation")

    calibration_df = calibration_prepared[0]

    # Method 1: Simple regression
    try:
        hr_min_1, mp_1, k_e_1, k_plus_1, k_minus_1 = _fit_simple_reg(
            calibration_df, ke_opti
        )
        results = _predict_with_params(
            results,
            hr_min=hr_min_1,
            mp=mp_1,
            k_plus=k_plus_1,
            k_minus=k_minus_1,
            k_e=k_e_1,
            hr_max=hr_max,
            dt2=dt2,
            dt3=dt3,
            pred_col="physio_pred_simple_reg",
        )
    except Exception as e:
        print(f"Warning: simple_reg fitting failed: {e}")

    # Method 2: Alternating fitting
    try:
        hr_min_2, mp_2, k_e_2, k_plus_2, k_minus_2 = _fit_parameters_alt_fitting(
            calibration_df, ke_opti
        )
        results = _predict_with_params(
            results,
            hr_min=hr_min_2,
            mp=mp_2,
            k_plus=k_plus_2,
            k_minus=k_minus_2,
            k_e=k_e_2,
            hr_max=hr_max,
            dt2=dt2,
            dt3=dt3,
            pred_col="physio_pred_alt_fitting",
        )
    except Exception as e:
        print(f"Warning: alt_fitting fitting failed: {e}")

    # Method 3: Nelder-Mead fitting
    try:
        hr_min_3, mp_3, k_e_3, k_plus_3, k_minus_3 = _fit_parameters_nelder(
            calibration_df, ke_opti
        )
        results = _predict_with_params(
            results,
            hr_min=hr_min_3,
            mp=mp_3,
            k_plus=k_plus_3,
            k_minus=k_minus_3,
            k_e=k_e_3,
            hr_max=hr_max,
            dt2=dt2,
            dt3=dt3,
            pred_col="physio_pred_fit_nelder",
        )
    except Exception as e:
        print(f"Warning: fit_nelder fitting failed: {e}")

    return results
