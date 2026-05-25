"""Baut aus ``TemplateData`` + ``MetadataPackage`` eine Liste von ``CanonicalFact``."""

from __future__ import annotations

from typing import List, Optional

from app.models import (
    CanonicalFact,
    Context,
    MetadataPackage,
    TemplateData,
)
from app.transformation.context_builder import ContextBuilder
from app.transformation.fact_mapper import FactMapper


class CanonicalModelBuilder:
    def __init__(
        self,
        fact_mapper: Optional[FactMapper] = None,
        context_builder: Optional[ContextBuilder] = None,
    ) -> None:
        self._fact_mapper = fact_mapper or FactMapper()
        self._context_builder = context_builder or ContextBuilder()

    def build(
        self,
        template_data: TemplateData,
        package: MetadataPackage,
        reference_date: str = "",
        entity: str = "",
    ) -> List[CanonicalFact]:
        tpl = package.template(template_data.template_id)
        if tpl is None:
            return []

        # Datenpunkte des Templates auflösen.
        datapoints = [
            dp for dp in package.datapoints if dp.datapoint_id in tpl.datapoint_ids
        ]
        if not datapoints:
            return []

        facts: List[CanonicalFact] = []
        df = template_data.df
        if df is None or df.empty:
            return []

        for row_index, row in df.iterrows():
            row_map = {col: row.get(col) for col in df.columns}
            row_entity = entity or self._safe_str(row_map.get("c0010"))
            row_date = reference_date or self._safe_str(row_map.get("c0020"))
            context: Context = self._context_builder.build(
                entity=row_entity,
                reference_date=row_date,
            )
            for dp in datapoints:
                fact = self._fact_mapper.map(
                    datapoint=dp,
                    row=row_map,
                    row_index=int(row_index),
                    source_file=template_data.source_name,
                    context=context,
                    metadata_version=package.framework_version,
                )
                if fact is not None:
                    facts.append(fact)
        return facts

    @staticmethod
    def _safe_str(value) -> str:
        if value is None:
            return ""
        try:
            text = str(value)
        except Exception:  # noqa: BLE001
            return ""
        return text.strip() if isinstance(text, str) else ""
