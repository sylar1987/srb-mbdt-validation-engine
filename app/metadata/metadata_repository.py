"""Immutable In-Memory-Ablage geladener ``MetadataPackage``.

Pakete werden über ``package_id`` + ``content_hash`` adressiert. Eine
einmal registrierte Version kann nicht mehr überschrieben werden.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.models import MetadataPackage


class MetadataRepository:
    def __init__(self) -> None:
        self._packages: Dict[Tuple[str, str], MetadataPackage] = {}

    def register(self, package: MetadataPackage) -> str:
        """Registriert ein Paket. Gibt den content_hash zurück.

        Wirft ``ValueError``, wenn dieselbe (package_id, hash)-Kombination
        bereits existiert (Immutability-Garantie).
        """
        key = (package.package_id, package.content_hash())
        if key in self._packages:
            raise ValueError(
                f"package {package.package_id} with hash {key[1]} already registered"
            )
        self._packages[key] = package
        return key[1]

    def get(self, package_id: str, content_hash: Optional[str] = None) -> Optional[MetadataPackage]:
        if content_hash is not None:
            return self._packages.get((package_id, content_hash))
        # Latest registered version for a package_id (insertion order).
        candidates = [pkg for (pid, _h), pkg in self._packages.items() if pid == package_id]
        return candidates[-1] if candidates else None

    def list_versions(self, package_id: str) -> List[MetadataPackage]:
        return [pkg for (pid, _h), pkg in self._packages.items() if pid == package_id]

    def all_packages(self) -> List[MetadataPackage]:
        return list(self._packages.values())

    def __len__(self) -> int:
        return len(self._packages)
