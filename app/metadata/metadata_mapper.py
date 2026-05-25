"""Mappt extrahierte Rohinhalte auf ein ``MetadataPackage`` und leitet
interne Konfigurationen (RuleDefinitionV2-Liste, Codelist-Map,
Template-Strukturen) ab.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.metadata.codelist_extractor import CodelistExtractor
from app.metadata.dpm_extractor import DpmExtractor
from app.metadata.glossary_extractor import GlossaryExtractor
from app.metadata.package_reader import RawPackage
from app.metadata.taxonomy_extractor import TaxonomyExtractor
from app.metadata.validation_rule_extractor import ValidationRuleExtractor
from app.models import (
    CodelistDefinition,
    MetadataPackage,
    RuleDefinitionV2,
    TemplateDefinition,
    Unit,
)


@dataclass
class GeneratedConfig:
    """Aus Metadaten abgeleitete interne Laufzeitkonfiguration."""

    rules: List[RuleDefinitionV2]
    codelist_map: Dict[str, CodelistDefinition]
    templates: List[TemplateDefinition]
    untranslatable_rule_ids: List[str]


class MetadataMapper:
    """Orchestriert alle Extractoren und baut ``MetadataPackage``."""

    def __init__(self) -> None:
        self._dpm = DpmExtractor()
        self._tax = TaxonomyExtractor()
        self._rules = ValidationRuleExtractor()
        self._codelist = CodelistExtractor()
        self._glossary = GlossaryExtractor()

    def build_package(self, raw: RawPackage) -> MetadataPackage:
        templates, dimensions = self._tax.extract(raw)
        datapoints = self._dpm.extract(raw)
        codelists = self._codelist.extract(raw)
        rules = self._rules.extract(raw)
        glossary = self._glossary.extract(raw)

        # Units aus Datapoint-Einheitenfeldern ableiten (MVP).
        unit_ids = sorted({dp.unit for dp in datapoints if dp.unit})
        units = [Unit(unit_id=u, measure=u) for u in unit_ids]

        pkg = MetadataPackage(
            package_id=raw.location.package_id,
            framework_version=str(raw.manifest.get("framework_version") or ""),
            release_date=str(raw.manifest.get("release_date") or ""),
            source_path=raw.location.path,
            hotfix=str(raw.manifest.get("hotfix") or ""),
            description=str(raw.manifest.get("description") or ""),
            datapoints=datapoints,
            templates=templates,
            codelists=codelists,
            rules=rules,
            dimensions=dimensions,
            units=units,
            glossary=glossary,
            diagnostics=list(raw.diagnostics),
        )
        return pkg

    def derive_config(self, package: MetadataPackage) -> GeneratedConfig:
        """Aus ``MetadataPackage`` interne Laufzeitkonfiguration ableiten."""
        codelist_map = {c.codelist_id: c for c in package.codelists}
        untranslatable = [
            r.rule_id
            for r in package.rules
            if not r.metadata.get("translatable", True)
        ]
        return GeneratedConfig(
            rules=list(package.rules),
            codelist_map=codelist_map,
            templates=list(package.templates),
            untranslatable_rule_ids=untranslatable,
        )
