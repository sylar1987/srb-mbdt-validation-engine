"""DPM: Datentyp- und Formatprüfungen.

Phase 1.5: Native Auswertung über ``utils.regex_patterns`` und ISO-Listen.
Die Regelzuordnung erfolgt über ``rule.test_type`` (numeric / date /
iso 3166 / iso 4217 / lei). Verhalten ist bewusst 1:1 zur Legacy-Logik
gehalten, damit Regressionstests grün bleiben.

Legacy-Fallback über ``ctx.use_native_validators = False``.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from app.models import RuleDefinition, ValidationIssue
from app.normalization.headers import find_column
from app.services.template_lookup_service import find_matching_keys
from app.utils.iso_lists import ISO_3166_COUNTRIES, ISO_4217_CURRENCIES
from app.utils.numeric import is_missing
from app.utils.regex_patterns import DATE_RE, ISO_3166_2_RE, LEI_RE
from app.validation._issue_builder import build_issue
from app.validation._legacy_adapter import _run_legacy_rule
from app.validation.context import ValidationContext


def handles(rule: RuleDefinition) -> bool:
    return rule.rule_level == "DPM" and rule.rule_type in (
        "DATATYPE_CHECK",
        "FORMAT_CHECK",
    )


def _numeric_check(val_str: str) -> Optional[str]:
    try:
        float(val_str.replace(",", "").replace(" ", ""))
        return None
    except (ValueError, TypeError):
        return f"Kein Zahlenwert: '{val_str}'."


def _date_check(val_str: str) -> Optional[str]:
    if DATE_RE.match(val_str):
        return None
    return f"Ungültiges Datum: '{val_str}'. Erwartet: yyyy-mm-dd."


def _iso_country_check(val_str: str) -> Optional[str]:
    upper = val_str.upper()
    if upper in ISO_3166_COUNTRIES or ISO_3166_2_RE.match(upper):
        return None
    return f"Ungültiger Ländercode: '{val_str}'."


def _iso_currency_check(val_str: str) -> Optional[str]:
    if val_str.upper() in ISO_4217_CURRENCIES:
        return None
    return f"Ungültiger ISO 4217 Währungscode: '{val_str}'."


def _lei_check(val_str: str) -> Optional[str]:
    if LEI_RE.match(val_str.upper()):
        return None
    return (
        f"Ungültiges LEI-Format: '{val_str}'. "
        "Erwartet: 20 alphanumerische Zeichen (ISO 17442)."
    )


def _select_checker(test_type: str) -> tuple[Optional[Callable[[str], Optional[str]]], str]:
    """Liefert (check_fn, ausgegebener rule_type) für die Regel.

    Spezifische Tokens (lei, iso 3166, iso 4217) werden vor allgemeinen
    Tokens (numeric, date) geprüft, damit z. B. ``"LEI format check
    (20 alphanumeric characters)"`` nicht über das Substring ``numeric``
    auf ``_numeric_check`` misrouted wird.
    """
    t = test_type.lower()
    if "lei" in t:
        return _lei_check, "FORMAT_CHECK"
    if "iso 3166" in t or ("country" in t and "iso" in t):
        return _iso_country_check, "FORMAT_CHECK"
    if "iso 4217" in t or "currency" in t:
        return _iso_currency_check, "FORMAT_CHECK"
    if "numeric" in t:
        return _numeric_check, "DATATYPE_CHECK"
    if "date" in t:
        return _date_check, "DATATYPE_CHECK"
    return None, "DATATYPE_CHECK"


def validate(ctx: ValidationContext, rule: RuleDefinition) -> List[ValidationIssue]:
    if not ctx.use_native_validators:
        return _run_legacy_rule(ctx, rule)

    check_fn, out_rule_type = _select_checker(rule.test_type)
    if check_fn is None:
        # Unbekannter test_type → kein nativer Fall, Legacy abfragen.
        return _run_legacy_rule(ctx, rule)

    matching = find_matching_keys(ctx.batch.templates, rule.template)
    if not matching:
        return []

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
            err = check_fn(val_str)
            if err is None:
                continue
            issues.append(
                build_issue(
                    rule,
                    template=tpl_key,
                    row=idx + 2,
                    value=val_str,
                    rule_type=out_rule_type,
                    message=(
                        f"{err} Feld '{rule.field_code}' Zeile {idx + 2}."
                    ),
                )
            )

    return issues
