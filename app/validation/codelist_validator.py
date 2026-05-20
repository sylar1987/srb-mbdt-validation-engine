"""CL: Codelisten-Checks (CODELIST_CHECK).

Phase 1.5: Native Auswertung. Codelisten kommen aus
``Catalog.codelists`` über ``rule.codelist_name`` oder den Eintrag in
``field_codelist_map``. Tolerierte Sonderwerte ("Not available", "N/A", …)
bleiben identisch zur Legacy-Logik, damit die Regression nicht bricht.

Legacy-Fallback über ``ctx.use_native_validators = False``.
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

_TOLERATED = frozenset({"Not available", "Not applicable", "N/A", "NA", ""})


def handles(rule: RuleDefinition) -> bool:
    return rule.rule_level == "CL" or rule.rule_type == "CODELIST_CHECK"


def _resolve_codelist_values(ctx: ValidationContext, rule: RuleDefinition) -> List[str]:
    values = list(rule.codelist_values or [])
    if values:
        return values
    cl_name = rule.codelist_name
    if not cl_name:
        cl_name = ctx.catalog.field_codelist_map.get(
            f"{rule.template};{rule.field_code}"
        )
    if cl_name:
        return list(ctx.catalog.codelists.get(cl_name, []))
    return []


def validate(ctx: ValidationContext, rule: RuleDefinition) -> List[ValidationIssue]:
    if not ctx.use_native_validators:
        return _run_legacy_rule(ctx, rule)

    matching = find_matching_keys(ctx.batch.templates, rule.template)
    if not matching:
        return []

    codelist_values = _resolve_codelist_values(ctx, rule)
    if not codelist_values:
        return []

    valid_set = {str(v).strip() for v in codelist_values} | _TOLERATED

    issues: List[ValidationIssue] = []
    for tpl_key in matching:
        df = ctx.batch.templates[tpl_key]
        col = find_column(df, rule.field_code)
        if col is None:
            continue

        for idx, val in enumerate(df[col]):
            if is_missing(val):
                continue
            val_str = str(val).strip()
            if val_str in valid_set:
                continue
            top10 = ", ".join(sorted(codelist_values)[:10])
            ellipsis = "..." if len(codelist_values) > 10 else ""
            issues.append(
                build_issue(
                    rule,
                    template=tpl_key,
                    row=idx + 2,
                    value=val_str,
                    message=(
                        f"Ungültiger Codelist-Wert '{val_str}' in "
                        f"'{rule.field_code}' ({rule.field_label}), "
                        f"Zeile {idx + 2}."
                    ),
                    explanation=f"Gültige Werte: {top10}{ellipsis}",
                )
            )

    return issues
