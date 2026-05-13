import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import pytest
import pandas as pd
import numpy as np

from app.services.prediction_algorithms import common


def test_import_common():
    from app.services.prediction_algorithms import common

    assert common is not None


def test_ml_imports_returns_tuple():
    lm, make_pipeline, StandardScaler = common._ml_imports()
    assert lm is not None


def test_warn_and_invalid_missing_columns():
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.warns(UserWarning):
        assert common._warn_and_is_invalid_hr_po(df, 0, "ctx") is True


def test_warn_and_invalid_empty_columns():
    df = pd.DataFrame({"po": [np.nan, np.nan], "hr": [np.nan, np.nan]})
    with pytest.warns(UserWarning):
        assert common._warn_and_is_invalid_hr_po(df, 1, "no_prediction") is True


def test_warn_and_invalid_valid_columns():
    df = pd.DataFrame({"po": [1, 2], "hr": [60, 70]})
    assert common._warn_and_is_invalid_hr_po(df, 1, "ctx") is False
