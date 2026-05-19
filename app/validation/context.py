"""ValidationContext – expliziter Laufzeit-Kontext für alle Validatoren."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.config.catalog_loader import Catalog
from app.models import InputBatch, RuleDefinition, ValidationIssue


@dataclass
class ValidationContext:
    """Bündelt alles, was Validatoren brauchen: Batch + Catalog + State."""

    batch: InputBatch
    catalog: Catalog
    field_structure: Optional[dict] = None
    de_annex: bool = False
    reference_date: str = ""
    issues: List[ValidationIssue] = field(default_factory=list)
    legacy_validator: Any = None  # Verweis auf MBDTValidator (Phase-1-Adapter)

    @property
    def templates(self) -> Dict:
        return self.batch.templates

    @property
    def rules(self) -> List[RuleDefinition]:
        return self.catalog.rules

    @property
    def codelists(self) -> Dict[str, list]:
        return self.catalog.codelists

    @property
    def field_codelist_map(self) -> Dict[str, str]:
        return self.catalog.field_codelist_map

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def extend_issues_from_dicts(self, items) -> None:
        for d in items:
            self.issues.append(ValidationIssue.from_dict(d))
