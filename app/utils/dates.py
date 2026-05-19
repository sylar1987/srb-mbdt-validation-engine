"""Datums-Hilfen."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Optional

from app.utils.numeric import is_missing


def parse_date(val: Any) -> Optional[_dt.date]:
    if is_missing(val):
        return None
    if isinstance(val, _dt.datetime):
        return val.date()
    if isinstance(val, _dt.date):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    return None
