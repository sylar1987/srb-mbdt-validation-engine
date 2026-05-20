"""Strukturprüfung gegen ``field_structure.json``.

Phase 1.5: Diese Prüfung läuft *vor* dem regelgetriebenen Dispatcher.
Sie meldet unbekannte Templates, unbekannte Felder und fehlende Pflicht-
spalten auf Strukturebene als ``ValidationIssue`` mit ``rule_level =
STRUCTURE``. So wird ``field_structure.json`` produktiv konsumiert.

Bewusst keine zeilenbasierte Pflichtfeldprüfung – dafür ist
``mandatory_validator`` (Regelkatalog) zuständig.
"""

from __future__ import annotations

from typing import List

from app.models import FieldStructure, ValidationIssue
from app.validation.context import ValidationContext


def _split_base(template_key: str) -> str:
    """``B02.00_TypeA`` → ``B02.00``; identisch für Templates ohne Variante."""
    return template_key.split("_", 1)[0] if "_" in template_key else template_key


def validate_structure(ctx: ValidationContext) -> List[ValidationIssue]:
    """Liefert Strukturbefunde gegen das typisierte Field-Structure-Modell."""
    structure: FieldStructure | None = ctx.field_structure_model
    if structure is None or not structure.templates:
        return []

    issues: List[ValidationIssue] = []

    for tpl_key, df in ctx.batch.templates.items():
        base_id = _split_base(tpl_key)
        tpl_struct = structure.get(base_id)
        if tpl_struct is None:
            issues.append(
                ValidationIssue(
                    rule_id="STRUCT_001",
                    rule_level="STRUCTURE",
                    rule_type="UNKNOWN_TEMPLATE",
                    template=tpl_key,
                    severity="WARNING",
                    message=(
                        f"Template '{tpl_key}' ist in field_structure.json "
                        "nicht beschrieben."
                    ),
                )
            )
            continue

        known_codes = set(tpl_struct.known_field_codes())
        df_cols = set(df.columns)

        for col in df_cols:
            if not col.startswith("c"):
                continue
            if col not in known_codes:
                issues.append(
                    ValidationIssue(
                        rule_id="STRUCT_002",
                        rule_level="STRUCTURE",
                        rule_type="UNKNOWN_FIELD",
                        template=tpl_key,
                        severity="WARNING",
                        field_code=col,
                        message=(
                            f"Feld '{col}' im Template '{tpl_key}' ist in "
                            "field_structure.json nicht beschrieben."
                        ),
                    )
                )

        for fd in tpl_struct.mandatory_fields():
            if fd.field_code not in df_cols:
                issues.append(
                    ValidationIssue(
                        rule_id="STRUCT_003",
                        rule_level="STRUCTURE",
                        rule_type="MISSING_MANDATORY_COLUMN",
                        template=tpl_key,
                        severity="ERROR",
                        field_code=fd.field_code,
                        field_label=fd.label,
                        message=(
                            f"Pflichtspalte '{fd.field_code}' ({fd.label}) "
                            f"fehlt im Template '{tpl_key}'."
                        ),
                    )
                )

    return issues
