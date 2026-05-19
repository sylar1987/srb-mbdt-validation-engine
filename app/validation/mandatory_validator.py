"""L1: Pflichtfeldregeln (MANDATORY_FIELD)."""

from __future__ import annotations

from typing import List

from app.models import RuleDefinition, ValidationIssue
from app.validation._legacy_adapter import _run_legacy_rule
from app.validation.context import ValidationContext


def handles(rule: RuleDefinition) -> bool:
    return rule.rule_level == "L1" and rule.rule_type == "MANDATORY_FIELD"


def validate(ctx: ValidationContext, rule: RuleDefinition) -> List[ValidationIssue]:
    return _run_legacy_rule(ctx, rule)
