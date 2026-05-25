"""Einheiten-Auflösung über Datenpunkt und ggf. Fallback-Spalten."""

from __future__ import annotations

from typing import Any, Mapping

from app.models import DataPointDefinition


class UnitBuilder:
    def resolve(
        self,
        datapoint: DataPointDefinition,
        row: Mapping[str, Any],
        currency_field: str = "c0030",
    ) -> str:
        """Auflösung in dieser Reihenfolge:

        1. ``datapoint.unit``
        2. Wert aus ``currency_field`` (falls vorhanden), z. B. ``c0030``
        3. leerer String
        """
        if datapoint.unit:
            return datapoint.unit
        if currency_field and currency_field in row:
            val = row.get(currency_field)
            if val is not None and str(val).strip():
                return str(val).strip()
        return ""
