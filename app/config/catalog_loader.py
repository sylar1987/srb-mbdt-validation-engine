"""Lädt JSON-Konfigurationen (Regelkatalog, Feldstruktur)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.models.rule import RuleDefinition
from app.settings import CATALOG_PATH, FIELD_STRUCTURE_PATH


@dataclass
class Catalog:
    """Geladene Konfiguration: typisierte Regeln + Roh-JSON für Legacy-Zugriff."""

    rules: List[RuleDefinition] = field(default_factory=list)
    codelists: Dict[str, list] = field(default_factory=dict)
    field_codelist_map: Dict[str, str] = field(default_factory=dict)
    raw_rules: List[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def apply_de_annex(self) -> None:
        """Überschreibt CL-Listen analog zum bisherigen Verhalten im DE-Modus."""
        if "DE_Nature of the liability" in self.codelists:
            self.codelists["Nature of the liability"] = self.codelists[
                "DE_Nature of the liability"
            ]
        if "DE_Balance sheet item according to national GAAP" in self.codelists:
            self.codelists["Balance sheet item according to national GAAP"] = self.codelists[
                "DE_Balance sheet item according to national GAAP"
            ]


def load_catalog(
    catalog_path: Path = CATALOG_PATH, de_annex: bool = False
) -> Catalog:
    """Lädt ``rule_catalog.json`` und liefert ein typisiertes ``Catalog``-Objekt."""
    path = Path(catalog_path)
    if not path.exists():
        raise FileNotFoundError(f"Regelkatalog nicht gefunden: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    raw_rules = list(data.get("rules", []))
    rules = [RuleDefinition.from_dict(r) for r in raw_rules]

    catalog = Catalog(
        rules=rules,
        codelists=dict(data.get("codelists", {})),
        field_codelist_map=dict(data.get("field_codelist_map", {})),
        raw_rules=raw_rules,
        metadata=dict(data.get("metadata", {})),
    )
    if de_annex:
        catalog.apply_de_annex()
    return catalog


def load_field_structure(path: Path = FIELD_STRUCTURE_PATH) -> Optional[dict]:
    """Lädt ``field_structure.json`` (optional)."""
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)
