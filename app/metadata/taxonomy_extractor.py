"""Extrahiert ``TemplateDefinition`` und ``Dimension`` (MVP-Taxonomie)."""

from __future__ import annotations

from typing import List, Tuple

from app.metadata.package_reader import RawPackage
from app.models import TemplateDefinition, Dimension


class TaxonomyExtractor:
    """Mappt CSV-Zeilen auf Templates und Dimensionen."""

    def extract(
        self, raw: RawPackage
    ) -> Tuple[List[TemplateDefinition], List[Dimension]]:
        version = str(raw.manifest.get("framework_version") or "")
        source = raw.location.package_id

        templates: List[TemplateDefinition] = []
        for row in raw.templates_rows:
            tpl_id = (row.get("template_id") or "").strip()
            if not tpl_id:
                raw.diagnostics.append("template missing template_id, skipped")
                continue
            dps = [
                d.strip()
                for d in (row.get("datapoint_ids") or "").split(",")
                if d.strip()
            ]
            dims = [
                d.strip()
                for d in (row.get("dimensions") or "").split(",")
                if d.strip()
            ]
            templates.append(
                TemplateDefinition(
                    template_id=tpl_id,
                    name=(row.get("name") or "").strip(),
                    description=(row.get("description") or "").strip(),
                    datapoint_ids=dps,
                    dimensions=dims,
                    version=version,
                    source=source,
                )
            )

        dimensions: List[Dimension] = []
        for row in raw.dimensions_rows:
            dim_id = (row.get("dimension_id") or "").strip()
            if not dim_id:
                raw.diagnostics.append("dimension missing dimension_id, skipped")
                continue
            mandatory_raw = (row.get("mandatory") or "").strip().lower()
            dimensions.append(
                Dimension(
                    dimension_id=dim_id,
                    name=(row.get("name") or "").strip(),
                    description=(row.get("description") or "").strip(),
                    codelist_id=(row.get("codelist_id") or "").strip(),
                    mandatory=mandatory_raw in ("true", "1", "yes", "y"),
                )
            )

        return templates, dimensions
