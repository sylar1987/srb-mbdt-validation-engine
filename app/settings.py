"""Zentrale Pfade und Defaults für die Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
CATALOG_PATH: Path = REPO_ROOT / "rule_catalog.json"
FIELD_STRUCTURE_PATH: Path = REPO_ROOT / "field_structure.json"
DEFAULT_OUTPUT_DIR: Path = REPO_ROOT / "output"


@dataclass
class EngineSettings:
    """Laufzeit-Konfiguration für einen Validierungslauf."""

    catalog_path: Path = CATALOG_PATH
    field_structure_path: Path = FIELD_STRUCTURE_PATH
    output_dir: Path = DEFAULT_OUTPUT_DIR
    de_annex: bool = False
    entity_name: str = ""
    reference_date: str = ""
    quiet: bool = False
    extra: dict = field(default_factory=dict)
