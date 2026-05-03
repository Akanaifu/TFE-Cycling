from __future__ import annotations

from typing import Any
import warnings

import pandas as pd


def _ml_imports() -> tuple[Any, Any, Any]:
    try:
        from sklearn import linear_model as lm
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing ML dependencies. Install scikit-learn in backend venv."
        ) from exc
    return lm, make_pipeline, StandardScaler


def _warn_and_is_invalid_hr_po(ride: pd.DataFrame, ride_idx: int, context: str) -> bool:
    """Warn and return True when ride misses hr/po or contains only NaN values."""
    issues: list[str] = []
    col_miss = ("po", "hr") if context.find("prediction") == -1 else ("hr")
    for col in col_miss:
        if col not in ride.columns:
            issues.append(f"missing '{col}' column")
            continue
        values = pd.to_numeric(ride[col], errors="coerce")
        if int(values.notna().sum()) == 0:
            issues.append(f"'{col}' column is empty (100% NaN)")

    if issues:
        msg = f"[{context}] ride {ride_idx}: {'; '.join(issues)}. Ride skipped."
        warnings.warn(msg, UserWarning)
        return True
    return False
