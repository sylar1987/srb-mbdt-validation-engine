"""Datenklassen für die Validierungsengine (Phasen 1–3)."""

from app.models.batch import InputBatch
from app.models.template_data import TemplateData
from app.models.rule import RuleDefinition
from app.models.rule_v2 import RuleDefinitionV2, map_legacy_rule, translate_legacy_prerequisite
from app.models.issue import ValidationIssue
from app.models.summary import ValidationSummary
from app.models.field_structure import FieldStructure, TemplateStructure, FieldDefinition
from app.models.metadata_objects import (
    MetadataPackage,
    DataPointDefinition,
    TemplateDefinition,
    CodelistDefinition,
    Dimension,
    Unit,
    Context,
    CanonicalFact,
    ExportArtifact,
    ExportPackage,
)

__all__ = [
    "InputBatch",
    "TemplateData",
    "RuleDefinition",
    "RuleDefinitionV2",
    "map_legacy_rule",
    "translate_legacy_prerequisite",
    "ValidationIssue",
    "ValidationSummary",
    "FieldStructure",
    "TemplateStructure",
    "FieldDefinition",
    "MetadataPackage",
    "DataPointDefinition",
    "TemplateDefinition",
    "CodelistDefinition",
    "Dimension",
    "Unit",
    "Context",
    "CanonicalFact",
    "ExportArtifact",
    "ExportPackage",
]
