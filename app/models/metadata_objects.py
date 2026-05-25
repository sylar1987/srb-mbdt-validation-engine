"""Phase-3-Domänenmodelle für regulatorische Metadaten.

Diese Modelle bilden die interne, versionsfähige Darstellung der aus
EBA-/SRB-Paketen extrahierten Artefakte. Sie sind bewusst als
Dataclasses gehalten, damit sie sich einfach serialisieren, hashen und
zwischen Repository, Mapper und Validierung weiterreichen lassen.

Reuse: Regeln werden auf ``RuleDefinitionV2`` aus Phase 2 abgebildet.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class CodelistDefinition:
    """Eine extrahierte Codelist mit Allowed Values und Versionsbezug."""

    codelist_id: str
    name: str = ""
    description: str = ""
    values: List[str] = field(default_factory=list)
    version: str = ""
    source: str = ""

    def contains(self, value: Any) -> bool:
        if value is None:
            return False
        return str(value) in self.values

    def to_dict(self) -> Dict[str, Any]:
        return {
            "codelist_id": self.codelist_id,
            "name": self.name,
            "description": self.description,
            "values": list(self.values),
            "version": self.version,
            "source": self.source,
        }


@dataclass
class DataPointDefinition:
    """Ein extrahierter DPM-Datenpunkt."""

    datapoint_id: str
    name: str = ""
    template_id: str = ""
    field_code: str = ""
    data_type: str = ""
    cardinality: str = "0..1"
    technical_identifier: str = ""
    description: str = ""
    codelist_id: str = ""
    dimensions: List[str] = field(default_factory=list)
    unit: str = ""
    version: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TemplateDefinition:
    """Eine extrahierte Template-/Tabellenbeschreibung."""

    template_id: str
    name: str = ""
    description: str = ""
    datapoint_ids: List[str] = field(default_factory=list)
    dimensions: List[str] = field(default_factory=list)
    version: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Dimension:
    """Eine Achsen-/Dimensionsbeschreibung."""

    dimension_id: str
    name: str = ""
    description: str = ""
    codelist_id: str = ""
    mandatory: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Unit:
    """Eine Einheit (z. B. Währung, Anzahl)."""

    unit_id: str
    measure: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Context:
    """Kontext (Stichtag, Periode, Entity) eines Fakts."""

    entity: str = ""
    period_start: str = ""
    period_end: str = ""
    scenario: str = ""
    reference_date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetadataPackage:
    """Ein eingelesenes EBA-/SRB-Paket als interne Darstellung."""

    package_id: str
    framework_version: str
    release_date: str = ""
    source_path: str = ""
    hotfix: str = ""
    description: str = ""
    datapoints: List[DataPointDefinition] = field(default_factory=list)
    templates: List[TemplateDefinition] = field(default_factory=list)
    codelists: List[CodelistDefinition] = field(default_factory=list)
    rules: List[Any] = field(default_factory=list)  # RuleDefinitionV2
    dimensions: List[Dimension] = field(default_factory=list)
    units: List[Unit] = field(default_factory=list)
    glossary: Dict[str, str] = field(default_factory=dict)
    diagnostics: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "framework_version": self.framework_version,
            "release_date": self.release_date,
            "source_path": self.source_path,
            "hotfix": self.hotfix,
            "description": self.description,
            "datapoints": [d.to_dict() for d in self.datapoints],
            "templates": [t.to_dict() for t in self.templates],
            "codelists": [c.to_dict() for c in self.codelists],
            "rules": [
                r.to_dict() if hasattr(r, "to_dict") else dict(r)
                for r in self.rules
            ],
            "dimensions": [d.to_dict() for d in self.dimensions],
            "units": [u.to_dict() for u in self.units],
            "glossary": dict(self.glossary),
            "diagnostics": list(self.diagnostics),
            "created_at": self.created_at,
        }

    def content_hash(self) -> str:
        """Hash über alle fachlichen Inhalte (ohne created_at) für Versionierung."""
        payload = self.to_dict()
        payload.pop("created_at", None)
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def codelist(self, codelist_id: str) -> Optional[CodelistDefinition]:
        for c in self.codelists:
            if c.codelist_id == codelist_id:
                return c
        return None

    def datapoint(self, datapoint_id: str) -> Optional[DataPointDefinition]:
        for d in self.datapoints:
            if d.datapoint_id == datapoint_id:
                return d
        return None

    def template(self, template_id: str) -> Optional[TemplateDefinition]:
        for t in self.templates:
            if t.template_id == template_id:
                return t
        return None


@dataclass
class CanonicalFact:
    """Exportfähiger, validierter Datenpunkt."""

    fact_id: str
    datapoint_id: str
    template_id: str
    field_code: str
    value: Any
    data_type: str = ""
    unit: str = ""
    context: Context = field(default_factory=Context)
    dimensions: Dict[str, str] = field(default_factory=dict)
    source_row: int = -1
    source_file: str = ""
    validation_status: str = "VALID"
    metadata_version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "datapoint_id": self.datapoint_id,
            "template_id": self.template_id,
            "field_code": self.field_code,
            "value": self.value,
            "data_type": self.data_type,
            "unit": self.unit,
            "context": self.context.to_dict(),
            "dimensions": dict(self.dimensions),
            "source_row": self.source_row,
            "source_file": self.source_file,
            "validation_status": self.validation_status,
            "metadata_version": self.metadata_version,
        }


@dataclass
class ExportArtifact:
    """Ein einzelnes geschriebenes Exportartefakt (Datei)."""

    filename: str
    content_type: str
    size_bytes: int = 0
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExportPackage:
    """Das technische Zielpaket (XML/xBRL-CSV + Manifest + Audit)."""

    package_id: str
    export_format: str  # "xml" | "xbrl-csv"
    metadata_version: str
    rule_version: str = ""
    rule_count: int = 0
    input_hash: str = ""
    run_id: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    )
    facts: List[CanonicalFact] = field(default_factory=list)
    artifacts: List[ExportArtifact] = field(default_factory=list)
    validation_issues: List[str] = field(default_factory=list)
    status: str = "PENDING"  # PENDING | VALIDATED | REJECTED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "export_format": self.export_format,
            "metadata_version": self.metadata_version,
            "rule_version": self.rule_version,
            "rule_count": self.rule_count,
            "input_hash": self.input_hash,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "fact_count": len(self.facts),
            "artifacts": [a.to_dict() for a in self.artifacts],
            "validation_issues": list(self.validation_issues),
            "status": self.status,
        }
