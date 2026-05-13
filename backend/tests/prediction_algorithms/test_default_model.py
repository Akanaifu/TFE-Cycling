import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
import pytest

from app.services.prediction_algorithms import default_model


def test_import_default_model():
    from app.services.prediction_algorithms import default_model

    assert default_model is not None


def make_ride(n=30):
    po = np.linspace(100, 200, n)
    work = po * 0.1
    work2 = work**2
    hr = 30 + 0.5 * po
    df = pd.DataFrame({"po": po, "work": work, "work2": work2, "hr": hr})
    return df


def test_prediction_empty():
    assert default_model.prediction([]) == []


def test_prediction_index_error():
    df = make_ride(25)
    with pytest.raises(IndexError):
        default_model.prediction([df], train_ride_index=5)


def test_prediction_basic():
    r1 = make_ride(50)
    r2 = make_ride(50)
    out = default_model.prediction([r1, r2], train_ride_index=1)
    assert isinstance(out, list)
    assert "pred1" in out[1].columns
    assert out[1]["pred1"].notna().any()


def make_ride_with_missing_cols(n=30):
    # no work/work2 columns to trigger missing regression columns
    po = np.linspace(100, 200, n)
    hr = 30 + 0.5 * po
    return pd.DataFrame({"po": po, "hr": hr})


def test_missing_regression_columns_warns_and_skips():
    r1 = make_ride_with_missing_cols(30)
    r2 = make_ride_with_missing_cols(30)
    # train ride missing work/work2 -> should warn and skip training, returning rides
    with pytest.warns(UserWarning):
        out = default_model.prediction([r1, r2], train_ride_index=1)
    assert isinstance(out, list)


def test_with_work_false_uses_only_po():
    r1 = make_ride(50)
    # add some po_lag columns so features list includes them
    for k in range(1, 10):
        r1[f"po_lag_{k}"] = np.roll(r1["po"].to_numpy(), k)
        r1.loc[: k - 1, f"po_lag_{k}"] = r1.loc[: k - 1, "po"]

    r2 = r1.copy()
    out = default_model.prediction([r1, r2], train_ride_index=1, with_work=False)
    assert isinstance(out, list)
    assert "pred1" in out[1].columns


def test_target_indices_int_and_list_and_skips():
    train = make_ride(60)
    for k in range(1, 10):
        train[f"po_lag_{k}"] = np.roll(train["po"].to_numpy(), k)
        train.loc[: k - 1, f"po_lag_{k}"] = train.loc[: k - 1, "po"]

    target_invalid = train.drop(columns=["work"])
    target_no_valid_rows = train.copy()
    target_no_valid_rows["po_lag_8"] = np.nan

    out_int = default_model.prediction(
        [train, train.copy()], train_ride_index=1, target_ride_indices=2
    )
    assert isinstance(out_int, list)

    with pytest.warns(UserWarning):
        out_list = default_model.prediction(
            [train, target_invalid, target_no_valid_rows],
            train_ride_index=1,
            target_ride_indices=[2, 3],
        )
    assert isinstance(out_list, list)


def test_invalid_training_due_to_nan_ratio():
    # create train ride with too many NaNs to trigger invalid_ratio branch
    n = 40
    po = np.linspace(100, 200, n)
    hr = np.array([np.nan] * n)
    r_train = pd.DataFrame(
        {"po": po, "work": po * 0.1, "work2": (po * 0.1) ** 2, "hr": hr}
    )
    r_target = pd.DataFrame(
        {"po": po, "work": po * 0.1, "work2": (po * 0.1) ** 2, "hr": hr + 100}
    )
    with pytest.warns(UserWarning):
        out = default_model.prediction(
            [r_train, r_target], train_ride_index=1, max_nan_ratio=0.0
        )
    assert isinstance(out, list)


def test_invalid_train_ride_warns_and_returns():
    invalid_train = pd.DataFrame(
        {"po": [np.nan, np.nan, np.nan], "hr": [np.nan, np.nan, np.nan]}
    )
    valid_target = make_ride(30)
    with pytest.warns(UserWarning):
        out = default_model.prediction(
            [invalid_train, valid_target], train_ride_index=1
        )
    assert isinstance(out, list)
