"""Einzelner Datenpunkt -> ``CanonicalFact``."""

from __future__ import annotations

from typing import Any, Mapping

from app.models import CanonicalFact, Context, DataPointDefinition
from app.transformation.dimension_mapper import DimensionMapper
from app.transformation.unit_builder import UnitBuilder


class FactMapper:
    def __init__(
        self,
        dimension_mapper: DimensionMapper | None = None,
        unit_builder: UnitBuilder | None = None,
    ) -> None:
        self._dim = dimension_mapper or DimensionMapper()
        self._unit = unit_builder or UnitBuilder()

    def map(
        self,
        datapoint: DataPointDefinition,
        row: Mapping[str, Any],
        row_index: int,
        source_file: str,
        context: Context,
        metadata_version: str,
        validation_status: str = "VALID",
    ) -> CanonicalFact | None:
        if not datapoint.field_code:
            return None
        value = row.get(datapoint.field_code)
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None

        unit = self._unit.resolve(datapoint, row)
        dimensions = self._dim.map(datapoint, row)
        fact_id = f"{datapoint.template_id}:{datapoint.field_code}:{row_index}"
        return CanonicalFact(
            fact_id=fact_id,
            datapoint_id=datapoint.datapoint_id,
            template_id=datapoint.template_id,
            field_code=datapoint.field_code,
            value=value,
            data_type=datapoint.data_type,
            unit=unit,
            context=context,
            dimensions=dimensions,
            source_row=row_index,
            source_file=source_file,
            validation_status=validation_status,
            metadata_version=metadata_version,
        )
