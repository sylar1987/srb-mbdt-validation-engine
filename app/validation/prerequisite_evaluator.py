"""Prerequisite-Evaluator – Phase 2: DSL/AST mit Phase-1-Fallback.

Die Funktion ``evaluate`` versucht zunächst, den ``prerequisite``-Text in
einen DSL-Ausdruck zu übersetzen (``RuleDefinitionV2.translate_legacy_prerequisite``)
und über die DSL-Engine auszuwerten. Gelingt das nicht, fällt sie auf die
ursprüngliche Phase-1-Heuristik zurück.

Ziele:
  - Keine Regression: für die Mustermenge aus ``rule_catalog.json``
    liefert die DSL dieselben Ergebnisse wie die Heuristik.
  - Transparenz: nicht abbildbare Prerequisites werden über das Logging
    bzw. den Diagnose-Mechanismus sichtbar gemacht; sie laufen über den
    Fallback, nicht stillschweigend als ``True``.
  - Auditierbarkeit: das letzte Diagnosis-Objekt pro Aufruf ist über
    ``last_diagnostics()`` abrufbar.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import pandas as pd

from app.models.rule_v2 import translate_legacy_prerequisite
from app.normalization.headers import find_column
from app.rules_language import EvaluationContext
from app.rules_language import evaluate as dsl_eval
from app.rules_language.diagnostics import DSLError, Diagnostic, DiagnosticCode


logger = logging.getLogger(__name__)

_LAST_DIAGNOSTICS: List[Diagnostic] = []


def last_diagnostics() -> List[Diagnostic]:
    """Diagnosen des letzten ``evaluate``-Aufrufs (Read-only)."""
    return list(_LAST_DIAGNOSTICS)


def evaluate(
    df: pd.DataFrame,
    row_idx: int,
    prerequisite: str,
    rule: Dict[str, Any],
    *,
    templates: Optional[Dict[str, pd.DataFrame]] = None,
    current_template: str = "",
) -> bool:
    """Gibt ``True`` zurück, wenn die Regel auf dieser Zeile angewendet werden soll."""
    global _LAST_DIAGNOSTICS
    _LAST_DIAGNOSTICS = []

    if not prerequisite:
        return True

    dsl_expr = translate_legacy_prerequisite(prerequisite)
    if dsl_expr is not None and dsl_expr != "":
        try:
            ctx = EvaluationContext(
                df=df,
                row_index=row_idx,
                templates=templates or {},
                current_template=current_template,
            )
            result = dsl_eval(dsl_expr, ctx)
            _LAST_DIAGNOSTICS = list(ctx.diagnostics)
            return bool(result)
        except DSLError as exc:
            _LAST_DIAGNOSTICS = [exc.diagnostic]
            # Unbekannte Felder/Templates dürfen nicht still verschluckt
            # werden, sonst maskieren wir echte Datenprobleme. Wir loggen
            # und fallen anschließend auf die Heuristik zurück, damit das
            # Verhalten gegenüber Phase 1 stabil bleibt.
            logger.debug(
                "DSL-Prerequisite-Auswertung fehlgeschlagen, fallback: %s "
                "(rule_id=%s, prerequisite=%r)",
                exc.diagnostic,
                rule.get("rule_id", "<?>"),
                prerequisite,
            )

    return _legacy_evaluate(df, row_idx, prerequisite)


_CROSS_TEMPLATE_REF = re.compile(
    r"\b[A-Za-z]\d+(?:\.\d+)*\.c\d{1,4}\b", re.IGNORECASE
)
_LOCAL_FIELD_EQ = re.compile(
    r"(?<![A-Za-z0-9_.])c(\d{1,4})\s*=\s*['\"]?([^'\"]+)['\"]?",
    re.IGNORECASE,
)


def _legacy_evaluate(df: pd.DataFrame, row_idx: int, prerequisite: str) -> bool:
    """Phase-1-Heuristik. Bleibt als sicherer Fallback erhalten.

    Cross-Template-Referenzen (z. B. ``B02.00.c0040 = "ISIN"``) werden hier
    NICHT als lokale Feldprüfung interpretiert. Wenn die Heuristik einen
    Cross-Ref sieht, dokumentiert sie das in den Diagnosen und liefert
    konservativ ``True`` (Phase-1-Verhalten: keine stille Unterdrückung von
    Issues), damit der Aufrufer Tools/Tests bemerken kann, dass die DSL hier
    hätte greifen müssen.
    """
    prereq_lower = prerequisite.lower()

    if _CROSS_TEMPLATE_REF.search(prerequisite):
        _LAST_DIAGNOSTICS.append(
            Diagnostic(
                DiagnosticCode.UNKNOWN_TEMPLATE,
                "Cross-Template-Referenz im Legacy-Fallback nicht auswertbar: "
                f"{prerequisite!r}. DSL-Pfad bevorzugt; Heuristik verweigert "
                "lokale Substring-Auswertung, um falsche Treffer zu vermeiden.",
            )
        )
        return True

    field_match = _LOCAL_FIELD_EQ.search(prerequisite)
    if field_match:
        cond_col_code = f"c{field_match.group(1).zfill(4)}"
        cond_val = field_match.group(2).strip()
        actual_col = find_column(df, cond_col_code)
        if actual_col and row_idx < len(df):
            actual_val = str(df[actual_col].iloc[row_idx]).strip()
            return cond_val.lower() in actual_val.lower()
        return False

    if "non-structured" in prereq_lower:
        col = find_column(df, "c0250")
        if col and row_idx < len(df):
            return "non-structured" in str(df[col].iloc[row_idx]).lower()

    if "structured" in prereq_lower and "non-structured" not in prereq_lower:
        col = find_column(df, "c0250")
        if col and row_idx < len(df):
            v = str(df[col].iloc[row_idx]).lower()
            return "structured" in v and "non-structured" not in v

    # Wenn weder DSL noch Heuristik die Bedingung erkennen, dokumentieren wir
    # das in den Diagnosen, antworten aber konservativ mit True (Phase-1-
    # Verhalten beibehalten, um keine Issues zu unterdrücken).
    _LAST_DIAGNOSTICS.append(
        Diagnostic(
            DiagnosticCode.UNSUPPORTED_FN,
            f"Prerequisite weder DSL- noch heuristik-erkennbar: {prerequisite!r}",
        )
    )
    return True


UNSUPPORTED_PATTERNS_DOC = """
Phase 2 / DSL deckt jetzt ab:
  - Gleichheit / Ungleichheit auf c-Feldern (= , == , != , <> , < , <= , > , >=)
  - Mengen-Mitgliedschaft (in / not in) und (\"A\" OR \"B\")-Syntaxen
  - Boolesche Verknüpfung mit and/or/not inkl. Klammern
  - Funktionen: is_null, is_not_null, is_reported, abs, min, max, len, lower, upper
  - Cross-Template-Referenzen (Bxx.xx.cNNNN)

Bleibt bewusst Phase-1-Fallback / nicht abgedeckt:
  - Frei-formulierte natürliche Sprache ohne strukturelles Muster
  - Aggregationen über Zeilen (SUM, COUNT)
  - Regex/Like
  - Datumsarithmetik
"""
