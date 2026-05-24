"""Hilfen für Zahlen-/Missing-Erkennung."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from app.utils.iso_lists import MISSING_STRINGS


def is_missing(val: Any) -> bool:
    """Robuste Missing-Erkennung (deckt NaN, NA, NaT, leere und Sondersymbole)."""
    try:
        if pd.isna(val):
            return True
    except (TypeError, ValueError):
        pass
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in MISSING_STRINGS


def safe_float(val: Any) -> Optional[float]:
    if is_missing(val):
        return None
    try:
        return float(str(val).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None
