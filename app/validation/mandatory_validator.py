"""L1: Pflichtfeldregeln (MANDATORY_FIELD).

Phase 1.5: Native Auswertung gegen ``RuleDefinition`` + Field-Structure.
Wenn keine Spalte für ``rule.field_code`` im Template gefunden wird, wird
ein Strukturfehler gemeldet. Pro Zeile entscheidet der Prerequisite-Evaluator,
ob die Regel anzuwenden ist; leere Werte führen zu einem Pflichtfeld-Issue.

Legacy-Fallback ist über ``ctx.use_native_validators = False`` erreichbar.
"""

from __future__ import annotations

from typing import List

from app.models import RuleDefinition, ValidationIssue
from app.normalization.headers import find_column
from app.services.template_lookup_service import find_matching_keys
from app.utils.numeric import is_missing
from app.validation._issue_builder import build_issue
from app.validation._legacy_adapter import _run_legacy_rule
from app.validation.context import ValidationContext
from app.validation.prerequisite_evaluator import evaluate as eval_prereq


def handles(rule: RuleDefinition) -> bool:
    return rule.rule_level == "L1" and rule.rule_type == "MANDATORY_FIELD"


def validate(ctx: ValidationContext, rule: RuleDefinition) -> List[ValidationIssue]:
    if not ctx.use_native_validators:
        return _run_legacy_rule(ctx, rule)

    template_id = rule.template
    matching = find_matching_keys(ctx.batch.templates, template_id)
    if not matching:
        return []

    issues: List[ValidationIssue] = []
    for tpl_key in matching:
        df = ctx.batch.templates[tpl_key]
        col = find_column(df, rule.field_code)

        if col is None:
            issues.append(
                build_issue(
                    rule,
                    template=tpl_key,
                    message=(
                        f"Spalte '{rule.field_code}' ({rule.field_label}) "
                        "fehlt im Template."
                    ),
                )
            )
            continue

        prereq = rule.prerequisite
        for idx, val in enumerate(df[col]):
            if not is_missing(val):
                continue
            if prereq and not eval_prereq(
                df,
                idx,
                prereq,
                rule.raw,
                templates=ctx.batch.templates,
                current_template=tpl_key,
            ):
                continue
            issues.append(
                build_issue(
                    rule,
                    template=tpl_key,
                    row=idx + 2,
                    value=None,
                    message=(
                        f"Pflichtfeld leer: '{rule.field_code}' "
                        f"({rule.field_label}) in Zeile {idx + 2}."
                    ),
                )
            )

    return issues
