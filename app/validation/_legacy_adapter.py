"""Adapter, der einzelne Regeln über die Legacy-Engine ausführt.

Phase 1 lässt die fachliche Auswertung bewusst in ``MBDTValidator`` und
übersetzt deren Dict-Errors in ``ValidationIssue``-Objekte. So bleibt
Verhalten 1:1 erhalten, während die Architektur bereits modular ist.
"""

from __future__ import annotations

from typing import List

from app.models import RuleDefinition, ValidationIssue
from app.validation.context import ValidationContext


def _run_legacy_rule(ctx: ValidationContext, rule: RuleDefinition) -> List[ValidationIssue]:
    """Führt eine einzelne Regel über den Legacy-Validator aus und liefert
    die *neu* entstandenen Issues als ``ValidationIssue``-Liste zurück."""
    legacy = ctx.legacy_validator
    if legacy is None:
        return []

    # Sync legacy state with current context
    legacy.templates = ctx.batch.templates
    legacy.de_annex = ctx.de_annex
    legacy.reference_date = ctx.reference_date
    legacy.codelists = ctx.catalog.codelists
    legacy.field_codelist_map = ctx.catalog.field_codelist_map

    before = len(legacy.errors)
    raw = rule.to_legacy_dict()
    level = rule.rule_level
    if level == "CROSS":
        legacy._validate_cross_template_rule(raw)
    elif level in ("L1", "L2", "CL", "DPM"):
        legacy._validate_single_template_rule(raw)
    elif level == "DQ":
        legacy._validate_dq_rule(raw)
    new_errors = legacy.errors[before:]
    return [ValidationIssue.from_dict(e) for e in new_errors]
