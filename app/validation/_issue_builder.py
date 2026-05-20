"""Hilfen zum Bauen von ``ValidationIssue`` aus Regel + Befund.

Ziel: Native Validatoren bauen Issues 1:1 mit demselben Schlüsselsatz wie
der Legacy-Adapter, damit Reporting und Tests stabil bleiben.
"""

from __future__ import annotations

from typing import Any, Optional

from app.models import RuleDefinition, ValidationIssue


def build_issue(
    rule: RuleDefinition,
    template: str,
    *,
    row: Optional[int] = None,
    value: Any = None,
    message: str = "",
    explanation: Optional[str] = None,
    severity: Optional[str] = None,
    rule_type: Optional[str] = None,
) -> ValidationIssue:
    """Erzeugt ein ``ValidationIssue`` aus Regeldefinition und Befunddetails."""
    return ValidationIssue(
        rule_id=rule.rule_id,
        rule_level=rule.rule_level,
        rule_type=rule_type or rule.rule_type,
        template=template,
        severity=severity or rule.severity or "ERROR",
        row=row,
        field_code=rule.field_code or "",
        field_label=rule.field_label or "",
        value=("" if value is None else str(value)[:200]),
        message=message,
        explanation=explanation if explanation is not None else (rule.explanation or ""),
        dpm_reference=rule.dpm_reference or "",
    )
