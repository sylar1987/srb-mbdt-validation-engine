"""Metadatenqualitätsprüfung für ein ``MetadataPackage``.

Liefert eine strukturierte Diagnose; fehlerhafte/unvollständige Pakete
führen nicht zu Exceptions, sondern zu kontrollierten Findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.models import MetadataPackage


@dataclass
class QualityFinding:
    severity: str  # ERROR | WARN | INFO
    code: str
    message: str

    def to_dict(self) -> dict:
        return {"severity": self.severity, "code": self.code, "message": self.message}


@dataclass
class QualityReport:
    package_id: str
    findings: List[QualityFinding] = field(default_factory=list)

    def has_errors(self) -> bool:
        return any(f.severity == "ERROR" for f in self.findings)

    def to_dict(self) -> dict:
        return {
            "package_id": self.package_id,
            "error_count": sum(1 for f in self.findings if f.severity == "ERROR"),
            "warn_count": sum(1 for f in self.findings if f.severity == "WARN"),
            "findings": [f.to_dict() for f in self.findings],
        }


class MetadataQualityChecker:
    def check(self, package: MetadataPackage) -> QualityReport:
        report = QualityReport(package_id=package.package_id)

        if not package.framework_version:
            report.findings.append(
                QualityFinding("ERROR", "MD001", "framework_version missing")
            )

        dp_ids = {dp.datapoint_id for dp in package.datapoints}
        if not dp_ids:
            report.findings.append(
                QualityFinding("ERROR", "MD010", "package has no datapoints")
            )

        cl_ids = {cl.codelist_id for cl in package.codelists}
        for dp in package.datapoints:
            if dp.codelist_id and dp.codelist_id not in cl_ids:
                report.findings.append(
                    QualityFinding(
                        "ERROR",
                        "MD020",
                        f"datapoint {dp.datapoint_id} references unknown codelist {dp.codelist_id}",
                    )
                )

        for tpl in package.templates:
            for dp_id in tpl.datapoint_ids:
                if dp_id not in dp_ids:
                    report.findings.append(
                        QualityFinding(
                            "ERROR",
                            "MD030",
                            f"template {tpl.template_id} references unknown datapoint {dp_id}",
                        )
                    )

        rule_ids: list[str] = []
        for rule in package.rules:
            if rule.rule_id in rule_ids:
                report.findings.append(
                    QualityFinding(
                        "ERROR", "MD040", f"duplicate rule_id {rule.rule_id}"
                    )
                )
            rule_ids.append(rule.rule_id)
            if not rule.metadata.get("translatable", True):
                report.findings.append(
                    QualityFinding(
                        "WARN",
                        "MD041",
                        f"rule {rule.rule_id} not translatable: {rule.metadata.get('translation_error', '')}",
                    )
                )

        for diag in package.diagnostics:
            report.findings.append(QualityFinding("WARN", "MD099", diag))

        return report
