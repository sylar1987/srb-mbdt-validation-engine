"""Erkennt regulatorische Metadaten-Pakete im Dateisystem.

MVP: Ein Paket ist ein Verzeichnis mit einer ``manifest.json``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PackageLocation:
    """Beschreibt einen erkannten Paketspeicherort."""

    package_id: str
    framework_version: str
    path: str
    manifest_path: str


class PackageLocator:
    """Findet Pakete an einem gegebenen Ablagepfad."""

    MANIFEST_NAME = "manifest.json"

    def locate(self, path: str) -> Optional[PackageLocation]:
        """Erkennt ein einzelnes Paket an ``path`` (Verzeichnis)."""
        if not path or not os.path.isdir(path):
            return None
        manifest_path = os.path.join(path, self.MANIFEST_NAME)
        if not os.path.isfile(manifest_path):
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None
        package_id = str(manifest.get("package_id") or os.path.basename(path))
        framework_version = str(manifest.get("framework_version") or "")
        return PackageLocation(
            package_id=package_id,
            framework_version=framework_version,
            path=path,
            manifest_path=manifest_path,
        )

    def discover(self, root: str) -> List[PackageLocation]:
        """Scannt ``root`` rekursiv nach Paketen (jeder Ordner mit Manifest)."""
        found: List[PackageLocation] = []
        if not root or not os.path.isdir(root):
            return found
        for dirpath, _dirnames, filenames in os.walk(root):
            if self.MANIFEST_NAME in filenames:
                loc = self.locate(dirpath)
                if loc is not None:
                    found.append(loc)
        found.sort(key=lambda p: (p.framework_version, p.package_id))
        return found
