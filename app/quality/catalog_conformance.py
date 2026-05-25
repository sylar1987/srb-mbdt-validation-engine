"""Katalog-Konformitätsprüfung – auflösbare Feldreferenzen.

Prüft jede Regel in ``rule_catalog.json`` darauf, ob ihr ``field_code``
gegen die ``field_structure.json`` desselben Templates auflösbar ist.

Findings adressieren genau die Klassen von Fehlern, die in der
Problembeschreibung des Nutzers genannt sind:

* ``MISSING_FIELD_CODE``      – Regel hat keinen technischen Code.
* ``NON_TECHNICAL_FIELD_CODE``– ``field_code`` sieht nicht wie ``cNNNN`` aus
                                (z. B. Caption-only).
* ``UNKNOWN_FIELD_CODE``      – Code ist syntaktisch korrekt, kommt aber im
                                Template-Feldgerüst nicht vor.
* ``UNKNOWN_TEMPLATE``        – Template ist nicht in ``field_structure.json``.
* ``LABEL_MISMATCH``          – Code in FS bekannt, aber ``field_label`` weicht
                                stark vom FS-Label ab (nur Warnung).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Mapping, Optional


_RE_TECHNICAL = re.compile(r"^c\d{3,5}$", re.IGNORECASE)


@dataclass(frozen=True)
class CatalogFinding:
    rule_id: str
    template: str
    field_code: str
    field_label: str
    code: str  # finding code, e.g. UNKNOWN_FIELD_CODE
    message: str


@dataclass
class CatalogConformanceReport:
    findings: List[CatalogFinding] = field(default_factory=list)
    rules_checked: int = 0
    rules_resolved: int = 0

    @property
    def is_clean(self) -> bool:
        return not any(f.code != "LABEL_MISMATCH" for f in self.findings)

    def by_code(self, code: str) -> List[CatalogFinding]:
        return [f for f in self.findings if f.code == code]


def _fs_codes_and_labels(field_structure_raw: Mapping[str, Any], tpl: str):
    """Liefert ``(codes_set_lower, label_by_code_lower)`` für ein Template."""
    entries = field_structure_raw.get(tpl, []) or []
    codes: set[str] = set()
    labels: dict[str, str] = {}
    for e in entries:
        c = str(e.get("field_code") or e.get("code") or "").strip()
        if not c:
            continue
        codes.add(c.lower())
        labels[c.lower()] = str(e.get("label") or "")
    return codes, labels


def _normalize_label(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def check_catalog(
    rule_catalog: Mapping[str, Any],
    field_structure_raw: Mapping[str, Any],
) -> CatalogConformanceReport:
    """Prüft den Regelkatalog gegen die Feldstruktur."""
    rules: Iterable[Mapping[str, Any]] = rule_catalog.get("rules", []) or []
    report = CatalogConformanceReport()

    for r in rules:
        report.rules_checked += 1
        rid = str(r.get("rule_id", "?"))
        tpl = str(r.get("template", "")).strip()
        fc = str(r.get("field_code", "")).strip()
        flabel = str(r.get("field_label", "")).strip()

        if not fc:
            report.findings.append(
                CatalogFinding(rid, tpl, fc, flabel, "MISSING_FIELD_CODE",
                               "Regel ohne field_code.")
            )
            continue

        # Multi-Template-Templates (z. B. "B02.00/B90.00") nicht hart prüfen;
        # auf erste Template-ID reduzieren.
        primary_tpl = tpl.split("/")[0].split(" ")[0]
        if not primary_tpl:
            report.findings.append(
                CatalogFinding(rid, tpl, fc, flabel, "UNKNOWN_TEMPLATE",
                               "Regel ohne template-Angabe.")
            )
            continue

        if not _RE_TECHNICAL.match(fc):
            report.findings.append(
                CatalogFinding(
                    rid, tpl, fc, flabel, "NON_TECHNICAL_FIELD_CODE",
                    f"field_code '{fc}' ist nicht im cNNNN-Format.",
                )
            )
            continue

        if primary_tpl not in field_structure_raw:
            report.findings.append(
                CatalogFinding(
                    rid, tpl, fc, flabel, "UNKNOWN_TEMPLATE",
                    f"Template '{primary_tpl}' nicht in field_structure.json.",
                )
            )
            continue

        codes, labels = _fs_codes_and_labels(field_structure_raw, primary_tpl)
        if fc.lower() not in codes:
            report.findings.append(
                CatalogFinding(
                    rid, tpl, fc, flabel, "UNKNOWN_FIELD_CODE",
                    f"field_code '{fc}' nicht in Template '{primary_tpl}'.",
                )
            )
            continue

        report.rules_resolved += 1

        fs_label = labels.get(fc.lower(), "")
        if (
            flabel
            and fs_label
            and _normalize_label(flabel) != _normalize_label(fs_label)
        ):
            # Nur weicher Hinweis. Manche Captions weichen redaktionell ab
            # (z. B. "Non-Structured/Vanilla" vs. "Non-Structured" im FS).
            report.findings.append(
                CatalogFinding(
                    rid, tpl, fc, flabel, "LABEL_MISMATCH",
                    f"Caption '{flabel}' weicht vom FS-Label '{fs_label}' ab.",
                )
            )

    return report
