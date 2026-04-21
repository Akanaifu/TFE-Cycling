"""FIT import helpers for manual upload workflow.

Converts uploaded .fit files to the project PKL schema:
- t  : elapsed time in seconds
- hr : heart rate (bpm)
- po : power (watts)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import tempfile

import numpy as np
import pandas as pd


def _load_fit_file_class():
    try:
        from fit_tool.fit_file import FitFile
    except Exception as exc:
        raise RuntimeError(
            "Missing dependency fit-tool. Install it in backend environment."
        ) from exc
    return FitFile


def convert_name_file(file_name: str) -> str:
    """Create standardized PKL filename from original FIT filename.

    Input example:
    - 2026-04-10-170547-WAHOOAPPIOS2047-13-0.fit

    Output example:
    - 2026-04-10T17_05_47.000000000.pkl
    """
    filename = Path(file_name).name
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})-(\d{6})", filename)

    if match:
        date_str = "-".join([match.group(1), match.group(2), match.group(3)])
        time_str = match.group(4)
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S")
    else:
        # Keep canonical format even when source filename is non-standard.
        dt = datetime.now(timezone.utc).replace(tzinfo=None)

    return dt.strftime("%Y-%m-%dT%H_%M_%S.000000000.pkl")


def _row_to_record_dict(row: pd.Series) -> dict[str, str]:
    record: dict[str, str] = {}
    for i in range(26):
        field_col = f"Field {i}"
        value_col = f"Value {i}"
        field_name = row.get(field_col)
        value = row.get(value_col)
        if pd.notna(field_name) and str(field_name).strip() != "":
            record[str(field_name).strip()] = value
    return record


def convert_fit_to_project_df(fit_path: str | Path) -> pd.DataFrame:
    """Convert a FIT file to project DataFrame format (t, hr, po)."""
    fit_path = Path(fit_path)
    if not fit_path.exists() or not fit_path.is_file():
        raise FileNotFoundError(f"FIT file not found: {fit_path}")

    FitFile = _load_fit_file_class()

    tmp_csv_handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    )
    tmp_csv_path = Path(tmp_csv_handle.name)
    tmp_csv_handle.close()

    try:
        fit_file = FitFile.from_file(str(fit_path))
        fit_file.to_csv(str(tmp_csv_path))

        raw = pd.read_csv(tmp_csv_path, dtype=str)
        records = raw[raw["Message"].eq("record")].copy()
        if records.empty:
            raise ValueError("No 'record' messages found in FIT output.")

        rec_df = pd.DataFrame(records.apply(_row_to_record_dict, axis=1).tolist())

        for col in ["timestamp", "distance", "heart_rate"]:
            if col in rec_df.columns:
                rec_df[col] = pd.to_numeric(rec_df[col], errors="coerce")

        if "timestamp" in rec_df.columns and rec_df["timestamp"].notna().any():
            ts = rec_df["timestamp"]
            epoch_like = ts >= 1_000_000_000_000
            if epoch_like.any():
                rec_df = rec_df.loc[epoch_like].reset_index(drop=True)
                ts = rec_df["timestamp"]

            first_ts = ts.dropna().iloc[0]
            t = (ts - first_ts) / 1000.0
        else:
            t = pd.Series(np.arange(len(rec_df), dtype=float))

        out_df = pd.DataFrame(
            {
                "t": t,
                "hr": (
                    rec_df["heart_rate"] if "heart_rate" in rec_df.columns else np.nan
                ),
                "po": rec_df["power"] if "power" in rec_df.columns else np.nan,
            }
        )

        out_df = out_df.reindex(columns=["t", "hr", "po"]).drop(
            columns=["cad", "d"], errors="ignore"
        )
        out_df = out_df.dropna(subset=["t"]).reset_index(drop=True)

        if out_df.empty:
            raise ValueError("Converted DataFrame is empty after cleanup.")

        return out_df
    finally:
        try:
            if tmp_csv_path.exists():
                tmp_csv_path.unlink()
        except Exception:
            pass
