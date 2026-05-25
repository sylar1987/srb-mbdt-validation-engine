"""Phase-3-Metadata-Pipeline.

Liest EBA-/SRB-ähnliche Pakete (MVP-Fixture-Format) ein und überführt
sie in ein internes, versionsfähiges Metadatenmodell.

Sub-Module:
  - package_locator: Erkennt Paket-Ablagen
  - package_reader: Liest Manifest und Rohdateien
  - dpm_extractor: Datenpunkte
  - taxonomy_extractor: Templates/Dimensionen
  - validation_rule_extractor: Regeln -> RuleDefinitionV2
  - codelist_extractor: Codelists
  - glossary_extractor: Glossarbegriffe
  - metadata_mapper: Mappt Roh-Objekte in MetadataPackage und leitet
    interne Konfigurationen ab
  - metadata_repository: Immutable Ablage geladener Packages
  - metadata_versioning: Delta-Analyse zwischen zwei Packages
  - metadata_quality: DQ-/Konsistenzdiagnose
"""

from app.metadata.package_locator import PackageLocator, PackageLocation
from app.metadata.package_reader import PackageReader, RawPackage
from app.metadata.dpm_extractor import DpmExtractor
from app.metadata.taxonomy_extractor import TaxonomyExtractor
from app.metadata.validation_rule_extractor import ValidationRuleExtractor
from app.metadata.codelist_extractor import CodelistExtractor
from app.metadata.glossary_extractor import GlossaryExtractor
from app.metadata.metadata_mapper import MetadataMapper
from app.metadata.metadata_repository import MetadataRepository
from app.metadata.metadata_versioning import MetadataVersioning, PackageDelta
from app.metadata.metadata_quality import MetadataQualityChecker, QualityReport

__all__ = [
    "PackageLocator",
    "PackageLocation",
    "PackageReader",
    "RawPackage",
    "DpmExtractor",
    "TaxonomyExtractor",
    "ValidationRuleExtractor",
    "CodelistExtractor",
    "GlossaryExtractor",
    "MetadataMapper",
    "MetadataRepository",
    "MetadataVersioning",
    "PackageDelta",
    "MetadataQualityChecker",
    "QualityReport",
]
