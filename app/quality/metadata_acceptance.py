"""Metadata-Acceptance-Gate vor Approval (AP 4.2).

Aggregiert harte Mindestanforderungen, die ein ``MetadataPackage``
erfüllen muss, bevor der Approval-Workflow überhaupt sinnvoll greift.
Schließt damit eine Lücke zwischen dem feinkörnigen ``MetadataQualityChecker``
und dem reinen Statusmodell.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

from app.models import MetadataPackage


@dataclass
class AcceptanceFinding:
    code: str
    level: str  # ERROR | WARN
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AcceptanceReport:
    package_id: str
    framework_version: str
    findings: List[AcceptanceFinding] = field(default_factory=list)

    def has_errors(self) -> bool:
        return any(f.level == "ERROR" for f in self.findings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "framework_version": self.framework_version,
            "findings": [f.to_dict() for f in self.findings],
            "error_count": sum(1 for f in self.findings if f.level == "ERROR"),
            "warning_count": sum(1 for f in self.findings if f.level == "WARN"),
        }


class MetadataAcceptanceChecker:
    """Liefert ``AcceptanceReport`` — Eingang in den Approval-Workflow."""

    def __init__(self, min_datapoints: int = 1, min_templates: int = 1) -> None:
        self._min_datapoints = min_datapoints
        self._min_templates = min_templates

    def check(self, package: MetadataPackage) -> AcceptanceReport:
        report = AcceptanceReport(
            package_id=package.package_id,
            framework_version=package.framework_version,
        )

        if not package.framework_version:
            report.findings.append(
                AcceptanceFinding("ACCEPT001", "ERROR", "framework_version missing")
            )

        if len(package.datapoints) < self._min_datapoints:
            report.findings.append(
                AcceptanceFinding(
                    "ACCEPT002",
                    "ERROR",
                    f"datapoint count {len(package.datapoints)} below threshold {self._min_datapoints}",
                )
            )

        if len(package.templates) < self._min_templates:
            report.findings.append(
                AcceptanceFinding(
                    "ACCEPT003",
                    "ERROR",
                    f"template count {len(package.templates)} below threshold {self._min_templates}",
                )
            )

        if not package.rules:
            report.findings.append(
                AcceptanceFinding("ACCEPT004", "WARN", "no rules registered for package")
            )
        else:
            untranslatable = [
                getattr(r, "rule_id", "?") for r in package.rules
                if isinstance(getattr(r, "metadata", {}), dict)
                and getattr(r, "metadata", {}).get("translatable") is False
            ]
            if untranslatable:
                report.findings.append(
                    AcceptanceFinding(
                        "ACCEPT005",
                        "WARN",
                        f"{len(untranslatable)} untranslatable rules: {', '.join(sorted(untranslatable))}",
                    )
                )

        codelist_ids = {c.codelist_id for c in package.codelists}
        for dp in package.datapoints:
            if dp.codelist_id and dp.codelist_id not in codelist_ids:
                report.findings.append(
                    AcceptanceFinding(
                        "ACCEPT006",
                        "ERROR",
                        f"datapoint {dp.datapoint_id} references unknown codelist {dp.codelist_id}",
                    )
                )

        return report
