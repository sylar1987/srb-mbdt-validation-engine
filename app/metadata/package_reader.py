"""Liest die Rohartefakte eines lokalisierten Pakets.

Ergebnis: ``RawPackage`` mit den unverarbeiteten Strukturen. Erst die
Extractoren transformieren diese in Domänenobjekte.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.metadata.package_locator import PackageLocation


@dataclass
class RawPackage:
    """Unverarbeitete Inhalte eines Pakets."""

    location: PackageLocation
    manifest: Dict[str, Any] = field(default_factory=dict)
    datapoints_rows: List[Dict[str, Any]] = field(default_factory=list)
    templates_rows: List[Dict[str, Any]] = field(default_factory=list)
    codelists_rows: List[Dict[str, Any]] = field(default_factory=list)
    dimensions_rows: List[Dict[str, Any]] = field(default_factory=list)
    rules_payload: Dict[str, Any] = field(default_factory=dict)
    glossary: Dict[str, str] = field(default_factory=dict)
    diagnostics: List[str] = field(default_factory=list)


class PackageReader:
    """Liest die in ``manifest.json`` referenzierten Dateien.

    Unterstützte Formate (MVP):
      - CSV mit ``;``-Trennzeichen (UTF-8, optional BOM)
      - JSON
    """

    def read(self, location: PackageLocation) -> RawPackage:
        raw = RawPackage(location=location)
        try:
            with open(location.manifest_path, "r", encoding="utf-8") as fh:
                raw.manifest = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raw.diagnostics.append(f"manifest unreadable: {exc}")
            return raw

        files = raw.manifest.get("files") or {}

        if "datapoints" in files:
            raw.datapoints_rows = self._read_csv(location.path, files["datapoints"], raw)
        if "templates" in files:
            raw.templates_rows = self._read_csv(location.path, files["templates"], raw)
        if "codelists" in files:
            raw.codelists_rows = self._read_csv(location.path, files["codelists"], raw)
        if "dimensions" in files:
            raw.dimensions_rows = self._read_csv(location.path, files["dimensions"], raw)
        if "rules" in files:
            raw.rules_payload = self._read_json(location.path, files["rules"], raw) or {}
        if "glossary" in files:
            glossary = self._read_json(location.path, files["glossary"], raw) or {}
            if isinstance(glossary, dict):
                raw.glossary = {str(k): str(v) for k, v in glossary.items()}
            else:
                raw.diagnostics.append("glossary file is not a JSON object")
        return raw

    def _read_csv(
        self, base: str, filename: str, raw: RawPackage
    ) -> List[Dict[str, Any]]:
        path = os.path.join(base, filename)
        if not os.path.isfile(path):
            raw.diagnostics.append(f"missing file: {filename}")
            return []
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh, delimiter=";")
                return [dict(row) for row in reader]
        except OSError as exc:
            raw.diagnostics.append(f"cannot read {filename}: {exc}")
            return []

    def _read_json(
        self, base: str, filename: str, raw: RawPackage
    ) -> Optional[Any]:
        path = os.path.join(base, filename)
        if not os.path.isfile(path):
            raw.diagnostics.append(f"missing file: {filename}")
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raw.diagnostics.append(f"cannot parse {filename}: {exc}")
            return None
