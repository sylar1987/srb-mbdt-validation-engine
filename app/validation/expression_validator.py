"""Phase-2: Assertion-basierter Regelauswerter (Vorbereitungsstufe).

Dieses Modul wertet ``RuleDefinitionV2`` mit ``condition`` und ``assertion``
generisch über die DSL/AST-Engine aus. In Phase 2 wird es noch **nicht** in
den Standard-Validationspfad eingehängt – das passiert in Phase 3, wenn
DPM-extrahierte Regeln über `RuleDefinitionV2` ankommen. Hier liegt jedoch
die voll funktionsfähige Auswertungsschicht inkl. Tests, sodass DPM-/EBA-
Regeln in Phase 3 ohne weitere Engine-Arbeit anschließen können.

Verwendung (Phase-3-Vorgriff, programmatisch):

    issues = validate_v2(ctx, rule_v2)
"""

from __future__ import annotations

import logging
from typing import List, Optional

import pandas as pd

from app.models import ValidationIssue
from app.models.rule_v2 import RuleDefinitionV2
from app.rules_language import EvaluationContext
from app.rules_language import evaluate as dsl_eval
from app.rules_language.diagnostics import DSLError
from app.services.template_lookup_service import find_matching_keys
from app.validation.context import ValidationContext


logger = logging.getLogger(__name__)


def validate_v2(ctx: ValidationContext, rule: RuleDefinitionV2) -> List[ValidationIssue]:
    """Wertet eine ``RuleDefinitionV2`` gegen den Validierungskontext aus."""
    if rule.scope == "row":
        return _validate_row(ctx, rule)
    if rule.scope == "template":
        return _validate_template(ctx, rule)
    if rule.scope == "cross":
        return _validate_cross(ctx, rule)
    raise ValueError(f"Unsupported scope: {rule.scope}")


def _resolve_target_df(ctx: ValidationContext, rule: RuleDefinitionV2) -> Optional[pd.DataFrame]:
    if not rule.target_template:
        return None
    matching = find_matching_keys(ctx.batch.templates, rule.target_template)
    if not matching:
        return None
    return ctx.batch.templates[matching[0]]


def _validate_row(ctx: ValidationContext, rule: RuleDefinitionV2) -> List[ValidationIssue]:
    df = _resolve_target_df(ctx, rule)
    if df is None:
        return []

    issues: List[ValidationIssue] = []
    for idx in range(len(df)):
        eval_ctx = EvaluationContext(
            df=df,
            row_index=idx,
            templates=dict(ctx.batch.templates),
            current_template=rule.target_template,
        )
        try:
            if rule.condition:
                cond_val = dsl_eval(rule.condition, eval_ctx)
                if not _truthy(cond_val):
                    continue
            if rule.assertion:
                assertion_val = dsl_eval(rule.assertion, eval_ctx)
                if not _truthy(assertion_val):
                    issues.append(_build_issue(rule, idx + 2, df))
        except DSLError as exc:
            logger.debug("DSL error in rule %s row %s: %s", rule.rule_id, idx, exc)
            # Diagnose wird nicht in Standard-Issues übersetzt, um in
            # Phase 2 keine Regressionen für Bestandsregeln zu erzeugen.
            continue
    return issues


def _validate_template(ctx: ValidationContext, rule: RuleDefinitionV2) -> List[ValidationIssue]:
    # Phase-2: Template-Scope = einmaliger Aufruf auf erster Zeile bzw. ohne Zeile.
    df = _resolve_target_df(ctx, rule)
    if df is None:
        return []
    eval_ctx = EvaluationContext(
        df=df,
        row_index=0,
        templates=dict(ctx.batch.templates),
        current_template=rule.target_template,
    )
    try:
        if rule.condition and not _truthy(dsl_eval(rule.condition, eval_ctx)):
            return []
        if rule.assertion and not _truthy(dsl_eval(rule.assertion, eval_ctx)):
            return [_build_issue(rule, None, df)]
    except DSLError as exc:
        logger.debug("DSL error in template-rule %s: %s", rule.rule_id, exc)
    return []


def _validate_cross(ctx: ValidationContext, rule: RuleDefinitionV2) -> List[ValidationIssue]:
    # Cross-Scope: Auswertung über alle Zeilen des target_template; Cross-
    # Template-Lookups laufen über die DSL (`Bxx.xx.cNNNN`).
    return _validate_row(ctx, rule)


def _truthy(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _build_issue(rule: RuleDefinitionV2, row: Optional[int], df: pd.DataFrame) -> ValidationIssue:
    return ValidationIssue(
        rule_id=rule.rule_id,
        rule_level=rule.metadata.get("rule_level", ""),
        rule_type=rule.metadata.get("rule_type", "EXPRESSION"),
        template=rule.target_template,
        severity=rule.severity or "ERROR",
        row=row,
        field_code=rule.metadata.get("field_code", ""),
        field_label=rule.metadata.get("field_label", ""),
        value="",
        message=rule.message or f"Assertion fehlgeschlagen: {rule.assertion}",
        explanation=rule.message or "",
        dpm_reference=rule.metadata.get("dpm_reference", ""),
    )
