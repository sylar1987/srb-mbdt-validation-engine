"""Missing-Handling: leere Strings/Markers → ``pd.NA``."""

from __future__ import annotations

import pandas as pd


def replace_blank_with_na(df: pd.DataFrame) -> pd.DataFrame:
    """Ersetzt leere Strings, ``"None"`` und ``"nan"`` durch ``pd.NA``."""
    if df is None or df.empty:
        return df
    return df.replace({"": pd.NA, "None": pd.NA, "nan": pd.NA})
