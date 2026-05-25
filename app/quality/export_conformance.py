"""Conformance-Checks für Phase-3-Exportpakete (AP 4.4).

MVP-Strategie: kontrollierte Findings statt harter OIM-Vollvalidierung.
Geprüft werden Strukturmerkmale, die ein zukünftiger OIM-Export
ohnehin braucht: ``report.json``-/``metadata.json``-Referenz, Filing
Indicator, Taxonomie-Referenz, Hash-Konsistenz im Manifest.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConformanceLevel:
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"

    ALL = (INFO, WARN, ERROR)


@dataclass
class ConformanceFinding:
    code: str
    level: str
    message: str
    location: str = ""

    def __post_init__(self) -> None:
        if self.level not in ConformanceLevel.ALL:
            raise ValueError(f"unsupported conformance level '{self.level}'")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConformanceReport:
    package_dir: str
    findings: List[ConformanceFinding] = field(default_factory=list)
    checked_files: List[str] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.level == ConformanceLevel.ERROR)

    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.level == ConformanceLevel.WARN)

    def has_errors(self) -> bool:
        return self.error_count() > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_dir": self.package_dir,
            "findings": [f.to_dict() for f in self.findings],
            "checked_files": list(self.checked_files),
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
        }


class ExportConformanceChecker:
    """Prüft Phase-3-Exportverzeichnisse auf OIM-Annäherung.

    Erwartet die MVP-Layout-Struktur ``facts.csv``, ``metadata.json``,
    ``parameters.csv`` plus optional ``manifest.json`` und ``audit.json``.
    Fehlt etwas, wird ein expliziter Finding mit Code emittiert, kein
    Crash — Conformance ist ein Bericht, kein Killer.
    """

    def check(self, package_dir: str) -> ConformanceReport:
        directory = Path(package_dir)
        report = ConformanceReport(package_dir=str(directory))

        if not directory.exists() or not directory.is_dir():
            report.findings.append(
                ConformanceFinding(
                    code="CONF000",
                    level=ConformanceLevel.ERROR,
                    message=f"package directory not found: {directory}",
                )
            )
            return report

        facts = directory / "facts.csv"
        metadata = directory / "metadata.json"
        params = directory / "parameters.csv"
        manifest = directory / "manifest.json"
        audit = directory / "audit.json"
        report_json = directory / "report.json"  # OIM-Zielname

        if facts.exists():
            report.checked_files.append(facts.name)
        else:
            report.findings.append(
                ConformanceFinding(
                    code="CONF001",
                    level=ConformanceLevel.ERROR,
                    message="facts.csv missing",
                    location=facts.name,
                )
            )

        metadata_payload: Optional[Dict[str, Any]] = None
        if metadata.exists():
            report.checked_files.append(metadata.name)
            try:
                metadata_payload = json.loads(metadata.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                report.findings.append(
                    ConformanceFinding(
                        code="CONF010",
                        level=ConformanceLevel.ERROR,
                        message=f"metadata.json not parseable: {exc}",
                        location=metadata.name,
                    )
                )
        else:
            report.findings.append(
                ConformanceFinding(
                    code="CONF002",
                    level=ConformanceLevel.ERROR,
                    message="metadata.json missing",
                    location=metadata.name,
                )
            )

        if params.exists():
            report.checked_files.append(params.name)
        else:
            report.findings.append(
                ConformanceFinding(
                    code="CONF003",
                    level=ConformanceLevel.WARN,
                    message="parameters.csv missing",
                    location=params.name,
                )
            )

        if metadata_payload is not None:
            for required in ("framework_version", "package_id", "metadata_version"):
                if not metadata_payload.get(required):
                    report.findings.append(
                        ConformanceFinding(
                            code="CONF020",
                            level=ConformanceLevel.ERROR,
                            message=f"metadata.json: required field '{required}' missing or empty",
                            location=metadata.name,
                        )
                    )
            if "filing_indicators" not in metadata_payload:
                report.findings.append(
                    ConformanceFinding(
                        code="CONF030",
                        level=ConformanceLevel.WARN,
                        message="metadata.json: filing_indicators not declared (OIM compatibility)",
                        location=metadata.name,
                    )
                )
            if "taxonomy_reference" not in metadata_payload:
                report.findings.append(
                    ConformanceFinding(
                        code="CONF031",
                        level=ConformanceLevel.WARN,
                        message="metadata.json: taxonomy_reference not declared (OIM compatibility)",
                        location=metadata.name,
                    )
                )

        if not report_json.exists():
            report.findings.append(
                ConformanceFinding(
                    code="CONF040",
                    level=ConformanceLevel.INFO,
                    message="report.json not present — OIM-style entry document still on roadmap",
                    location=report_json.name,
                )
            )

        if manifest.exists():
            report.checked_files.append(manifest.name)
            try:
                manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                report.findings.append(
                    ConformanceFinding(
                        code="CONF050",
                        level=ConformanceLevel.ERROR,
                        message=f"manifest.json not parseable: {exc}",
                        location=manifest.name,
                    )
                )
            else:
                if "artifacts" not in manifest_payload:
                    report.findings.append(
                        ConformanceFinding(
                            code="CONF051",
                            level=ConformanceLevel.WARN,
                            message="manifest.json: artifacts section missing",
                            location=manifest.name,
                        )
                    )

        if audit.exists():
            report.checked_files.append(audit.name)

        return report
