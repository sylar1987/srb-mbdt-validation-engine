"""Phase-4-Quality-Layer.

Conformance-Checks, Metadata-Acceptance-Gates und Vorstufen einer
Regression-Suite. Vermeidet bewusst eine harte OIM-Vollvalidierung —
der MVP liefert klare Findings, keine generische Taxonomieprüfung.
"""

from app.quality.catalog_conformance import (
    CatalogConformanceReport,
    CatalogFinding,
    check_catalog,
)
from app.quality.export_conformance import (
    ExportConformanceChecker,
    ConformanceFinding,
    ConformanceReport,
    ConformanceLevel,
)
from app.quality.metadata_acceptance import (
    MetadataAcceptanceChecker,
    AcceptanceFinding,
    AcceptanceReport,
)
from app.quality.rule_test_generator import (
    RuleTestRequirement,
    generate_rule_test_requirements,
)
from app.quality.regression_suite import (
    RegressionCase,
    RegressionSuite,
    RegressionRunResult,
)

__all__ = [
    "CatalogConformanceReport",
    "CatalogFinding",
    "check_catalog",
    "ExportConformanceChecker",
    "ConformanceFinding",
    "ConformanceReport",
    "ConformanceLevel",
    "MetadataAcceptanceChecker",
    "AcceptanceFinding",
    "AcceptanceReport",
    "RuleTestRequirement",
    "generate_rule_test_requirements",
    "RegressionCase",
    "RegressionSuite",
    "RegressionRunResult",
]
