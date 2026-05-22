"""Prediction algorithms extracted from notebook.py."""

from .arx_no_fuite import (
    prediction_arx_with_prev_rides_no_fuite as prediction_arx_with_prev_rides_no_fuite,
)
from .arx_selected import (
    prediction_arx_from_selected_ride as prediction_arx_from_selected_ride,
)
from .default_model import prediction as prediction
from .historical_model import prediction_with_prev_rides as prediction_with_prev_rides
from .physiologic import (
    infer_cyclist_hr_max as infer_cyclist_hr_max,
    prediction_physiologic as prediction_physiologic,
)

__all__ = [
    "prediction_arx_with_prev_rides_no_fuite",
    "prediction_arx_from_selected_ride",
    "prediction",
    "prediction_with_prev_rides",
    "infer_cyclist_hr_max",
    "prediction_physiologic",
]
