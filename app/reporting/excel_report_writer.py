"""Excel-Fehlerreport schreiben.

Phase 1 nutzt die bestehende, sehr ausführliche Formatierung in
``MBDTValidator.generate_error_report``. Der Writer stellt einen
modul-orientierten Einstiegspunkt bereit, der ausschließlich auf
``ValidationIssue``-Objekten arbeitet.
"""

from __future__ import annotations

from typing import Iterable, List

from app.models import ValidationIssue


def write_excel_report(
    legacy_validator,
    issues: Iterable[ValidationIssue],
    output_path: str,
    entity_name: str = "",
    reference_date: str = "",
) -> str:
    """Erzeugt den Excel-Report aus einer Liste ``ValidationIssue``.

    Der Writer setzt ``legacy_validator.errors`` so, dass das bestehende
    Layout (Deckblatt, Fehlerdetails, Zusammenfassung, Regelkatalog)
    erhalten bleibt – aber alles wird aus den ``ValidationIssue``-Objekten
    rekonstruiert. Reporting ist damit nur noch Consumer.
    """
    legacy_validator.errors = [i.to_dict() for i in issues]
    return legacy_validator.generate_error_report(
        output_path=output_path,
        entity_name=entity_name,
        reference_date=reference_date,
    )
