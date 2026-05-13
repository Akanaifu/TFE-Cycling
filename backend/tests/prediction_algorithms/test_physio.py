import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
import pytest
from numpy.random import default_rng

from app.services.prediction_algorithms import physiologic as phys


def test_import_physiologic():
    from app.services.prediction_algorithms import physiologic

    assert physiologic is not None


def make_simple_ride(n=50):
    t = np.arange(n)
    po = np.clip(100 + 0.5 * t, 0, 500)
    hr = np.clip(60 + 0.2 * t + np.random.randn(n) * 0.1, 35, 200)
    return pd.DataFrame({"po": po, "hr": hr})


def test_infer_cyclist_hr_max():
    r1 = pd.DataFrame({"hr": [80, 90, np.nan]})
    r2 = pd.DataFrame({"hr": [85, 88]})
    assert phys.infer_cyclist_hr_max([r1, r2]) == 90.0


def test_roll_and_add_columns():
    df = make_simple_ride(30)
    arr = np.array([1.0, 2.0, 3.0, 4.0])
    out = phys._rolling_mean(arr, 1)
    assert out.shape == arr.shape

    phys._add_pof(df, 3)
    phys._add_hrf(df, 2)
    phys._add_grad_hr(df, 1)
    assert "pof" in df.columns
    assert "hrf" in df.columns
    assert "grad_hr" in df.columns


def test_clip_physio_params():
    hr_min, m, k_e, k_plus, k_minus = phys._clip_physio_params(-100, 10, 1.0, -1.0, 5.0)
    assert hr_min >= phys.HR_MIN_BOUNDS[0]
    assert m >= phys.MP_BOUNDS[0]


def test_get_calibration_ride_errors():
    with pytest.raises(ValueError):
        phys._get_calibration_ride([], [], 0)
    rides = [make_simple_ride(10)]
    with pytest.raises(IndexError):
        phys._get_calibration_ride(None, rides, 5)


def test_predict_with_params_basic():
    df = make_simple_ride(30)
    phys._add_pof(df, 2)
    phys._add_hrf(df, 2)
    phys._add_grad_hr(df, 1)

    out = phys._predict_with_params(
        [df],
        hr_min=50.0,
        mp=0.1,
        k_plus=0.01,
        k_minus=0.01,
        k_e=0.0,
        hr_max=200.0,
        dt2=2,
        dt3=2,
        pred_col="test_pred",
    )
    assert isinstance(out, list)
    assert "test_pred" in out[0].columns


def make_long_ride(n=1200):
    t = np.arange(n)
    rng = default_rng(0)
    po = 120.0 + 10.0 * np.sin(t * 0.01) + rng.normal(0, 0.1, size=n)
    hr = 60.0 + 20.0 * np.sin(t * 0.02) + rng.normal(0, 0.2, size=n)
    df = pd.DataFrame({"po": po, "hr": hr})
    phys._add_pof(df, dt2=6)
    phys._add_hrf(df, dt3=3)
    phys._add_grad_hr(df, dt1=5)
    return df


def test_fit_simple_and_fixed_k_and_get_k():
    df = make_long_ride()
    hr_min, m, k_e, k_plus, k_minus = phys._fit_simple_reg(df, ke_opti=1)
    assert isinstance(hr_min, float)
    hr_min2, m2, k_e2 = phys._fit_simple_reg_fixed_k(
        df, ke_opti=1, k_minus=0.01, k_plus=0.012
    )
    assert isinstance(k_e2, float)
    k_minus_calc, k_plus_calc = phys._get_k_minus_and_plus(df, hr_min, m, k_e)
    assert 0.0 <= k_minus_calc <= 1.0
    assert 0.0 <= k_plus_calc <= 1.0


def test_alt_fitting_and_predict():
    df = make_long_ride()
    params = phys._fit_parameters_alt_fitting(df, ke_opti=1)
    assert len(params) == 5
    hr_min, mp, k_e, k_plus, k_minus = params
    out = phys._predict_with_params(
        [df],
        hr_min=hr_min,
        mp=mp,
        k_plus=k_plus,
        k_minus=k_minus,
        k_e=k_e,
        hr_max=220.0,
        dt2=6,
        dt3=3,
        pred_col="physio_test",
    )
    assert isinstance(out, list)
    assert "physio_test" in out[0].columns


def test_prepare_rides_and_fit_from_ride_and_all_methods():
    df = make_long_ride()
    prepared = phys._prepare_rides_for_fitting([df], dt1=5, dt2=6, dt3=3)
    assert isinstance(prepared, list)
    params = phys._fit_parameters_from_ride(
        df, dt1=5, dt2=6, dt3=3, ke_opti=1, method="alt_fitting"
    )
    assert len(params) == 5

    results = phys.prediction_physiologic_all_methods(
        [df], rides_train=[df], hr_max=220.0, dt1=5, dt2=6, dt3=3, ke_opti=1
    )
    assert isinstance(results, list)


def make_tiny_ride():
    return pd.DataFrame(
        {
            "po": [120.0, 125.0, 130.0, 128.0, 126.0, 124.0],
            "hr": [80.0, 82.0, 85.0, 84.0, 83.0, 81.0],
        }
    )


def test_prediction_physiologic_nelder_fallback(monkeypatch):
    df = make_tiny_ride()

    monkeypatch.setattr(
        phys,
        "_fit_simple_reg",
        lambda df_arg, ke_opti: (_ for _ in ()).throw(Exception("boom")),
    )

    res = phys.prediction_physiologic(
        [df],
        rides_train=[df],
        hr_max=200.0,
        method="fit_nelder",
        calibration_ride_index=0,
    )
    assert isinstance(res, list)


def test_prediction_physiologic_all_methods_exceptions(monkeypatch):
    df = pd.DataFrame(
        {"po": np.linspace(100, 120, 50), "hr": 60 + np.linspace(0, 10, 50)}
    )

    monkeypatch.setattr(
        phys, "_fit_simple_reg", lambda *a, **k: (_ for _ in ()).throw(Exception("s1"))
    )
    monkeypatch.setattr(
        phys,
        "_fit_parameters_alt_fitting",
        lambda *a, **k: (_ for _ in ()).throw(Exception("s2")),
    )
    monkeypatch.setattr(
        phys,
        "_fit_parameters_nelder",
        lambda *a, **k: (_ for _ in ()).throw(Exception("s3")),
    )

    out = phys.prediction_physiologic_all_methods(
        [df], rides_train=[df], calibration_ride_index=0
    )
    assert isinstance(out, list)


def test_physio_helpers_edge_cases():
    df = make_simple_ride(8)
    assert phys._rolling_mean(np.array([1.0, 2.0, 3.0]), 1).tolist() == [1.0, 2.0, 3.0]
    phys._add_pof(df, 0)
    phys._add_hrf(df, 0)
    phys._add_grad_hr(df, -1)
    assert "pof" in df.columns
    assert "hrf" in df.columns
    assert "grad_hr" in df.columns


def test_infer_cyclist_hr_max_missing_and_empty():
    with pytest.raises(ValueError):
        phys.infer_cyclist_hr_max([pd.DataFrame({"po": [1.0, 2.0]})])
    with pytest.raises(ValueError):
        phys.infer_cyclist_hr_max([pd.DataFrame({"hr": [np.nan, np.nan]})])


def test_fit_simple_reg_numeric_ke_opti():
    df = make_long_ride()
    params = phys._fit_simple_reg(df, ke_opti=0.5)
    assert len(params) == 5


def test_fit_simple_reg_invalid_ke_opti():
    df = make_long_ride()
    with pytest.raises(ValueError):
        phys._fit_simple_reg(df, ke_opti="bad")


def test_fit_simple_reg_fixed_k_numeric_ke_opti():
    df = make_long_ride()
    params = phys._fit_simple_reg_fixed_k(df, ke_opti=0.5, k_minus=0.01, k_plus=0.02)
    assert len(params) == 3


def test_fit_simple_reg_fixed_k_invalid_ke_opti():
    df = make_long_ride()
    with pytest.raises(ValueError):
        phys._fit_simple_reg_fixed_k(df, ke_opti="bad")


def test_fit_parameters_nelder_preloop(monkeypatch):
    df = make_long_ride()

    monkeypatch.setattr(
        phys, "_fit_simple_reg", lambda *args, **kwargs: (60.0, 0.2, 0.0, 0.03, 0.02)
    )
    monkeypatch.setattr(
        phys, "_get_k_minus_and_plus", lambda *args, **kwargs: (0.02, 0.03)
    )
    monkeypatch.setattr(
        phys, "_fit_simple_reg_fixed_k", lambda *args, **kwargs: (60.0, 0.2, 0.0)
    )

    class DummyResult:
        success = True
        x = np.array([60.0, 0.2, 0.03, 0.02, 0.0], dtype=float)

    def fake_minimize(objective, x0, method, options):
        objective(x0)
        return DummyResult()

    monkeypatch.setattr(phys, "minimize", fake_minimize)

    params = phys._fit_parameters_nelder(df, ke_opti=1)
    assert len(params) == 5


def test_fit_parameters_nelder_objective_exception(monkeypatch):
    df = make_long_ride()

    monkeypatch.setattr(
        phys, "_fit_simple_reg", lambda *args, **kwargs: (60.0, 0.2, 0.0, 0.03, 0.02)
    )
    monkeypatch.setattr(
        phys, "_get_k_minus_and_plus", lambda *args, **kwargs: (0.02, 0.03)
    )
    monkeypatch.setattr(
        phys, "_fit_simple_reg_fixed_k", lambda *args, **kwargs: (60.0, 0.2, 0.0)
    )
    monkeypatch.setattr(
        phys,
        "_predict_with_params",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("boom")),
    )

    class DummyResult:
        success = True
        x = np.array([60.0, 0.2, 0.03, 0.02, 0.0], dtype=float)

    def fake_minimize(objective, x0, method, options):
        objective(x0)
        return DummyResult()

    monkeypatch.setattr(phys, "minimize", fake_minimize)

    params = phys._fit_parameters_nelder(df, ke_opti=1)
    assert len(params) == 5


def test_fit_parameters_nelder_objective_nan_prediction(monkeypatch):
    df = make_long_ride()

    monkeypatch.setattr(
        phys, "_fit_simple_reg", lambda *args, **kwargs: (60.0, 0.2, 0.0, 0.03, 0.02)
    )
    monkeypatch.setattr(
        phys, "_get_k_minus_and_plus", lambda *args, **kwargs: (0.02, 0.03)
    )
    monkeypatch.setattr(
        phys, "_fit_simple_reg_fixed_k", lambda *args, **kwargs: (60.0, 0.2, 0.0)
    )

    def fake_predict_with_params(*args, **kwargs):
        return [
            pd.DataFrame(
                {"__physio_nelder__": np.full(len(df), np.nan), "hr": df["hr"].values}
            )
        ]

    monkeypatch.setattr(phys, "_predict_with_params", fake_predict_with_params)

    class DummyResult:
        success = True
        x = np.array([60.0, 0.2, 0.03, 0.02, 0.0], dtype=float)

    def fake_minimize(objective, x0, method, options):
        objective(x0)
        return DummyResult()

    monkeypatch.setattr(phys, "minimize", fake_minimize)

    params = phys._fit_parameters_nelder(df, ke_opti=1)
    assert len(params) == 5


def test_prediction_physiologic_empty_and_infers_hr_max():
    assert phys.prediction_physiologic([]) == []
    df = make_long_ride()
    out = phys.prediction_physiologic(
        [df], rides_train=[df], hr_max=None, method="alt_fitting"
    )
    assert isinstance(out, list)


def test_prediction_physiologic_all_methods_empty_and_invalid_calibration():
    assert phys.prediction_physiologic_all_methods([]) == []
    with pytest.raises(ValueError):
        phys.prediction_physiologic_all_methods(
            [pd.DataFrame({"hr": [80.0, 81.0], "work": [1.0, 2.0]})],
            rides_train=[pd.DataFrame({"hr": [80.0, 81.0], "work": [1.0, 2.0]})],
        )


def test_predict_with_params_edge_branches():
    base = make_simple_ride(10)
    base.loc[:2, "hr"] = np.nan
    phys._add_pof(base, 2)
    phys._add_hrf(base, 2)
    phys._add_grad_hr(base, 1)

    out1 = phys._predict_with_params(
        [base],
        hr_min=np.nan,
        mp=0.1,
        k_plus=0.01,
        k_minus=0.01,
        k_e=0.0,
        hr_max=200.0,
        pred_col="pred_nan_hrmin",
    )
    assert "pred_nan_hrmin" in out1[0].columns

    mostly_nan_hr = pd.DataFrame(
        {"po": np.linspace(100, 110, 10), "hr": [np.nan] * 9 + [85.0]}
    )
    out2 = phys._predict_with_params(
        [mostly_nan_hr],
        hr_min=np.nan,
        mp=0.1,
        k_plus=0.01,
        k_minus=0.01,
        k_e=0.0,
        hr_max=200.0,
        pred_col="pred_mostly_nan",
    )
    assert "pred_mostly_nan" in out2[0].columns

    out3 = phys._predict_with_params(
        [base],
        hr_min=60.0,
        mp=0.1,
        k_plus=0.01,
        k_minus=0.01,
        k_e=np.nan,
        hr_max=200.0,
        pred_col="pred_nan_target",
    )
    assert "pred_nan_target" in out3[0].columns
