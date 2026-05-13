import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
import pytest

from app.services.prediction_algorithms import historical_model


def test_import_historical_model():
    from app.services.prediction_algorithms import historical_model

    assert historical_model is not None


def make_ride(n=40):
    po = np.linspace(80, 220, n)
    work = po * 0.1
    work2 = work**2
    hr = 40 + 0.3 * po
    df = pd.DataFrame({"po": po, "work": work, "work2": work2, "hr": hr})
    return df


def test_prediction_with_prev_rides_empty():
    assert historical_model.prediction_with_prev_rides([]) == []


def test_prediction_with_prev_rides_basic():
    r0 = make_ride(50)
    r1 = make_ride(50)
    r2 = make_ride(50)
    out = historical_model.prediction_with_prev_rides([r0, r1, r2], x_prev_rides=2)
    assert isinstance(out, list)
    # pred_prevx should be added to rides
    assert "pred_prevx" in out[1].columns or "pred_prevx" in out[2].columns


def test_prediction_with_prev_rides_invalid_and_short_train():
    valid = make_ride(50)
    invalid = pd.DataFrame({"po": [np.nan, np.nan], "hr": [np.nan, np.nan]})

    with pytest.warns(UserWarning):
        out = historical_model.prediction_with_prev_rides(
            [valid, invalid], x_prev_rides=1
        )
    assert isinstance(out, list)

    short = make_ride(5)
    for k in range(1, 10):
        short[f"po_lag_{k}"] = np.roll(short["po"].to_numpy(), k)
        short.loc[: k - 1, f"po_lag_{k}"] = short.loc[: k - 1, "po"]
    invalid_tail = pd.DataFrame({"po": [np.nan, np.nan], "hr": [np.nan, np.nan]})
    with pytest.warns(UserWarning):
        out_short = historical_model.prediction_with_prev_rides(
            [short, make_ride(50), invalid_tail], x_prev_rides=1
        )
    assert isinstance(out_short, list)
