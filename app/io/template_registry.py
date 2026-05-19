"""Mapping zwischen Sheetnamen und normalisierten Template-IDs."""

from __future__ import annotations

from typing import Optional

TEMPLATE_SHEET_MAP: dict[str, str] = {
    "B9900": "B99.00", "B0100": "B01.00", "B0200": "B02.00",
    "B0300": "B03.00", "B0400": "B04.00", "B0500": "B05.00",
    "B0600": "B06.00", "B9000": "B90.00",
    "B99.00": "B99.00", "B01.00": "B01.00", "B02.00": "B02.00",
    "B03.00": "B03.00", "B04.00": "B04.00", "B05.00": "B05.00",
    "B06.00": "B06.00", "B90.00": "B90.00",
}


def normalize_sheet_name(sheet_name: str) -> Optional[str]:
    """Liefert die kanonische Template-ID für ein Sheet oder ``None``."""
    return TEMPLATE_SHEET_MAP.get(sheet_name)
