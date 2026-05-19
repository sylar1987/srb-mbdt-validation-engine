"""Wert-Normalisierung."""

from __future__ import annotations

import pandas as pd


def normalize_dataframe_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Wandelt das DataFrame durchgehend in String-Werte um und behandelt
    Missing-Symbole konsistent (kompatibel zum bisherigen XLSX-Pfad)."""
    if df is None:
        return df
    out = df.astype(str).replace("None", pd.NA).replace("nan", pd.NA)
    return out
