"""Mappt Werte aus einer Datenzeile auf die Dimensionen eines Datenpunkts."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from app.models import DataPointDefinition


class DimensionMapper:
    """Heuristisches MVP-Mapping.

    Bekannte Dimensionen:
      - ENTITY -> ``c0010`` (LEI)
      - PERIOD -> ``c0020`` (Reporting Date)
      - UNIT   -> ``c0030`` (Currency)
    """

    DEFAULT_DIMENSION_FIELDS: Dict[str, str] = {
        "ENTITY": "c0010",
        "PERIOD": "c0020",
        "UNIT": "c0030",
    }

    def map(
        self,
        datapoint: DataPointDefinition,
        row: Mapping[str, Any],
        dimension_fields: Dict[str, str] | None = None,
    ) -> Dict[str, str]:
        fields = dimension_fields or self.DEFAULT_DIMENSION_FIELDS
        out: Dict[str, str] = {}
        for dim in datapoint.dimensions:
            field_code = fields.get(dim, "")
            if not field_code:
                continue
            value = row.get(field_code)
            if value is None or str(value).strip() == "":
                continue
            out[dim] = str(value).strip()
        return out
