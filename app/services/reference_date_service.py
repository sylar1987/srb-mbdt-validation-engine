"""Reference Date aus B99.00 c0070 extrahieren."""

from __future__ import annotations

from typing import Optional

from app.normalization.headers import find_column
from app.utils.numeric import is_missing


def extract_reference_date(templates: dict) -> Optional[str]:
    """Extrahiert das Reference Date aus B99.00 (Spalte c0070, erste Zeile)."""
    b99 = templates.get("B99.00")
    if b99 is None or b99.empty:
        return None
    ref_col = find_column(b99, "c0070")
    if ref_col is None:
        return None
    ref_val = b99.iloc[0][ref_col]
    if is_missing(ref_val):
        return None
    return str(ref_val).strip()[:10]
