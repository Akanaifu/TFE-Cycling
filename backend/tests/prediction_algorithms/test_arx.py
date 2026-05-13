import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
import pytest

from app.services.prediction_algorithms import arx_selected, arx_no_fuite


def test_import_arx_modules():
    from app.services.prediction_algorithms import arx_no_fuite, arx_selected

    assert arx_no_fuite is not None
    assert arx_selected is not None


def make_arx_ride(length=80, po_base=120):
    po = np.full(length, po_base, dtype=float)
    hr = 60.0 + 0.2 * np.arange(length)
    work = po * 0.1
    df = pd.DataFrame({"po": po, "hr": hr, "work": work})
    # add po_lag columns
    for k in range(1, 12):
        df[f"po_lag_{k}"] = np.roll(po, k)
        df.loc[: k - 1, f"po_lag_{k}"] = np.nan
    return df


def test_prediction_arx_selected_basic():
    r0 = make_arx_ride(80)
    r1 = make_arx_ride(80)
    r2 = make_arx_ride(80)
    out = arx_selected.prediction_arx_from_selected_ride(
        [r0, r1, r2], train_ride_index=1
    )
    assert isinstance(out, list)
    # predictions column exists on targets
    assert (
        "arx_pred_selected" in out[1].columns or "arx_pred_selected" in out[2].columns
    )


def test_prediction_arx_no_fuite_basic():
    rides = [make_arx_ride(80) for _ in range(4)]
    out = arx_no_fuite.prediction_arx_with_prev_rides_no_fuite(rides, x_prev_rides=2)
    assert isinstance(out, list)
    assert "arx_pred" in out[1].columns


def test_arx_selected_index_error():
    with pytest.raises(IndexError):
        arx_selected.prediction_arx_from_selected_ride(
            [make_arx_ride(50)], train_ride_index=5
        )


def make_small_arx_ride(length=30):
    po = np.linspace(100, 150, length)
    hr = 60 + 0.2 * np.arange(length)
    work = po * 0.1
    df = pd.DataFrame({"po": po, "hr": hr, "work": work})
    # add some po_lag
    for k in range(1, 6):
        df[f"po_lag_{k}"] = np.roll(po, k)
        df.loc[: k - 1, f"po_lag_{k}"] = np.nan
    return df


def test_arx_selected_ridge_none_and_missing_columns():
    r = make_small_arx_ride(40)
    # remove feature columns from train to trigger early return
    r_missing = r.drop(columns=["work"])
    with pytest.warns(UserWarning):
        out = arx_selected.prediction_arx_from_selected_ride(
            [r_missing, r], train_ride_index=1, ridge_alpha=None
        )
    # train invalid -> returns rides_out unchanged (pred col present but NaN)
    assert isinstance(out, list)


def test_arx_no_fuite_with_nan_exog_and_init_window():
    r0 = make_small_arx_ride(50)
    r1 = make_small_arx_ride(50)
    # inject NaN in exog for some timesteps to test skip
    r1.loc[10:15, "po"] = np.nan
    out = arx_no_fuite.prediction_arx_with_prev_rides_no_fuite(
        [r0, r1, r0], x_prev_rides=2, ridge_alpha=0.5, init_window=5
    )
    assert isinstance(out, list)
    assert "arx_pred" in out[1].columns


def test_arx_selected_index_and_target_handling():
    r = make_small_arx_ride(50)
    with pytest.raises(IndexError):
        arx_selected.prediction_arx_from_selected_ride([r], train_ride_index=5)


def test_arx_empty_lists_return_empty():
    assert arx_selected.prediction_arx_from_selected_ride([], train_ride_index=1) == []
    assert arx_no_fuite.prediction_arx_with_prev_rides_no_fuite([]) == []


def test_arx_selected_target_index_branches():
    r0 = make_small_arx_ride(60)
    r1 = make_small_arx_ride(60)
    r2 = make_small_arx_ride(60)
    out_int = arx_selected.prediction_arx_from_selected_ride(
        [r0, r1, r2], train_ride_index=1, target_ride_indices=2
    )
    assert isinstance(out_int, list)
    out_list = arx_selected.prediction_arx_from_selected_ride(
        [r0, r1, r2], train_ride_index=1, target_ride_indices=[2, 3]
    )
    assert isinstance(out_list, list)


def test_arx_selected_short_training_returns():
    short_train = make_small_arx_ride(10)
    out = arx_selected.prediction_arx_from_selected_ride(
        [short_train, make_small_arx_ride(10)], train_ride_index=1
    )
    assert isinstance(out, list)
    assert out[1]["arx_pred_selected"].isna().all()


def test_arx_selected_invalid_target_and_nonfinite_prediction(monkeypatch):
    class DummyLinearRegression:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        def fit(self, X, y):
            return self

        def predict(self, X):
            self.calls += 1
            if self.calls == 1:
                return np.array([np.nan])
            return np.array([float(np.nanmean(np.asarray(X, dtype=float)))])

    class DummyLM:
        LinearRegression = DummyLinearRegression
        Ridge = DummyLinearRegression

    monkeypatch.setattr(
        arx_selected,
        "_ml_imports",
        lambda: (DummyLM, lambda *args, **kwargs: DummyLinearRegression(), object),
    )

    train = make_small_arx_ride(60)
    train["hr"] = np.inf

    target_invalid = make_small_arx_ride(60).drop(columns=["po"])
    target_valid = make_small_arx_ride(60)

    with pytest.warns(UserWarning):
        out = arx_selected.prediction_arx_from_selected_ride(
            [train, target_invalid, target_valid],
            train_ride_index=1,
            target_ride_indices=[2, 3],
            ridge_alpha=None,
            n_hr_lags=15,
            init_window=10,
        )
    assert isinstance(out, list)


def test_arx_no_fuite_short_train_missing_cols_and_nonfinite(monkeypatch):
    short = make_small_arx_ride(5)
    out_short = arx_no_fuite.prediction_arx_with_prev_rides_no_fuite(
        [short, make_small_arx_ride(60)], x_prev_rides=1
    )
    assert isinstance(out_short, list)

    train_missing = make_small_arx_ride(60).drop(columns=["work"])
    out_missing = arx_no_fuite.prediction_arx_with_prev_rides_no_fuite(
        [train_missing, make_small_arx_ride(60)], x_prev_rides=1
    )
    assert isinstance(out_missing, list)

    class DummyLinearRegression:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        def fit(self, X, y):
            return self

        def predict(self, X):
            self.calls += 1
            if self.calls == 1:
                return np.array([np.nan])
            return np.array([float(np.nanmean(np.asarray(X, dtype=float)))])

    class DummyLM:
        LinearRegression = DummyLinearRegression
        Ridge = DummyLinearRegression

    monkeypatch.setattr(
        arx_no_fuite,
        "_ml_imports",
        lambda: (DummyLM, lambda *args, **kwargs: DummyLinearRegression(), object),
    )

    train = make_small_arx_ride(60)
    train["hr"] = np.inf

    target_invalid = make_small_arx_ride(60).drop(columns=["hr"])
    target_valid = make_small_arx_ride(60)

    with pytest.warns(UserWarning):
        out = arx_no_fuite.prediction_arx_with_prev_rides_no_fuite(
            [train, target_invalid, target_valid],
            x_prev_rides=1,
            ridge_alpha=None,
            n_hr_lags=15,
            init_window=10,
        )
    assert isinstance(out, list)
