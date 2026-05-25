"""Extrahiert ``DataPointDefinition`` aus ``RawPackage.datapoints_rows``."""

from __future__ import annotations

from typing import List

from app.metadata.package_reader import RawPackage
from app.models import DataPointDefinition


class DpmExtractor:
    """Mappt CSV-Zeilen auf ``DataPointDefinition``."""

    def extract(self, raw: RawPackage) -> List[DataPointDefinition]:
        version = str(raw.manifest.get("framework_version") or "")
        source = raw.location.package_id
        result: List[DataPointDefinition] = []
        for row in raw.datapoints_rows:
            dp_id = (row.get("datapoint_id") or "").strip()
            if not dp_id:
                raw.diagnostics.append("datapoint missing datapoint_id, skipped")
                continue
            dims = [
                d.strip()
                for d in (row.get("dimensions") or "").split(",")
                if d.strip()
            ]
            result.append(
                DataPointDefinition(
                    datapoint_id=dp_id,
                    name=(row.get("name") or "").strip(),
                    template_id=(row.get("template_id") or "").strip(),
                    field_code=(row.get("field_code") or "").strip(),
                    data_type=(row.get("data_type") or "").strip(),
                    cardinality=(row.get("cardinality") or "0..1").strip(),
                    technical_identifier=(row.get("technical_identifier") or "").strip(),
                    description=(row.get("description") or "").strip(),
                    codelist_id=(row.get("codelist_id") or "").strip(),
                    dimensions=dims,
                    unit=(row.get("unit") or "").strip(),
                    version=version,
                    source=source,
                )
            )
        return result
