"""Aggregierte Ergebnis-Zusammenfassung eines Validierungslaufs."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List

from app.models.issue import ValidationIssue


@dataclass
class ValidationSummary:
    total: int = 0
    errors: int = 0
    warnings: int = 0
    by_template: Dict[str, int] = field(default_factory=dict)
    by_rule_type: Dict[str, int] = field(default_factory=dict)
    by_rule_level: Dict[str, int] = field(default_factory=dict)
    templates_validated: List[str] = field(default_factory=list)
    validation_time: str = ""

    @classmethod
    def from_issues(
        cls,
        issues: Iterable[ValidationIssue],
        templates_validated: Iterable[str],
    ) -> "ValidationSummary":
        issues = list(issues)
        by_template: Dict[str, int] = defaultdict(int)
        by_type: Dict[str, int] = defaultdict(int)
        by_level: Dict[str, int] = defaultdict(int)
        errors = warnings = 0
        for it in issues:
            by_template[it.template] += 1
            by_type[it.rule_type] += 1
            by_level[it.rule_level] += 1
            if it.severity == "ERROR":
                errors += 1
            elif it.severity == "WARNING":
                warnings += 1
        return cls(
            total=len(issues),
            errors=errors,
            warnings=warnings,
            by_template=dict(by_template),
            by_rule_type=dict(by_type),
            by_rule_level=dict(by_level),
            templates_validated=sorted(templates_validated),
            validation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def to_dict(self) -> Dict:
        return {
            "total": self.total,
            "errors": self.errors,
            "warnings": self.warnings,
            "by_template": self.by_template,
            "by_rule_type": self.by_rule_type,
            "by_rule_level": self.by_rule_level,
            "templates_validated": self.templates_validated,
            "validation_time": self.validation_time,
        }
