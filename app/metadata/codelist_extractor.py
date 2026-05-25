"""Extrahiert ``CodelistDefinition``."""

from __future__ import annotations

from typing import List

from app.metadata.package_reader import RawPackage
from app.models import CodelistDefinition


class CodelistExtractor:
    """Mappt CSV-Zeilen auf ``CodelistDefinition``."""

    def extract(self, raw: RawPackage) -> List[CodelistDefinition]:
        version = str(raw.manifest.get("framework_version") or "")
        source = raw.location.package_id
        result: List[CodelistDefinition] = []
        for row in raw.codelists_rows:
            cl_id = (row.get("codelist_id") or "").strip()
            if not cl_id:
                raw.diagnostics.append("codelist missing codelist_id, skipped")
                continue
            values = [
                v.strip()
                for v in (row.get("values") or "").split(",")
                if v.strip()
            ]
            result.append(
                CodelistDefinition(
                    codelist_id=cl_id,
                    name=(row.get("name") or "").strip(),
                    description=(row.get("description") or "").strip(),
                    values=values,
                    version=version,
                    source=source,
                )
            )
        return result
