"""
SRB Minimum Bail-in Data Template (MBDT) Validierungsengine
Version: 1.4  (DE Country Annex + CL-Erweiterung)
Quelle:  SRB MBDT (published 2024-11-05) + EBA DPM 4.2 + DE Country Annex 2024-11-05

Regeltypen:
  L1    – SRB Level 1 : Pflichtfeld-Checks (Completeness)
  L2    – SRB Level 2 : Interne Konsistenz (Consistency)
  CL    – Codelisten-Prüfungen (Domain-Werte)
  DPM   – EBA DPM 4.2 : Datentyp- & Format-Checks
  CROSS – Cross-Template-Konsistenz (inkl. MREL-Anforderungen)

Behobene Bugs (v1.1):
  BUG-01  Docstring load_xlsx korrigiert
  BUG-02  _find_header_row: Integer-Codes (10, 20 statt '0010') erkannt
  BUG-03  _extract_headers: Deduplizierung doppelter Spaltennamen
  BUG-04  load_xlsx: Zeilenlänge nicht mehr hart auf headers-Länge gestutzt
  BUG-05  _is_missing: nutzt pandas.isna() + robuste NaN/NA-Behandlung
  BUG-06  ISIN-Check: Warnung wenn col_type fehlt
  BUG-07  Unbenutzter 'template'/'test_type' in _validate_cross_template_rule entfernt
  BUG-08  v_CROSS_0007: IndexError-Schutz via len(df02)-Check
  BUG-10  get_summary: sorted Template-IDs
  BUG-11  Unbenutzte Imports entfernt (GradientFill, dataframe_to_rows, os)
  BUG-12  generate_error_report() implementiert (CRITICAL)
  BUG-13  Unbenutztes 'template'/'rule_type' in validate() entfernt
  BUG-14  _check_prerequisite() korrekt implementiert (kein blindes True)
  BUG-16  _extract_headers: robuste Spaltenzuordnung für alle Spaltentypen
  BUG-L2  32 ungematchte L2 test_types abgedeckt:
           "Drop down values", cross-field Formeln, "numeric from 1",
           ISO 3166-2, "equal to zero", "Not applicable must be reported"
"""

from __future__ import annotations

import json
import math
import re
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

warnings.filterwarnings("ignore", category=UserWarning)

# ─────────────────────────────────────────────────────────────────────────────
# Pfade
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
CATALOG_PATH = BASE_DIR / "rule_catalog.json"

# ─────────────────────────────────────────────────────────────────────────────
# ISO-Referenz-Codelisten
# ─────────────────────────────────────────────────────────────────────────────
ISO_4217_CURRENCIES: frozenset[str] = frozenset({
    "EUR","USD","GBP","CHF","JPY","SEK","NOK","DKK","PLN","CZK",
    "HUF","RON","BGN","HRK","ISK","TRY","AUD","CAD","CNY","HKD",
    "SGD","KRW","INR","BRL","MXN","ZAR","RUB","SAR","AED","THB",
    "IDR","MYR","NZD","TWD","ILS","EGP","NGN","PKR","BDT","VND",
    "CLP","COP","ARS","PEN","UAH","KZT","QAR","KWD","BHD","OMR",
    "MAD","TND","DZD","XOF","XAF","GHS","KES","TZS","UGX","ETB",
    "XDR","XAU","XAG",
})

ISO_3166_COUNTRIES: frozenset[str] = frozenset({
    "AT","BE","BG","CY","CZ","DE","DK","EE","ES","FI","FR",
    "GR","HR","HU","IE","IT","LT","LU","LV","MT","NL","PL",
    "PT","RO","SE","SI","SK","AL","BA","BY","CH","GB","IS",
    "LI","MD","ME","MK","NO","RS","RU","TR","UA","XK",
    "US","JP","CN","IN","BR","CA","AU","SG","HK","KR",
    "SA","AE","ZA","NG","EG","KE","MA","MX","AR","CL","CO",
})

# Akzeptierte Fehlenwerte in allen Templates
_MISSING_STRINGS: frozenset[str] = frozenset({
    "", "none", "nan", "nat", "n/a", "na", "not available", "not applicable",
})


# ─────────────────────────────────────────────────────────────────────────────
# Haupt-Klasse
# ─────────────────────────────────────────────────────────────────────────────
class MBDTValidator:
    """
    Validierungsengine für das SRB Minimum Bail-in Data Template (MBDT).
    Unterstützt xlsx (SRB-Originaltemplates) und CSV als Input.
    """

    # Sheet-Name → normalisiertes Template-ID
    TEMPLATE_SHEET_MAP: dict[str, str] = {
        "B9900": "B99.00", "B0100": "B01.00", "B0200": "B02.00",
        "B0300": "B03.00", "B0400": "B04.00", "B0500": "B05.00",
        "B0600": "B06.00", "B9000": "B90.00",
        "B99.00": "B99.00", "B01.00": "B01.00", "B02.00": "B02.00",
        "B03.00": "B03.00", "B04.00": "B04.00", "B05.00": "B05.00",
        "B06.00": "B06.00", "B90.00": "B90.00",
    }

    # Kompilierte Regex-Muster (Klassen-Ebene für Performance)
    DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(\s\d{2}:\d{2}:\d{2})?$")
    ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
    LEI_RE  = re.compile(r"^[0-9A-Z]{20}$")
    # ISO 3166-2 subdivision code (z.B. DE-BY, FR-IDF)
    ISO_3166_2_RE = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}$")

    def __init__(self, catalog_path: Path = CATALOG_PATH, de_annex: bool = False) -> None:
        """
        Parameters
        ----------
        catalog_path : Path
            Pfad zur rule_catalog.json
        de_annex : bool
            True  → DE Country Annex Modus aktivieren:
                    - DE-spezifische Felder und Codelisten werden berücksichtigt
                    - 'de_only'-Regeln werden ausgeführt
                    - 'Nature of the liability' nutzt DE_Nature-Codeliste (inkl. DE_Silent/Profit)
                    - 'Balance sheet national GAAP' nutzt DE_Balance-Codeliste (9 Werte)
            False → Standard MBDT-Regeln (keine DE-spezifischen Felder/Regeln)
        """
        with open(catalog_path, "r", encoding="utf-8") as fh:
            catalog_data = json.load(fh)
        self.de_annex:          bool               = de_annex
        self.rules:             list[dict]         = catalog_data["rules"]
        self.codelists:         dict[str, list]    = catalog_data["codelists"]
        self.field_codelist_map: dict[str, str]    = catalog_data.get("field_codelist_map", {})
        self.errors:            list[dict]         = []
        self.templates:         dict[str, pd.DataFrame] = {}
        self.reference_date: str               = ""

        # DE-Modus: Codelisten-Überschreibungen aktivieren
        if de_annex:
            # Nature of the liability → DE-erweiterte Codeliste (inkl. DE_Silent/Profit)
            if "DE_Nature of the liability" in self.codelists:
                self.codelists["Nature of the liability"] = self.codelists["DE_Nature of the liability"]
            # Balance sheet national GAAP → DE-Codeliste (9 Werte statt 5)
            if "DE_Balance sheet item according to national GAAP" in self.codelists:
                self.codelists["Balance sheet item according to national GAAP"] = (
                    self.codelists["DE_Balance sheet item according to national GAAP"]
                )

    # ══════════════════════════════════════════════════════════════════════════
    # INPUT LOADING
    # ══════════════════════════════════════════════════════════════════════════

    def load_xlsx(self, filepath: str) -> dict[str, pd.DataFrame]:
        """
        Lädt ein MBDT-xlsx-Workbook (SRB Annex I Format).
        Gibt ein Dict {template_id → DataFrame} zurück und setzt self.templates.
        """
        wb = openpyxl.load_workbook(filepath, data_only=True)
        templates: dict[str, pd.DataFrame] = {}

        for sheet_name in wb.sheetnames:
            normalized = self.TEMPLATE_SHEET_MAP.get(sheet_name)
            if not normalized:
                continue
            ws      = wb[sheet_name]
            all_rows = list(ws.iter_rows(values_only=True))
            if not all_rows:
                continue

            # FIX BUG-02/16: Header-Zeile mit Integer- UND String-Codes finden
            header_idx = self._find_header_row(all_rows)
            if header_idx is None:
                continue

            # FIX BUG-16: robuste Header-Extraktion
            headers = self._extract_headers(all_rows, header_idx)
            if not headers:
                continue

            # FIX BUG-04: Datenzeilen nicht hard auf headers-Länge kürzen
            data_rows = []
            for row in all_rows[header_idx + 1:]:
                if any(cell is not None for cell in row):
                    # Pad wenn Zeile kürzer als Header, truncate wenn länger
                    row_list = list(row)
                    if len(row_list) < len(headers):
                        row_list += [None] * (len(headers) - len(row_list))
                    else:
                        row_list = row_list[:len(headers)]
                    data_rows.append(row_list)

            if data_rows:
                df = pd.DataFrame(data_rows, columns=headers)
                # Alle Werte als String speichern (konsistent mit CSV-Input)
                df = df.astype(str).replace("None", pd.NA).replace("nan", pd.NA)
                templates[normalized] = df

        self.templates = templates
        return templates

    def load_csv_dir(self, directory: str) -> dict[str, pd.DataFrame]:
        """
        Lädt CSV-Dateien aus einem Verzeichnis.
        Dateinamen-Konvention: B02.00_TypeA.csv, B02.00_TypeB.csv, B90.00.csv
        Separator: Semikolon (;) gemäß SRB MBDT Annex II §1.1
        """
        templates: dict[str, pd.DataFrame] = {}
        for csv_file in Path(directory).glob("*.csv"):
            m = re.match(r"(B\d{2}\.\d{2})", csv_file.stem)
            if not m:
                continue
            tpl_id = m.group(1)
            suffix = csv_file.stem.replace(tpl_id, "").strip("_")
            key    = f"{tpl_id}_{suffix}" if suffix else tpl_id
            try:
                df = pd.read_csv(
                    csv_file, sep=";", dtype=str,
                    encoding="utf-8-sig", keep_default_na=False
                )
                df.columns = self._normalize_col_names(df.columns.tolist())
                # Leere Strings → pd.NA
                df = df.replace("", pd.NA)
                templates[key] = (
                    pd.concat([templates[key], df], ignore_index=True)
                    if key in templates else df
                )
            except Exception as exc:
                print(f"  WARNUNG: CSV '{csv_file.name}' konnte nicht gelesen werden: {exc}")

        self.templates = templates
        return templates

    def load_single_csv(self, filepath: str, template_id: str) -> pd.DataFrame:
        """Lädt eine einzelne CSV-Datei als spezifisches Template."""
        df = pd.read_csv(
            filepath, sep=";", dtype=str,
            encoding="utf-8-sig", keep_default_na=False
        )
        df.columns = self._normalize_col_names(df.columns.tolist())
        df = df.replace("", pd.NA)
        self.templates[template_id] = df
        return df

    # ══════════════════════════════════════════════════════════════════════════
    # CORE VALIDATION
    # ══════════════════════════════════════════════════════════════════════════

    def validate(self) -> list[dict]:
        """
        Führt alle Validierungsregeln durch.
        Gibt die vollständige Fehlerliste zurück (self.errors wird überschrieben).
        """
        self.errors = []

        if not self.templates:
            self._add_error(
                rule_id="SYS_001", rule_level="SYSTEM", rule_type="SYSTEM",
                template="ALL", row=None, field_code=None, field_label="n/a",
                severity="ERROR", value=None,
                message="Keine Templates geladen. load_xlsx() oder load_csv_dir() aufrufen.",
                explanation="", dpm_reference=""
            )
            return self.errors

        # B99.00 ist Pflicht in jeder Submission
        if "B99.00" not in self.templates:
            self._add_error(
                rule_id="SYS_002", rule_level="SYSTEM", rule_type="MANDATORY_TEMPLATE",
                template="B99.00", row=None, field_code=None, field_label="n/a",
                severity="ERROR", value=None,
                message="B99.00 (Identification of the report) fehlt. Pflicht-Template.",
                explanation="Every MBDT submission must include B99.00.",
                dpm_reference="SRB MBDT Guidance §2.1"
            )

        # CR-04: Reference date aus B99.00 c0070 extrahieren (für DQ-Datumsregeln)
        _b99 = self.templates.get("B99.00")
        if _b99 is not None and not _b99.empty:
            _ref_col = self._find_column(_b99, "c0070")
            if _ref_col is not None:
                _ref_val = _b99.iloc[0][_ref_col]
                if not self._is_missing(_ref_val):
                    self.reference_date = str(_ref_val).strip()[:10]

        # FIX BUG-13: 'rule_type'/'template' nicht lokal extrahieren wenn ungenutzt
        for rule in self.rules:
            # DE-only Regeln nur im DE-Annex-Modus ausführen
            if rule.get("de_only") and not self.de_annex:
                continue
            rule_level = rule.get("rule_level", "")
            if rule_level == "CROSS":
                self._validate_cross_template_rule(rule)
            elif rule_level in ("L1", "L2", "CL", "DPM"):
                self._validate_single_template_rule(rule)
            elif rule_level == "DQ":
                self._validate_dq_rule(rule)

        return self.errors

    # ──────────────────────────────────────────────────────────────────────────
    # SINGLE-TEMPLATE RULES (L1, L2, CL, DPM)
    # ──────────────────────────────────────────────────────────────────────────

    def _validate_single_template_rule(self, rule: dict) -> None:
        """Verarbeitet L1/L2/CL/DPM-Regeln für ein einzelnes Template."""
        template_id  = rule.get("template", "")
        # Finde alle geladenen Template-Varianten (z.B. B02.00_TypeA, B02.00_TypeB)
        matching_keys = [
            k for k in self.templates
            if k == template_id or k.startswith(template_id)
        ]
        if not matching_keys:
            return

        for tpl_key in matching_keys:
            df          = self.templates[tpl_key]
            field_code  = rule.get("field_code", "")
            rule_type   = rule.get("rule_type", "")
            severity    = rule.get("severity", "ERROR")
            rule_id     = rule.get("rule_id", "")
            rule_level  = rule.get("rule_level", "")
            field_label = rule.get("field_label", "")
            explanation = rule.get("explanation", "")
            dpm_ref     = rule.get("dpm_reference", "")
            prerequisite = rule.get("prerequisite", "")
            col_name    = self._find_column(df, field_code)

            # ── L1: Mandatory Field ──────────────────────────────────────────
            if rule_type == "MANDATORY_FIELD":
                if col_name is None:
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level, rule_type=rule_type,
                        template=tpl_key, row=None,
                        field_code=field_code, field_label=field_label,
                        severity=severity, value=None,
                        message=f"Spalte '{field_code}' ({field_label}) fehlt im Template.",
                        explanation=explanation, dpm_reference=dpm_ref
                    )
                    continue
                for idx, val in enumerate(df[col_name]):
                    if not self._is_missing(val):
                        continue
                    # FIX BUG-14: echte Voraussetzungsprüfung
                    if prerequisite and not self._check_prerequisite(df, idx, prerequisite, rule):
                        continue
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level, rule_type=rule_type,
                        template=tpl_key, row=idx + 2,
                        field_code=field_code, field_label=field_label,
                        severity=severity, value=None,
                        message=f"Pflichtfeld leer: '{field_code}' ({field_label}) in Zeile {idx+2}.",
                        explanation=explanation, dpm_reference=dpm_ref
                    )

            # ── L2: Consistency Check ────────────────────────────────────────
            elif rule_type == "CONSISTENCY_CHECK":
                if col_name is not None:
                    self._apply_consistency_rule(rule, df, tpl_key)

            # ── CL: Codelist Check ───────────────────────────────────────────
            elif rule_type == "CODELIST_CHECK":
                if col_name is None:
                    continue
                codelist_vals = rule.get("codelist_values") or []
                if not codelist_vals:
                    cl_name = (rule.get("codelist_name") or
                               self.field_codelist_map.get(f"{template_id};{field_code}"))
                    if cl_name:
                        codelist_vals = self.codelists.get(cl_name, [])
                if not codelist_vals:
                    continue
                valid_set = {str(v).strip() for v in codelist_vals}
                valid_set.update({"Not available", "Not applicable", "N/A", "NA", ""})
                for idx, val in enumerate(df[col_name]):
                    if self._is_missing(val):
                        continue
                    val_str = str(val).strip()
                    if val_str not in valid_set:
                        top10 = ", ".join(sorted(codelist_vals)[:10])
                        ellipsis = "..." if len(codelist_vals) > 10 else ""
                        self._add_error(
                            rule_id=rule_id, rule_level=rule_level, rule_type=rule_type,
                            template=tpl_key, row=idx + 2,
                            field_code=field_code, field_label=field_label,
                            severity=severity, value=val_str,
                            message=(
                                f"Ungültiger Codelist-Wert '{val_str}' in "
                                f"'{field_code}' ({field_label}), Zeile {idx+2}."
                            ),
                            explanation=f"Gültige Werte: {top10}{ellipsis}",
                            dpm_reference=dpm_ref
                        )

            # ── DPM: Datentyp / Format Check ────────────────────────────────
            elif rule_type in ("DATATYPE_CHECK", "FORMAT_CHECK"):
                if col_name is not None:
                    self._apply_dpm_rule(rule, df, tpl_key, col_name)

    # ──────────────────────────────────────────────────────────────────────────
    # L2: CONSISTENCY RULES
    # ──────────────────────────────────────────────────────────────────────────

    def _apply_consistency_rule(self, rule: dict, df: pd.DataFrame, tpl_key: str) -> None:
        """Wendet L2-Konsistenzregeln über test_type-Matching an."""
        test_type   = rule.get("test_type", "").lower()
        rule_id     = rule.get("rule_id", "")
        rule_level  = rule.get("rule_level", "L2")
        field_code  = rule.get("field_code", "")
        field_label = rule.get("field_label", "")
        severity    = rule.get("severity", "ERROR")
        explanation = rule.get("explanation", "")
        dpm_ref     = rule.get("dpm_reference", "")

        col = self._find_column(df, field_code)
        if col is None:
            return

        # ── ISIN-Format ──────────────────────────────────────────────────────
        if "isin" in test_type:
            col_type = self._find_column(df, "c0040")
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                val_str = str(val).strip()
                # FIX BUG-06: prüfe immer, wenn col_type vorhanden; prüfe ISIN-Format direkt
                id_type = str(df[col_type].iloc[idx]).strip() if col_type else "ISIN"
                if "ISIN" in id_type.upper() or col_type is None:
                    if not self.ISIN_RE.match(val_str):
                        self._add_error(
                            rule_id=rule_id, rule_level=rule_level,
                            rule_type="CONSISTENCY_CHECK", template=tpl_key,
                            row=idx+2, field_code=field_code, field_label=field_label,
                            severity=severity, value=val_str,
                            message=(
                                f"Ungültiges ISIN-Format: '{val_str}' in Zeile {idx+2}. "
                                "Erwartet: 2 Großbuchstaben + 9 alphanumerisch + 1 Prüfziffer."
                            ),
                            explanation=explanation, dpm_reference=dpm_ref
                        )

        # ── ISO 4217 Währung ─────────────────────────────────────────────────
        elif "4217" in test_type or "currency" in test_type:
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                val_str = str(val).strip().upper()
                if val_str not in ISO_4217_CURRENCIES:
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="CONSISTENCY_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=val_str,
                        message=f"Ungültiger ISO 4217 Währungscode: '{val_str}' in Zeile {idx+2}.",
                        explanation=explanation, dpm_reference=dpm_ref
                    )

        # ── ISO 3166-1 alpha-2 oder 3166-2 ──────────────────────────────────
        elif "iso 3166" in test_type or "country" in test_type:
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                val_str = str(val).strip()
                # FIX BUG-L2: 3166-2 subdivision codes ebenfalls akzeptieren
                valid = (
                    val_str.upper() in ISO_3166_COUNTRIES
                    or bool(self.ISO_3166_2_RE.match(val_str.upper()))
                )
                if not valid:
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="CONSISTENCY_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=val_str,
                        message=(
                            f"Ungültiger Ländercode: '{val_str}' in Zeile {idx+2}. "
                            "Erwartet: ISO 3166-1 alpha-2 (z.B. 'DE') oder "
                            "ISO 3166-2 (z.B. 'DE-BY')."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

        # ── > 0 ──────────────────────────────────────────────────────────────
        elif "higher than 0" in test_type or "> 0" in test_type:
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                try:
                    num = float(str(val).replace(",", ""))
                    if num <= 0:
                        self._add_error(
                            rule_id=rule_id, rule_level=rule_level,
                            rule_type="CONSISTENCY_CHECK", template=tpl_key,
                            row=idx+2, field_code=field_code, field_label=field_label,
                            severity=severity, value=str(val),
                            message=f"Wert muss > 0 sein: '{val}' in '{field_code}' Zeile {idx+2}.",
                            explanation=explanation, dpm_reference=dpm_ref
                        )
                except (ValueError, TypeError):
                    pass

        # ── >= 0 ─────────────────────────────────────────────────────────────
        elif ("higher than or equal" in test_type or ">= 0" in test_type
              or "equal 0" in test_type):
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                try:
                    num = float(str(val).replace(",", ""))
                    if num < 0:
                        self._add_error(
                            rule_id=rule_id, rule_level=rule_level,
                            rule_type="CONSISTENCY_CHECK", template=tpl_key,
                            row=idx+2, field_code=field_code, field_label=field_label,
                            severity=severity, value=str(val),
                            message=f"Wert muss >= 0 sein: '{val}' in '{field_code}' Zeile {idx+2}.",
                            explanation=explanation, dpm_reference=dpm_ref
                        )
                except (ValueError, TypeError):
                    pass

        # ── Datum ─────────────────────────────────────────────────────────────
        elif "date" in test_type:
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                val_str = str(val).strip()
                if not self.DATE_RE.match(val_str):
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="CONSISTENCY_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=val_str,
                        message=(
                            f"Ungültiges Datumsformat: '{val_str}' in "
                            f"'{field_code}' Zeile {idx+2}. Erwartet: yyyy-mm-dd."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

        # ── Boolean ──────────────────────────────────────────────────────────
        elif "boolean" in test_type or "true/false" in test_type:
            valid_bools = {"True", "False", "true", "false", "TRUE", "FALSE", "1", "0"}
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                if str(val).strip() not in valid_bools:
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="CONSISTENCY_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=str(val).strip(),
                        message=(
                            f"Ungültiger Boolean-Wert: '{val}' in "
                            f"'{field_code}' Zeile {idx+2}. Erwartet: True/False."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

        # ── Integer / Zeilennummer ─────────────────────────────────────────
        elif ("integer" in test_type or "row number" in test_type
              or "unique" in test_type):
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                try:
                    int(float(str(val).replace(",", "")))
                except (ValueError, TypeError):
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="CONSISTENCY_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity="WARNING", value=str(val).strip(),
                        message=(
                            f"Ganzzahl erwartet in '{field_code}' Zeile {idx+2}: '{val}'."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

        # FIX BUG-L2: Drop-down / Codelist-Verweis in L2-Regeln ──────────────
        elif "drop down" in test_type or "drop-down" in test_type:
            # Lade Codelist über field_codelist_map
            cl_name = self.field_codelist_map.get(
                f"{rule.get('template','')};{field_code}"
            )
            cl_vals = self.codelists.get(cl_name, []) if cl_name else []
            if cl_vals:
                valid_set = {str(v).strip() for v in cl_vals}
                valid_set.update({"Not available", "Not applicable", "N/A", "NA", ""})
                for idx, val in enumerate(df[col]):
                    if self._is_missing(val):
                        continue
                    val_str = str(val).strip()
                    if val_str not in valid_set:
                        top10 = ", ".join(sorted(cl_vals)[:10])
                        self._add_error(
                            rule_id=rule_id, rule_level=rule_level,
                            rule_type="CONSISTENCY_CHECK", template=tpl_key,
                            row=idx+2, field_code=field_code, field_label=field_label,
                            severity=severity, value=val_str,
                            message=(
                                f"Ungültiger Dropdown-Wert '{val_str}' in "
                                f"'{field_code}' Zeile {idx+2}."
                            ),
                            explanation=f"Gültige Werte: {top10}{'...' if len(cl_vals)>10 else ''}",
                            dpm_reference=dpm_ref
                        )

        # FIX BUG-L2: Numeric >= 1 (z.B. Zeilennummern in B03/B04) ───────────
        elif "numeric" in test_type and "from 1" in test_type:
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                try:
                    num = float(str(val).replace(",", ""))
                    if num < 1 or num != int(num):
                        self._add_error(
                            rule_id=rule_id, rule_level=rule_level,
                            rule_type="CONSISTENCY_CHECK", template=tpl_key,
                            row=idx+2, field_code=field_code, field_label=field_label,
                            severity=severity, value=str(val),
                            message=(
                                f"Wert muss ganze Zahl >= 1 sein: "
                                f"'{val}' in '{field_code}' Zeile {idx+2}."
                            ),
                            explanation=explanation, dpm_reference=dpm_ref
                        )
                except (ValueError, TypeError):
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="CONSISTENCY_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=str(val).strip(),
                        message=f"Numerischer Wert >= 1 erwartet in '{field_code}' Zeile {idx+2}.",
                        explanation=explanation, dpm_reference=dpm_ref
                    )

        # FIX BUG-L2: Wert muss "Not applicable" sein ─────────────────────────
        elif "not applicable" in test_type and "must be reported" in test_type:
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                val_str = str(val).strip()
                if val_str.lower() not in {"not applicable", "n/a"}:
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="CONSISTENCY_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=val_str,
                        message=(
                            f"Feld '{field_code}' muss 'Not applicable' enthalten "
                            f"(Zeile {idx+2}): Ist-Wert='{val_str}'."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

        # FIX BUG-L2: equal to zero ──────────────────────────────────────────
        elif "equal to zero" in test_type or "equal to 0" in test_type:
            for idx, val in enumerate(df[col]):
                if self._is_missing(val):
                    continue
                try:
                    num = float(str(val).replace(",", ""))
                    if abs(num) > 0.01:
                        self._add_error(
                            rule_id=rule_id, rule_level=rule_level,
                            rule_type="CONSISTENCY_CHECK", template=tpl_key,
                            row=idx+2, field_code=field_code, field_label=field_label,
                            severity=severity, value=str(val),
                            message=(
                                f"Wert muss 0 sein: '{val}' in "
                                f"'{field_code}' Zeile {idx+2}."
                            ),
                            explanation=explanation, dpm_reference=dpm_ref
                        )
                except (ValueError, TypeError):
                    pass

        # FIX BUG-L2: Cross-field Formeln (c0130 = c0080 + c0100 + c0110 etc.) ─
        elif "equal to" in test_type and ("c0" in test_type or "c0" in explanation.lower()):
            self._apply_cross_field_formula(rule, df, tpl_key, col, idx_offset=2)

    def _apply_cross_field_formula(
        self, rule: dict, df: pd.DataFrame, tpl_key: str,
        result_col: str, idx_offset: int
    ) -> None:
        """
        Wertet Cross-Field-Formeln aus dem test_type aus.
        Unterstützte Muster:
          "Check if field is equal to c0080 + c0100 + c0110"
          "Check if field is equal to max(0, c0120 - c0300 - c0320)"
          "Check if field is equal to c0080 - c0090 + c0100"
        """
        rule_id     = rule.get("rule_id", "")
        rule_level  = rule.get("rule_level", "L2")
        field_code  = rule.get("field_code", "")
        field_label = rule.get("field_label", "")
        severity    = rule.get("severity", "WARNING")  # Formeln → Warning (Rundung)
        explanation = rule.get("explanation", "")
        dpm_ref     = rule.get("dpm_reference", "")
        test_type   = rule.get("test_type", "")

        # Extrahiere alle cXXXX-Referenzen aus dem test_type
        referenced_cols = re.findall(r"c\d{4}", test_type.lower())
        if not referenced_cols:
            return

        for idx in range(len(df)):
            try:
                result_val_raw = df[result_col].iloc[idx]
                if self._is_missing(result_val_raw):
                    continue
                result_val = float(str(result_val_raw).replace(",", ""))

                # Sammle Eingabewerte
                ref_vals: dict[str, float] = {}
                for rc in referenced_cols:
                    rc_col = self._find_column(df, rc)
                    if rc_col is None:
                        break
                    v = df[rc_col].iloc[idx]
                    if self._is_missing(v):
                        break
                    ref_vals[rc] = float(str(v).replace(",", ""))
                else:
                    # Alle Eingabewerte vorhanden → Formel auswerten
                    # Einfache Addition/Subtraktion
                    formula_str = test_type.lower()
                    # max(0, ...) Pattern
                    if "max(0," in formula_str or "max(0 ," in formula_str:
                        inner = re.search(r"max\(0[,\s]+(.+?)\)", formula_str)
                        if inner:
                            expr = inner.group(1).strip()
                            computed = self._eval_simple_expr(expr, ref_vals)
                            if computed is not None:
                                expected = max(0.0, computed)
                                if abs(result_val - expected) > 1.0:
                                    self._add_error(
                                        rule_id=rule_id, rule_level=rule_level,
                                        rule_type="CONSISTENCY_CHECK", template=tpl_key,
                                        row=idx+idx_offset,
                                        field_code=field_code, field_label=field_label,
                                        severity=severity,
                                        value=f"{result_val:,.2f} (erwartet: {expected:,.2f})",
                                        message=(
                                            f"Formelabweichung in '{field_code}' Zeile {idx+idx_offset}: "
                                            f"Ist {result_val:,.2f}, erwartet {expected:,.2f}. "
                                            f"Formel: {test_type[:80]}"
                                        ),
                                        explanation=explanation, dpm_reference=dpm_ref
                                    )
                    else:
                        # Einfache Summenformel
                        expr = re.search(r"equal to[:\s]+(.+?)\.?$", formula_str)
                        if expr:
                            computed = self._eval_simple_expr(expr.group(1).strip(), ref_vals)
                            if computed is not None and abs(result_val - computed) > 1.0:
                                self._add_error(
                                    rule_id=rule_id, rule_level=rule_level,
                                    rule_type="CONSISTENCY_CHECK", template=tpl_key,
                                    row=idx+idx_offset,
                                    field_code=field_code, field_label=field_label,
                                    severity=severity,
                                    value=f"{result_val:,.2f} (erwartet: {computed:,.2f})",
                                    message=(
                                        f"Formelabweichung in '{field_code}' Zeile {idx+idx_offset}: "
                                        f"Ist {result_val:,.2f}, erwartet {computed:,.2f}."
                                    ),
                                    explanation=explanation, dpm_reference=dpm_ref
                                )
            except (ValueError, TypeError, IndexError):
                continue

    @staticmethod
    def _eval_simple_expr(expr: str, vals: dict[str, float]) -> Optional[float]:
        """
        Wertet einfache arithmetische Ausdrücke aus (Addition/Subtraktion).
        Eingabe: "c0080 + c0100 - c0090", vals={'c0080': 100.0, ...}
        Gibt None zurück wenn Ausdruck nicht auswertbar.
        """
        # Normalisiere Whitespace
        expr = expr.strip()
        try:
            # Ersetze cXXXX durch ihre Werte
            for code, value in sorted(vals.items(), key=lambda x: -len(x[0])):
                expr = expr.replace(code, str(value))
            # Nur +/- erlaubt (keine eval()-Injection möglich mit dieser Einschränkung)
            if re.search(r"[^0-9+\-.\s]", expr):
                return None
            # Einfache Addition/Subtraktion auswerten
            tokens = re.split(r"([+\-])", expr)
            result = 0.0
            sign   = 1.0
            for token in tokens:
                token = token.strip()
                if token == "+":
                    sign = 1.0
                elif token == "-":
                    sign = -1.0
                elif token:
                    result += sign * float(token)
            return result
        except (ValueError, TypeError):
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # DPM: DATENTYP- & FORMAT-REGELN
    # ──────────────────────────────────────────────────────────────────────────

    def _apply_dpm_rule(
        self, rule: dict, df: pd.DataFrame,
        tpl_key: str, col_name: str
    ) -> None:
        """Wendet DPM 4.2 Datentyp- und Formatregeln zeilenweise an."""
        test_type   = rule.get("test_type", "").lower()
        rule_id     = rule.get("rule_id", "")
        rule_level  = rule.get("rule_level", "DPM")
        field_code  = rule.get("field_code", "")
        field_label = rule.get("field_label", "")
        severity    = rule.get("severity", "ERROR")
        explanation = rule.get("explanation", "")
        dpm_ref     = rule.get("dpm_reference", "")

        for idx, val in enumerate(df[col_name]):
            if self._is_missing(val):
                continue
            val_str = str(val).strip()

            if "numeric" in test_type:
                try:
                    float(val_str.replace(",", "").replace(" ", ""))
                except (ValueError, TypeError):
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="DATATYPE_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=val_str,
                        message=f"Kein Zahlenwert: '{val_str}' in '{field_code}' Zeile {idx+2}.",
                        explanation=explanation, dpm_reference=dpm_ref
                    )

            elif "date" in test_type:
                if not self.DATE_RE.match(val_str):
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="DATATYPE_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=val_str,
                        message=(
                            f"Ungültiges Datum: '{val_str}' in '{field_code}' "
                            f"Zeile {idx+2}. Erwartet: yyyy-mm-dd."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

            elif "iso 3166" in test_type or ("country" in test_type and "iso" in test_type):
                valid = (
                    val_str.upper() in ISO_3166_COUNTRIES
                    or bool(self.ISO_3166_2_RE.match(val_str.upper()))
                )
                if not valid:
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="FORMAT_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=val_str,
                        message=(
                            f"Ungültiger Ländercode: '{val_str}' in "
                            f"'{field_code}' Zeile {idx+2}."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

            elif "iso 4217" in test_type or "currency" in test_type:
                if val_str.upper() not in ISO_4217_CURRENCIES:
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="FORMAT_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=val_str,
                        message=(
                            f"Ungültiger ISO 4217 Währungscode: '{val_str}' "
                            f"in '{field_code}' Zeile {idx+2}."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

            elif "lei" in test_type:
                if not self.LEI_RE.match(val_str.upper()):
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type="FORMAT_CHECK", template=tpl_key,
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=val_str,
                        message=(
                            f"Ungültiges LEI-Format: '{val_str}' in "
                            f"'{field_code}' Zeile {idx+2}. "
                            "Erwartet: 20 alphanumerische Zeichen (ISO 17442)."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

    # ──────────────────────────────────────────────────────────────────────────
    # CROSS-TEMPLATE RULES
    # ──────────────────────────────────────────────────────────────────────────

    def _validate_cross_template_rule(self, rule: dict) -> None:
        """Verarbeitet alle Cross-Template-Regeln nach rule_id."""
        # FIX BUG-07: 'template' und 'test_type' nur bei Bedarf lesen, nicht global unbenutzt
        rule_id     = rule.get("rule_id", "")
        rule_level  = rule.get("rule_level", "CROSS")
        rule_type   = rule.get("rule_type", "")
        field_code  = rule.get("field_code", "")
        field_label = rule.get("field_label", "")
        severity    = rule.get("severity", "WARNING")
        explanation = rule.get("explanation", "")
        dpm_ref     = rule.get("dpm_reference", "")

        # ── v_CROSS_0001: B01 ↔ B02 Reconciliation ───────────────────────────
        if rule_id == "v_CROSS_0001":
            df01 = self._get_template("B01.00")
            df02 = self._get_template("B02.00")
            if df01 is None or df02 is None:
                return
            col01 = self._find_column(df01, "c0050")
            col02 = self._find_column(df02, "c0130")
            if col01 is None or col02 is None:
                return
            try:
                total_b01 = sum(
                    float(str(v).replace(",", "")) for v in df01[col01]
                    if not self._is_missing(v)
                )
                total_b02 = sum(
                    float(str(v).replace(",", "")) for v in df02[col02]
                    if not self._is_missing(v)
                )
                if abs(total_b01 - total_b02) > 1.0:
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type=rule_type, template="B01.00/B02.00",
                        row=None, field_code=field_code, field_label=field_label,
                        severity=severity,
                        value=f"B01={total_b01:,.2f} / B02={total_b02:,.2f}",
                        message=(
                            f"Abstimmungsfehler: B01;c0050={total_b01:,.2f} ≠ "
                            f"B02;c0130-Summe={total_b02:,.2f}. "
                            f"Differenz: {abs(total_b01-total_b02):,.2f}"
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )
            except (ValueError, TypeError):
                pass

        # ── v_CROSS_0002: B02 → B90 Referential Integrity ────────────────────
        elif rule_id == "v_CROSS_0002":
            df02 = self._get_template("B02.00")
            df90 = self._get_template("B90.00")
            if df02 is None or df90 is None:
                return
            col02 = self._find_column(df02, "c0030")
            col90 = self._find_column(df90, "c0020")
            if col02 is None or col90 is None:
                return
            b90_ids = {
                str(v).strip() for v in df90[col90] if not self._is_missing(v)
            }
            skip_vals = {"Aggregated", "N/A", "Not applicable", ""}
            for idx, val in enumerate(df02[col02]):
                if self._is_missing(val):
                    continue
                val_str = str(val).strip()
                if val_str in skip_vals:
                    continue
                if val_str not in b90_ids:
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type=rule_type, template="B02.00",
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=val_str,
                        message=(
                            f"Referenzfehler: '{val_str}' (B02;c0030, Zeile {idx+2}) "
                            "fehlt in B90.00;c0020."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

        # ── v_CROSS_0003: B03 → B90 ───────────────────────────────────────────
        elif rule_id == "v_CROSS_0003":
            self._check_ref_integrity(
                rule, "B03.00", "B90.00", "c0020", "c0020",
                {"Aggregated", "N/A", "Not applicable", ""}
            )

        # ── v_CROSS_0004: B04 → B90 ───────────────────────────────────────────
        elif rule_id == "v_CROSS_0004":
            self._check_ref_integrity(
                rule, "B04.00", "B90.00", "c0020", "c0020",
                {"Aggregated", "N/A", "Not applicable", ""}
            )

        # ── v_CROSS_0005: Entity-Type → Template-Präsenz ─────────────────────
        elif rule_id == "v_CROSS_0005":
            df99 = self._get_template("B99.00")
            if df99 is None:
                return
            col99 = self._find_column(df99, "c0060")
            if col99 is None:
                return
            for idx, val in enumerate(df99[col99]):
                if (not self._is_missing(val)
                        and "Non-Resolution Entity" in str(val)
                        and "B05.00" not in self.templates
                        and "B06.00" not in self.templates):
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type=rule_type, template="B99.00",
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=str(val).strip(),
                        message=(
                            "Reporting entity type = 'Non-Resolution Entity', "
                            "aber B05.00/B06.00 nicht im Submission. Prüfen ob erforderlich."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

        # ── v_CROSS_0006: MREL Insolvency Ranking ────────────────────────────
        elif rule_id == "v_CROSS_0006":
            df02 = self._get_template("B02.00")
            if df02 is None:
                return
            col = self._find_column(df02, "c0160")
            if col is None:
                return
            for idx, val in enumerate(df02[col]):
                if self._is_missing(val):
                    continue
                try:
                    rank = int(float(str(val).replace(",", "")))
                    if rank < 0:
                        self._add_error(
                            rule_id=rule_id, rule_level=rule_level,
                            rule_type=rule_type, template="B02.00",
                            row=idx+2, field_code=field_code, field_label=field_label,
                            severity=severity, value=str(val),
                            message=(
                                f"Ungültiges Insolvency Ranking: '{val}' Zeile {idx+2}. "
                                "Muss >= 0 sein."
                            ),
                            explanation=explanation, dpm_reference=dpm_ref
                        )
                except (ValueError, TypeError):
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type=rule_type, template="B02.00",
                        row=idx+2, field_code=field_code, field_label=field_label,
                        severity=severity, value=str(val),
                        message=(
                            f"Insolvency Ranking kein Integer: '{val}' Zeile {idx+2}."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

        # ── v_CROSS_0007: MREL Amount Derivation ─────────────────────────────
        elif rule_id == "v_CROSS_0007":
            df02 = self._get_template("B02.00")
            if df02 is None or len(df02) == 0:  # FIX BUG-08: leeres DataFrame
                return
            col130 = self._find_column(df02, "c0130")
            col080 = self._find_column(df02, "c0080")
            col100 = self._find_column(df02, "c0100")
            col250 = self._find_column(df02, "c0250")
            if col130 is None or col080 is None:
                return
            for idx in range(len(df02)):  # FIX BUG-08: safe iteration
                try:
                    c130_raw = df02[col130].iloc[idx]
                    c080_raw = df02[col080].iloc[idx]
                    if self._is_missing(c130_raw) or self._is_missing(c080_raw):
                        continue
                    c130 = float(str(c130_raw).replace(",", ""))
                    c080 = float(str(c080_raw).replace(",", ""))
                    c100 = 0.0
                    if col100:
                        c100_raw = df02[col100].iloc[idx]
                        if not self._is_missing(c100_raw):
                            c100 = float(str(c100_raw).replace(",", ""))
                    c250_val = ""
                    if col250:
                        c250_raw = df02[col250].iloc[idx]
                        c250_val = "" if self._is_missing(c250_raw) else str(c250_raw).strip()

                    is_structured = c250_val not in (
                        "Non-structured/Vanilla", "", "Not available", "Not applicable"
                    )
                    if not is_structured:
                        expected = c080 + c100
                        if abs(c130 - expected) > 1.0:
                            self._add_error(
                                rule_id=rule_id, rule_level=rule_level,
                                rule_type=rule_type, template="B02.00",
                                row=idx+2, field_code=field_code, field_label=field_label,
                                severity=severity,
                                value=f"c0130={c130:,.2f} | c0080+c0100={expected:,.2f}",
                                message=(
                                    f"MREL-Betragsableitung: c0130 ({c130:,.2f}) ≠ "
                                    f"c0080+c0100 ({expected:,.2f}), Zeile {idx+2}. "
                                    f"Differenz: {abs(c130-expected):,.2f}"
                                ),
                                explanation=explanation, dpm_reference=dpm_ref
                            )
                except (ValueError, TypeError, IndexError):
                    continue

        # ── v_CROSS_0008: MREL Art. 21(7a) SRMR ─────────────────────────────
        elif rule_id == "v_CROSS_0008":
            df02 = self._get_template("B02.00")
            if df02 is None:
                return
            col060  = self._find_column(df02, "c0060")
            col5010 = self._find_column(df02, "c5010")
            if col060 is None:
                return
            for idx, val in enumerate(df02[col060]):
                if (not self._is_missing(val)
                        and "Intragroup and intra-resolution group" in str(val)):
                    if col5010 is None or self._is_missing(df02[col5010].iloc[idx]):
                        self._add_error(
                            rule_id=rule_id, rule_level=rule_level,
                            rule_type=rule_type, template="B02.00",
                            row=idx+2, field_code="c5010", field_label=field_label,
                            severity=severity, value=str(val).strip(),
                            message=(
                                f"Intragroup-Instrument Zeile {idx+2}: "
                                "c5010 (Art. 21(7a) SRMR) sollte befüllt sein."
                            ),
                            explanation=explanation, dpm_reference=dpm_ref
                        )

        # ── v_CROSS_0009: NCWO-Consistency ───────────────────────────────────
        elif rule_id == "v_CROSS_0009":
            df01 = self._get_template("B01.00")
            df02 = self._get_template("B02.00")
            if df01 is None or df02 is None:
                return
            col01_060 = self._find_column(df01, "c0060")
            col02_050 = self._find_column(df02, "c0050")
            col02_130 = self._find_column(df02, "c0130")
            if col01_060 is None or col02_050 is None or col02_130 is None:
                return
            art44_cats = {
                "Covered deposits (BRRD art. 44/2/a)",
                "Secured liabilities - collateralized part (BRRD art. 44/2/b)",
                "Client liabilities, if protected in insolvency (BRRD art. 44/2/c)",
                "Fiduciary liabilities, if protected in insolvency (BRRD art. 44/2/d)",
                "Institution liabilities < 7 days (BRRD art. 44/2/e)",
                "System (operator) and CCP liabilities < 7 days (BRRD art. 44/2/f)",
                "Employee liabilities (BRRD art. 44/2/g/i)",
                "Critical service liabilities (BRRD art. 44/2/g/ii)",
                "Tax and social security authorities liabilities, if preferred (BRRD art. 44/2/g/iii)",
                "DGS liabilities (BRRD art. 44/2/g/iv)",
                "Liabilities towards other entities of the resolution group (BRRD art. 44/2/h)",
            }
            try:
                excl_b01 = sum(
                    float(str(v).replace(",", "")) for v in df01[col01_060]
                    if not self._is_missing(v) and str(v).strip() not in ("0", "0.0")
                )
                excl_b02 = 0.0
                for i, cat in enumerate(df02[col02_050]):
                    if str(cat).strip() in art44_cats:
                        v = df02[col02_130].iloc[i]
                        if not self._is_missing(v):
                            excl_b02 += float(str(v).replace(",", ""))
                if (excl_b01 > 0 and excl_b02 > 0
                        and abs(excl_b01 - excl_b02) / max(abs(excl_b01), 1) > 0.05):
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type=rule_type, template="B01.00/B02.00",
                        row=None, field_code="c0060", field_label=field_label,
                        severity=severity,
                        value=f"B01;c0060={excl_b01:,.2f} | B02 Art.44(2)={excl_b02:,.2f}",
                        message=(
                            f"NCWO-Abstimmung: B01;c0060 ({excl_b01:,.2f}) weicht >5% ab "
                            f"von B02 BRRD Art.44(2) Summe ({excl_b02:,.2f})."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )
            except (ValueError, TypeError):
                pass

        # ── v_CROSS_0010: Submission A/B Deduplication ───────────────────────
        elif rule_id == "v_CROSS_0010":
            df02_a = self.templates.get("B02.00_TypeA") or self.templates.get("B02.00")
            df02_b = self.templates.get("B02.00_TypeB")
            if df02_a is None or df02_b is None:
                return
            col_a = self._find_column(df02_a, "c0020")
            col_b = self._find_column(df02_b, "c0020")
            if col_a is None or col_b is None:
                return
            ids_a = {str(v).strip() for v in df02_a[col_a] if not self._is_missing(v)}
            for idx, val in enumerate(df02_b[col_b]):
                if self._is_missing(val):
                    continue
                val_str = str(val).strip()
                if val_str in ids_a:
                    self._add_error(
                        rule_id=rule_id, rule_level=rule_level,
                        rule_type=rule_type, template="B02.00_TypeB",
                        row=idx+2, field_code="c0020",
                        field_label="Unique internal identification number",
                        severity=severity, value=val_str,
                        message=(
                            f"Duplikat: ID '{val_str}' in Submission B (Zeile {idx+2}) "
                            "ist bereits in Submission A. Verletzung Anti-Doppelzählung."
                        ),
                        explanation=explanation, dpm_reference=dpm_ref
                    )

    def _check_ref_integrity(
        self,
        rule: dict,
        src_tpl: str,
        ref_tpl: str,
        src_col: str,
        ref_col: str,
        skip_vals: set[str],
    ) -> None:
        """Generischer referenzieller Integritäts-Check: src_tpl.src_col → ref_tpl.ref_col"""
        df_src = self._get_template(src_tpl)
        df_ref = self._get_template(ref_tpl)
        if df_src is None or df_ref is None:
            return
        col_src = self._find_column(df_src, src_col)
        col_ref = self._find_column(df_ref, ref_col)
        if col_src is None or col_ref is None:
            return
        ref_ids = {str(v).strip() for v in df_ref[col_ref] if not self._is_missing(v)}
        for idx, val in enumerate(df_src[col_src]):
            if self._is_missing(val):
                continue
            val_str = str(val).strip()
            if val_str in skip_vals:
                continue
            if val_str not in ref_ids:
                self._add_error(
                    rule_id=rule.get("rule_id", ""),
                    rule_level=rule.get("rule_level", "CROSS"),
                    rule_type=rule.get("rule_type", ""),
                    template=src_tpl,
                    row=idx+2,
                    field_code=rule.get("field_code", ""),
                    field_label=rule.get("field_label", ""),
                    severity=rule.get("severity", "ERROR"),
                    value=val_str,
                    message=(
                        f"Referenzfehler: '{val_str}' ({src_tpl};{src_col}, Zeile {idx+2}) "
                        f"fehlt in {ref_tpl};{ref_col}."
                    ),
                    explanation=rule.get("explanation", ""),
                    dpm_reference=rule.get("dpm_reference", "")
                )

    # ══════════════════════════════════════════════════════════════════════════
    # REPORT GENERATOR  ← FIX BUG-12 [CRITICAL]
    # ══════════════════════════════════════════════════════════════════════════

    def generate_error_report(
        self,
        output_path: str = "MBDT_Fehlerreport.xlsx",
        entity_name: str = "",
        reference_date: str = "",
    ) -> str:
        """
        Generiert einen formatierten xlsx-Fehlerreport.

        Parameters
        ----------
        output_path    : Pfad der Ausgabedatei
        entity_name    : Name der meldenden Entität (für Deckblatt)
        reference_date : Referenzdatum (für Deckblatt)

        Returns
        -------
        Absoluter Pfad der erzeugten Datei
        """
        wb   = openpyxl.Workbook()
        summary = self.get_summary()

        # ── Farbpalette ────────────────────────────────────────────────────
        CLR = {
            "header_dark":  "1F3864",   # Dunkelblau (SRB-Farbe)
            "header_mid":   "2E5FA3",   # Mittelblau
            "header_light": "D6E4F7",   # Hellblau
            "error_bg":     "FDDEDE",   # Rot-hell
            "warning_bg":   "FFF3CD",   # Gelb-hell
            "ok_bg":        "D4EDDA",   # Grün-hell
            "row_alt":      "F2F6FC",   # Alternierend
            "white":        "FFFFFF",
            "text_dark":    "1A1A2E",
            "text_red":     "C0392B",
            "text_orange":  "E67E22",
        }

        thin = Side(style="thin", color="CCCCCC")
        medium = Side(style="medium", color="1F3864")
        border_thin  = Border(left=thin, right=thin, top=thin, bottom=thin)
        border_medium = Border(left=medium, right=medium, top=medium, bottom=medium)

        def hdr_font(bold=True, color="FFFFFF", size=11):
            return Font(name="Calibri", bold=bold, color=color, size=size)

        def cell_font(bold=False, color="1A1A2E", size=10):
            return Font(name="Calibri", bold=bold, color=color, size=size)

        def fill(hex_color):
            return PatternFill("solid", fgColor=hex_color)

        def center():
            return Alignment(horizontal="center", vertical="center", wrap_text=True)

        def left():
            return Alignment(horizontal="left", vertical="center", wrap_text=True)

        # ══════════════════════════════════════════════════════════════════
        # SHEET 1: DECKBLATT
        # ══════════════════════════════════════════════════════════════════
        ws_cover = wb.active
        ws_cover.title = "Deckblatt"
        ws_cover.sheet_view.showGridLines = False
        ws_cover.column_dimensions["A"].width = 3
        ws_cover.column_dimensions["B"].width = 35
        ws_cover.column_dimensions["C"].width = 45

        # Titel-Block
        ws_cover.row_dimensions[1].height = 15
        ws_cover.row_dimensions[2].height = 40
        ws_cover.merge_cells("B2:C2")
        c = ws_cover["B2"]
        c.value = "SRB MBDT Validierungsreport"
        c.font  = Font(name="Calibri", bold=True, size=18, color=CLR["header_dark"])
        c.alignment = left()

        ws_cover.row_dimensions[3].height = 20
        ws_cover.merge_cells("B3:C3")
        c = ws_cover["B3"]
        c.value = "Minimum Bail-in Data Template — Fehlerreport"
        c.font  = Font(name="Calibri", size=12, color=CLR["header_mid"])
        c.alignment = left()

        ws_cover.row_dimensions[4].height = 10

        # Meta-Tabelle
        meta = [
            ("Validierungszeitpunkt", summary.get("validation_time", "")),
            ("Meldende Entität",      entity_name or "—"),
            ("DE Country Annex",       "Ja – DE Country Annex (2024-11-05)" if self.de_annex else "Nein (Standard MBDT)"),
            ("Referenzdatum",         reference_date or "—"),
            ("Geprüfte Templates",    ", ".join(sorted(summary.get("templates_validated", [])))),
            ("Gesamt-Befunde",        str(summary.get("total", 0))),
            ("  davon FEHLER",        str(summary.get("errors", 0))),
            ("  davon WARNUNGEN",     str(summary.get("warnings", 0))),
            ("Engine-Version",        "1.4 (SRB MBDT + EBA DPM 4.2 + DE Country Annex + DQ)"),
        ]
        for i, (key, val) in enumerate(meta, start=5):
            ws_cover.row_dimensions[i].height = 20
            ck = ws_cover.cell(row=i, column=2, value=key)
            cv = ws_cover.cell(row=i, column=3, value=val)
            ck.font      = cell_font(bold=True)
            cv.font      = cell_font()
            ck.alignment = left()
            cv.alignment = left()
            bg = CLR["row_alt"] if i % 2 == 0 else CLR["white"]
            ck.fill = fill(bg)
            cv.fill = fill(bg)
            ck.border = border_thin
            cv.border = border_thin

        # Ergebnis-Ampel
        row_ampel = len(meta) + 7
        ws_cover.row_dimensions[row_ampel].height = 30
        ws_cover.merge_cells(f"B{row_ampel}:C{row_ampel}")
        c = ws_cover.cell(row=row_ampel, column=2)
        total_errors = summary.get("errors", 0)
        total_warns  = summary.get("warnings", 0)
        if total_errors == 0 and total_warns == 0:
            c.value = "✓  Keine Befunde — Submission valide"
            c.fill  = fill(CLR["ok_bg"])
            c.font  = Font(name="Calibri", bold=True, size=12, color="276221")
        elif total_errors == 0:
            c.value = f"⚠  {total_warns} Warnung(en) — Bitte prüfen"
            c.fill  = fill(CLR["warning_bg"])
            c.font  = Font(name="Calibri", bold=True, size=12, color="7D6608")
        else:
            c.value = f"✗  {total_errors} Fehler, {total_warns} Warnung(en) — Korrekturbedarf"
            c.fill  = fill(CLR["error_bg"])
            c.font  = Font(name="Calibri", bold=True, size=12, color=CLR["text_red"])
        c.alignment = center()
        c.border    = border_medium

        # ══════════════════════════════════════════════════════════════════
        # SHEET 2: FEHLERDETAILS
        # ══════════════════════════════════════════════════════════════════
        ws = wb.create_sheet("Fehlerdetails")
        ws.sheet_view.showGridLines = False
        ws.freeze_panes = "A3"

        # Spalten-Definition: (Header, Breite)
        COLS = [
            ("Nr.",               6),
            ("Regel-ID",          14),
            ("Level",              9),
            ("Regeltyp",          22),
            ("Template",          16),
            ("Zeile",              7),
            ("Feldcode",          10),
            ("Feldbezeichnung",   30),
            ("Schweregrad",       13),
            ("Fehlerwert",        25),
            ("Fehlermeldung",     55),
            ("Erläuterung",       45),
            ("DPM-Referenz",      28),
            ("Zeitstempel",       20),
        ]
        for ci, (hdr, width) in enumerate(COLS, 1):
            ws.column_dimensions[get_column_letter(ci)].width = width

        # Gruppenzeile (Zeile 1: Kategorie-Farbbänder)
        ws.row_dimensions[1].height = 14
        groups = [
            (1,  2,  CLR["header_dark"],  "Regel"),
            (3,  3,  CLR["header_mid"],   ""),
            (4,  5,  CLR["header_mid"],   "Lokalisierung"),
            (6,  8,  "2E75B6",            "Feld"),
            (9,  9,  CLR["text_red"],     "Schwere"),
            (10, 13, "555555",            "Details"),
            (14, 14, "777777",            "Meta"),
        ]
        for start, end, color, label in groups:
            ws.merge_cells(
                start_row=1, start_column=start,
                end_row=1,   end_column=end
            )
            c = ws.cell(row=1, column=start, value=label)
            c.fill      = fill(color)
            c.font      = Font(name="Calibri", bold=True, size=8, color="FFFFFF")
            c.alignment = center()

        # Header-Zeile (Zeile 2)
        ws.row_dimensions[2].height = 30
        for ci, (hdr, _) in enumerate(COLS, 1):
            c = ws.cell(row=2, column=ci, value=hdr)
            c.fill      = fill(CLR["header_dark"])
            c.font      = hdr_font(size=10)
            c.alignment = center()
            c.border    = border_thin

        # Datenzeilen
        if not self.errors:
            ws.row_dimensions[3].height = 25
            c = ws.cell(row=3, column=1,
                        value="✓  Keine Validierungsfehler gefunden.")
            c.font      = Font(name="Calibri", bold=True, size=11, color="276221")
            c.fill      = fill(CLR["ok_bg"])
            c.alignment = left()
            ws.merge_cells(f"A3:{get_column_letter(len(COLS))}3")
        else:
            # Sortiere: Errors vor Warnings, dann nach Template + Zeile
            sorted_errors = sorted(
                self.errors,
                key=lambda e: (
                    0 if e.get("severity") == "ERROR" else 1,
                    e.get("template", ""),
                    e.get("row") or 0,
                    e.get("rule_id", "")
                )
            )
            for ri, err in enumerate(sorted_errors, start=3):
                ws.row_dimensions[ri].height = 22
                sev = err.get("severity", "")
                bg  = (CLR["error_bg"] if sev == "ERROR"
                       else CLR["warning_bg"] if sev == "WARNING"
                       else CLR["white"])
                alt = CLR["row_alt"] if ri % 2 == 0 else CLR["white"]

                row_data = [
                    ri - 2,
                    err.get("rule_id", ""),
                    err.get("rule_level", ""),
                    err.get("rule_type", ""),
                    err.get("template", ""),
                    err.get("row", ""),
                    err.get("field_code", ""),
                    err.get("field_label", ""),
                    err.get("severity", ""),
                    err.get("value", ""),
                    err.get("message", ""),
                    err.get("explanation", ""),
                    err.get("dpm_reference", ""),
                    err.get("timestamp", ""),
                ]
                for ci, val in enumerate(row_data, 1):
                    c         = ws.cell(row=ri, column=ci, value=val)
                    c.font    = cell_font()
                    c.border  = border_thin
                    c.alignment = (center() if ci in (1, 6, 9) else left())
                    # Schweregrad-Spalte einfärben
                    if ci == 9:
                        c.fill = fill(CLR["error_bg"] if sev == "ERROR"
                                      else CLR["warning_bg"])
                        c.font = Font(
                            name="Calibri", bold=True, size=10,
                            color=(CLR["text_red"] if sev == "ERROR"
                                   else CLR["text_orange"])
                        )
                    else:
                        c.fill = fill(bg if ci <= 9 else alt)

        # AutoFilter auf Header-Zeile
        ws.auto_filter.ref = (
            f"A2:{get_column_letter(len(COLS))}{max(3, 2 + len(self.errors))}"
        )

        # ══════════════════════════════════════════════════════════════════
        # SHEET 3: ZUSAMMENFASSUNG
        # ══════════════════════════════════════════════════════════════════
        ws_sum = wb.create_sheet("Zusammenfassung")
        ws_sum.sheet_view.showGridLines = False
        ws_sum.column_dimensions["A"].width = 3
        ws_sum.column_dimensions["B"].width = 35
        ws_sum.column_dimensions["C"].width = 15
        ws_sum.column_dimensions["D"].width = 15

        def section_header(ws, row, text, color):
            ws.row_dimensions[row].height = 22
            ws.merge_cells(f"B{row}:D{row}")
            c = ws.cell(row=row, column=2, value=text)
            c.fill = fill(color)
            c.font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
            c.alignment = left()
            c.border = border_thin

        def data_row(ws, row, label, val_err, val_warn=None, alt=False):
            ws.row_dimensions[row].height = 18
            bg = CLR["row_alt"] if alt else CLR["white"]
            cl = ws.cell(row=row, column=2, value=label)
            cl.font = cell_font(bold=False)
            cl.fill = fill(bg)
            cl.alignment = left()
            cl.border = border_thin
            ce = ws.cell(row=row, column=3, value=val_err)
            ce.font = cell_font(bold=True, color=CLR["text_red"] if val_err and val_err > 0 else "276221")
            ce.fill = fill(CLR["error_bg"] if val_err and val_err > 0 else CLR["ok_bg"])
            ce.alignment = center()
            ce.border = border_thin
            if val_warn is not None:
                cw = ws.cell(row=row, column=4, value=val_warn)
                cw.font = cell_font(bold=True, color=CLR["text_orange"] if val_warn > 0 else "276221")
                cw.fill = fill(CLR["warning_bg"] if val_warn > 0 else CLR["ok_bg"])
                cw.alignment = center()
                cw.border = border_thin

        # Spaltenheader
        ws_sum.row_dimensions[2].height = 25
        for ci, hdr in enumerate(["", "Kategorie", "Fehler", "Warnungen"], 1):
            c = ws_sum.cell(row=2, column=ci, value=hdr)
            c.fill = fill(CLR["header_dark"])
            c.font = hdr_font()
            c.alignment = center()
            if ci > 1:
                c.border = border_thin

        row = 3
        section_header(ws_sum, row, "Nach Regeltyp", CLR["header_mid"])
        row += 1
        by_type = summary.get("by_rule_type", {})
        for i, (rt, count) in enumerate(sorted(by_type.items())):
            errs  = sum(1 for e in self.errors if e.get("rule_type") == rt and e.get("severity") == "ERROR")
            warns = sum(1 for e in self.errors if e.get("rule_type") == rt and e.get("severity") == "WARNING")
            data_row(ws_sum, row, rt, errs, warns, alt=i % 2 == 0)
            row += 1

        row += 1
        section_header(ws_sum, row, "Nach Template", CLR["header_mid"])
        row += 1
        by_tpl = summary.get("by_template", {})
        for i, (tpl, count) in enumerate(sorted(by_tpl.items())):
            errs  = sum(1 for e in self.errors if e.get("template") == tpl and e.get("severity") == "ERROR")
            warns = sum(1 for e in self.errors if e.get("template") == tpl and e.get("severity") == "WARNING")
            data_row(ws_sum, row, tpl, errs, warns, alt=i % 2 == 0)
            row += 1

        row += 1
        section_header(ws_sum, row, "Nach Regel-Level", CLR["header_dark"])
        row += 1
        level_labels = {
            "L1": "L1 – Pflichtfelder (SRB)",
            "L2": "L2 – Konsistenz (SRB)",
            "CL": "CL – Codelisten (DPM)",
            "DPM": "DPM – Datentypen (EBA DPM 4.2)",
            "CROSS": "CROSS – Übergreifend + MREL",
            "SYSTEM": "SYSTEM – Technisch",
            "DQ": "DQ – Datenqualität (v1.4)",
        }
        by_level = summary.get("by_rule_level", {})
        for i, (lv, count) in enumerate(sorted(by_level.items())):
            errs  = sum(1 for e in self.errors if e.get("rule_level") == lv and e.get("severity") == "ERROR")
            warns = sum(1 for e in self.errors if e.get("rule_level") == lv and e.get("severity") == "WARNING")
            data_row(ws_sum, row, level_labels.get(lv, lv), errs, warns, alt=i % 2 == 0)
            row += 1

        # ══════════════════════════════════════════════════════════════════
        # SHEET 4: REGELKATALOG
        # ══════════════════════════════════════════════════════════════════
        ws_cat = wb.create_sheet("Regelkatalog")
        ws_cat.sheet_view.showGridLines = False
        ws_cat.freeze_panes = "A2"

        cat_cols = [
            ("Regel-ID", 14), ("Level", 8), ("Typ", 22), ("Template", 14),
            ("Feldcode", 10), ("Bezeichnung", 35), ("Schweregrad", 13),
            ("Test-Beschreibung", 55), ("DPM-Referenz", 28),
        ]
        for ci, (hdr, width) in enumerate(cat_cols, 1):
            ws_cat.column_dimensions[get_column_letter(ci)].width = width
            c = ws_cat.cell(row=1, column=ci, value=hdr)
            c.fill = fill(CLR["header_dark"])
            c.font = hdr_font(size=10)
            c.alignment = center()
            c.border = border_thin

        ws_cat.row_dimensions[1].height = 28
        ws_cat.auto_filter.ref = f"A1:{get_column_letter(len(cat_cols))}1"

        for ri, rule in enumerate(self.rules, start=2):
            ws_cat.row_dimensions[ri].height = 16
            bg = CLR["row_alt"] if ri % 2 == 0 else CLR["white"]
            rule_data = [
                rule.get("rule_id", ""),
                rule.get("rule_level", ""),
                rule.get("rule_type", ""),
                rule.get("template", ""),
                rule.get("field_code", ""),
                rule.get("field_label", ""),
                rule.get("severity", ""),
                rule.get("test_type", ""),
                rule.get("dpm_reference", ""),
            ]
            for ci, val in enumerate(rule_data, 1):
                c = ws_cat.cell(row=ri, column=ci, value=val)
                c.font      = cell_font(size=9)
                c.fill      = fill(bg)
                c.alignment = (center() if ci in (1, 2, 7) else left())
                c.border    = border_thin

        # ══════════════════════════════════════════════════════════════════
        # Speichern
        # ══════════════════════════════════════════════════════════════════
        out = Path(output_path).resolve()
        wb.save(str(out))
        return str(out)

    # ══════════════════════════════════════════════════════════════════════════
    # HILFSFUNKTIONEN
    # ══════════════════════════════════════════════════════════════════════════

    def _find_header_row(self, all_rows: list) -> Optional[int]:
        """
        Findet die Zeile mit 4-stelligen Spaltencodes (0010, 0020 … oder int 10, 20).
        FIX BUG-02: Integer-Codes aus Excel werden korrekt erkannt.
        """
        for idx, row in enumerate(all_rows):
            count = 0
            for c in row:
                if c is None:
                    continue
                s = str(c).strip().lstrip("0") or "0"
                # Erkenne '0010', '10', 10, 20, etc. – alles was als 4-stelliger Code gilt
                if str(c).strip().isdigit() and 10 <= int(str(c).strip()) <= 9999:
                    count += 1
                elif str(c).strip().zfill(4).isdigit() and len(str(c).strip()) == 4:
                    count += 1
            if count >= 2:
                return idx
        return None

    def _extract_headers(self, all_rows: list, code_row_idx: int) -> list[str]:
        """
        Extrahiert Spaltennamen aus der Code-Zeile.
        FIX BUG-03/16: Deduplizierung + robuste None-Behandlung für alle Spalten.
        """
        code_row  = all_rows[code_row_idx]
        label_row = all_rows[code_row_idx - 1] if code_row_idx > 0 else []
        headers   = []
        seen: dict[str, int] = {}

        for i, code in enumerate(code_row):
            if code is not None:
                code_str = str(code).strip()
                # Normalisiere zu 4-stelligem Integer → cXXXX
                if code_str.isdigit():
                    col_name = f"c{code_str.zfill(4)}"
                else:
                    col_name = code_str
            else:
                # Fallback: Label aus der Zeile darüber
                label = label_row[i] if i < len(label_row) else None
                if label and str(label).strip():
                    col_name = str(label).strip()[:40].replace(" ", "_")
                else:
                    col_name = f"col_{i}"

            # FIX BUG-03: Deduplizierung
            if col_name in seen:
                seen[col_name] += 1
                col_name = f"{col_name}_{seen[col_name]}"
            else:
                seen[col_name] = 0

            headers.append(col_name)

        return headers

    def _normalize_col_names(self, cols: list[str]) -> list[str]:
        """Normalisiert CSV-Spaltennamen zu cXXXX-Format."""
        normalized = []
        seen: dict[str, int] = {}
        for col in cols:
            col = str(col).strip()
            if re.match(r"^\d{4}$", col):
                name = f"c{col}"
            elif re.match(r"^c\d{4}$", col):
                name = col
            elif re.match(r"^\d{1,3}$", col):
                name = f"c{col.zfill(4)}"
            else:
                name = col
            if name in seen:
                seen[name] += 1
                name = f"{name}_{seen[name]}"
            else:
                seen[name] = 0
            normalized.append(name)
        return normalized

    def _safe_float(self, val) -> "Optional[float]":
        """Konvertiert einen Wert sicher zu float oder gibt None zurück."""
        if self._is_missing(val):
            return None
        try:
            return float(str(val).strip().replace(",", "."))
        except (ValueError, TypeError):
            return None

    def _parse_date(self, val):
        """Parst ein Datum aus verschiedenen Formaten. Gibt datetime.date oder None zurück."""
        import datetime as _dt
        if self._is_missing(val):
            return None
        if isinstance(val, _dt.datetime):
            return val.date()
        if isinstance(val, _dt.date):
            return val
        s = str(val).strip()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y%m%d"):
            try:
                return _dt.datetime.strptime(s, fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # DQ – DATENQUALITÄT HANDLER (CR-01, v1.4)
    # ══════════════════════════════════════════════════════════════════════════

    def _validate_dq_rule(self, rule: dict) -> None:
        """Dispatcht DQ-Regeln nach rule_type."""
        rt = rule.get("rule_type", "")
        if rt == "CONDITIONAL_MANDATORY":
            self._dq_conditional_mandatory(rule)
        elif rt == "VALUE_PLAUSIBILITY":
            self._dq_value_plausibility(rule)
        elif rt == "DATE_CONSISTENCY":
            self._dq_date_consistency(rule)
        elif rt == "CROSS_TEMPLATE_CONSISTENCY":
            self._dq_cross_ref(rule)
        elif rt == "UNIQUENESS_CHECK":
            self._dq_uniqueness(rule)
        elif rt == "BUSINESS_LOGIC":
            self._dq_business_logic(rule)
        elif rt == "FORMAT_CHECK":
            self._dq_format_check(rule)

    def _dq_conditional_mandatory(self, rule: dict) -> None:
        """Prüft: wenn condition_field op condition_value, muss target_field gefüllt sein."""
        tmpl   = rule.get("template", "")
        cond_f = rule.get("condition_field", "")
        cond_v = rule.get("condition_value", "")
        op     = rule.get("operator", "eq")
        tgt_f  = rule.get("target_field", "")
        for key in [k for k in self.templates if k == tmpl or k.startswith(tmpl)]:
            df = self.templates[key]
            cf_col = self._find_column(df, cond_f)
            tf_col = self._find_column(df, tgt_f)
            if cf_col is None or tf_col is None:
                continue
            for row_idx, row_data in df.iterrows():
                cv = row_data[cf_col]
                tv = row_data[tf_col]
                triggered = False
                if op == "eq":
                    triggered = (not self._is_missing(cv)) and str(cv).strip() == str(cond_v).strip()
                elif op == "neq":
                    triggered = (not self._is_missing(cv)) and str(cv).strip() != str(cond_v).strip()
                elif op == "not_missing":
                    triggered = not self._is_missing(cv)
                elif op == "missing":
                    triggered = self._is_missing(cv)
                if triggered and self._is_missing(tv):
                    self._add_error(
                        rule_id=rule.get("rule_id", ""), rule_level="DQ",
                        rule_type=rule.get("rule_type", ""), template=key,
                        row=int(row_idx) + 2, field_code=tgt_f,
                        field_label=rule.get("field_label", tgt_f),
                        severity=rule.get("severity", "WARNING"), value="<leer>",
                        message=rule.get("message", f"Pflichtfeld fehlt wenn {cond_f}={cond_v}"),
                        explanation=rule.get("explanation", ""),
                        dpm_reference=rule.get("dpm_reference", "")
                    )

    def _dq_value_plausibility(self, rule: dict) -> None:
        """Prüft numerische Plausibilität (lte, sum_lte, gte_zero_if, equals_diff, etc.)."""
        tmpl  = rule.get("template", "")
        fld   = rule.get("field", "")
        op    = rule.get("operator", "")
        fld2  = rule.get("field2", "")
        fld3  = rule.get("field3", "")
        threshold = rule.get("threshold")
        for key in [k for k in self.templates if k == tmpl or k.startswith(tmpl)]:
            df = self.templates[key]
            col  = self._find_column(df, fld)
            col2 = self._find_column(df, fld2) if fld2 else None
            col3 = self._find_column(df, fld3) if fld3 else None
            if col is None:
                continue
            for row_idx, row_data in df.iterrows():
                v1 = self._safe_float(row_data[col])
                v2 = self._safe_float(row_data[col2]) if col2 else None
                v3 = self._safe_float(row_data[col3]) if col3 else None
                error = False
                if op == "lte" and v1 is not None and v2 is not None:
                    error = v1 > v2
                elif op == "sum_lte" and v1 is not None and v2 is not None and v3 is not None:
                    error = (v1 + v2) > v3
                elif op == "gte_zero_if" and col2:
                    cv = row_data[col2]
                    if not self._is_missing(cv) and v1 is not None:
                        error = v1 < 0
                elif op == "equals_diff" and v1 is not None and v2 is not None and v3 is not None:
                    error = abs(v1 - (v2 - v3)) > 0.01
                elif op == "gt_zero_if" and col2:
                    cv = row_data[col2]
                    if not self._is_missing(cv) and v1 is not None:
                        error = v1 <= 0
                elif op == "gt_zero_if_present" and v1 is not None:
                    error = v1 <= 0
                elif op == "opposite_sign_or_zero" and v1 is not None and v2 is not None:
                    if v2 > 0:
                        error = v1 > 0
                    elif v2 < 0:
                        error = v1 < 0
                elif op == "range_exclusive_min" and v1 is not None:
                    lo = rule.get("range_min", 0)
                    hi = rule.get("range_max")
                    error = not (v1 > lo and (hi is None or v1 <= hi))
                elif op == "gte_zero" and v1 is not None:
                    error = v1 < 0
                elif op == "gt_zero" and v1 is not None:
                    error = v1 <= 0
                if error:
                    self._add_error(
                        rule_id=rule.get("rule_id", ""), rule_level="DQ",
                        rule_type=rule.get("rule_type", ""), template=key,
                        row=int(row_idx) + 2, field_code=fld,
                        field_label=rule.get("field_label", fld),
                        severity=rule.get("severity", "WARNING"),
                        value=row_data[col],
                        message=rule.get("message", f"Plausibilitätsfehler: {op}"),
                        explanation=rule.get("explanation", ""),
                        dpm_reference=rule.get("dpm_reference", "")
                    )

    def _dq_date_consistency(self, rule: dict) -> None:
        """Prüft Datumsbeziehungen (lte_refdate, gte_refdate, lte_field, gte_field)."""
        import datetime as _dt
        tmpl = rule.get("template", "")
        fld  = rule.get("field", "")
        op   = rule.get("operator", "")
        fld2 = rule.get("field2", "")
        ref_date = self._parse_date(self.reference_date) if self.reference_date else None
        for key in [k for k in self.templates if k == tmpl or k.startswith(tmpl)]:
            df = self.templates[key]
            col  = self._find_column(df, fld)
            col2 = self._find_column(df, fld2) if fld2 else None
            if col is None:
                continue
            for row_idx, row_data in df.iterrows():
                d1 = self._parse_date(row_data[col])
                if d1 is None:
                    continue
                error = False
                if op == "lte_refdate" and ref_date:
                    error = d1 > ref_date
                elif op == "gte_refdate" and ref_date:
                    error = d1 < ref_date
                elif op == "lte_field" and col2:
                    d2 = self._parse_date(row_data[col2])
                    if d2 is not None:
                        error = d1 > d2
                elif op == "gte_field" and col2:
                    d2 = self._parse_date(row_data[col2])
                    if d2 is not None:
                        error = d1 < d2
                if error:
                    self._add_error(
                        rule_id=rule.get("rule_id", ""), rule_level="DQ",
                        rule_type=rule.get("rule_type", ""), template=key,
                        row=int(row_idx) + 2, field_code=fld,
                        field_label=rule.get("field_label", fld),
                        severity=rule.get("severity", "WARNING"),
                        value=str(row_data[col]),
                        message=rule.get("message", f"Datumsfehler: {op}"),
                        explanation=rule.get("explanation", ""),
                        dpm_reference=rule.get("dpm_reference", "")
                    )

    def _dq_uniqueness(self, rule: dict) -> None:
        """Prüft Einzigartigkeit von Werten in key_fields."""
        tmpl       = rule.get("template", "")
        key_fields = rule.get("key_fields", [])
        for key in [k for k in self.templates if k == tmpl or k.startswith(tmpl)]:
            df = self.templates[key]
            cols = [self._find_column(df, f) for f in key_fields]
            cols = [c for c in cols if c is not None]
            if not cols:
                continue
            seen: dict = {}
            for row_idx, row_data in df.iterrows():
                vals = tuple(str(row_data[c]).strip() for c in cols)
                if any(self._is_missing(row_data[c]) for c in cols):
                    continue
                if vals in seen:
                    self._add_error(
                        rule_id=rule.get("rule_id", ""), rule_level="DQ",
                        rule_type=rule.get("rule_type", ""), template=key,
                        row=int(row_idx) + 2, field_code=",".join(key_fields),
                        field_label=rule.get("field_label", ",".join(key_fields)),
                        severity=rule.get("severity", "WARNING"),
                        value=str(vals),
                        message=rule.get("message", f"Duplikat gefunden: {vals}"),
                        explanation=rule.get("explanation", ""),
                        dpm_reference=rule.get("dpm_reference", "")
                    )
                else:
                    seen[vals] = row_idx

    def _dq_business_logic(self, rule: dict) -> None:
        """Prüft komplexe Geschäftslogik-Regeln."""
        tmpl        = rule.get("template", "")
        biz_rule    = rule.get("business_rule", "")
        for key in [k for k in self.templates if k == tmpl or k.startswith(tmpl)]:
            df = self.templates[key]
            errors_rows = []
            if biz_rule == "structural_subordination_rank":
                col_rank  = self._find_column(df, "c0170")
                col_subord = self._find_column(df, "c0160")
                if col_rank and col_subord:
                    for ri, rd in df.iterrows():
                        if str(rd[col_subord]).strip() == "1" and self._is_missing(rd[col_rank]):
                            errors_rows.append((ri, "c0170", rd[col_rank]))
            elif biz_rule == "own_funds_rank_check":
                col_type  = self._find_column(df, "c0060")
                col_rank  = self._find_column(df, "c0170")
                if col_type and col_rank:
                    for ri, rd in df.iterrows():
                        if str(rd[col_type]).strip() in ("T1", "T2", "AT1") and self._is_missing(rd[col_rank]):
                            errors_rows.append((ri, "c0170", rd[col_rank]))
            elif biz_rule == "zero_coupon_accruals":
                col_coup = self._find_column(df, "c0110")
                col_acc  = self._find_column(df, "c0220")
                if col_coup and col_acc:
                    for ri, rd in df.iterrows():
                        v_coup = self._safe_float(rd[col_coup])
                        v_acc  = self._safe_float(rd[col_acc])
                        if v_coup == 0.0 and v_acc is not None and v_acc != 0.0:
                            errors_rows.append((ri, "c0220", rd[col_acc]))
            elif biz_rule == "non_structured_fields_empty":
                col_struct = self._find_column(df, "c0360")
                struct_fields = rule.get("structured_fields", [])
                if col_struct and struct_fields:
                    for ri, rd in df.iterrows():
                        if str(rd[col_struct]).strip() == "0":
                            for sf in struct_fields:
                                sc = self._find_column(df, sf)
                                if sc and not self._is_missing(rd[sc]):
                                    errors_rows.append((ri, sf, rd[sc]))
            elif biz_rule == "unsecured_no_collateral":
                col_sec  = self._find_column(df, "c0300")
                col_coll = self._find_column(df, "c0310")
                if col_sec and col_coll:
                    for ri, rd in df.iterrows():
                        if str(rd[col_sec]).strip() == "0" and not self._is_missing(rd[col_coll]):
                            errors_rows.append((ri, "c0310", rd[col_coll]))
            elif biz_rule == "securities_count_consistency":
                col_count = self._find_column(df, "c0410")
                col_sec   = self._find_column(df, "c0420")
                if col_count and col_sec:
                    for ri, rd in df.iterrows():
                        v_count = self._safe_float(rd[col_count])
                        v_sec   = self._safe_float(rd[col_sec])
                        if v_count is not None and v_sec is not None and v_count > 0 and v_sec == 0:
                            errors_rows.append((ri, "c0420", rd[col_sec]))
            elif biz_rule == "ccp_cleared_stay_na":
                col_ccp  = self._find_column(df, "c0380")
                col_stay = self._find_column(df, "c0390")
                if col_ccp and col_stay:
                    for ri, rd in df.iterrows():
                        if str(rd[col_ccp]).strip() == "1" and not self._is_missing(rd[col_stay]):
                            errors_rows.append((ri, "c0390", rd[col_stay]))
            elif biz_rule == "carrying_amount_plausibility":
                col_ca  = self._find_column(df, "c0070")
                col_nom = self._find_column(df, "c0080")
                if col_ca and col_nom:
                    for ri, rd in df.iterrows():
                        v_ca  = self._safe_float(rd[col_ca])
                        v_nom = self._safe_float(rd[col_nom])
                        if v_ca is not None and v_nom is not None and v_nom > 0 and abs(v_ca) > v_nom * 1.5:
                            errors_rows.append((ri, "c0070", rd[col_ca]))
            elif biz_rule == "eur_exchange_rate_positive":
                col_rate = self._find_column(df, "c0060")
                if col_rate:
                    for ri, rd in df.iterrows():
                        v = self._safe_float(rd[col_rate])
                        if v is not None and v <= 0:
                            errors_rows.append((ri, "c0060", rd[col_rate]))
            elif biz_rule == "eur_currency_rate_one":
                col_curr = self._find_column(df, "c0020")
                col_rate = self._find_column(df, "c0060")
                if col_curr and col_rate:
                    for ri, rd in df.iterrows():
                        if str(rd[col_curr]).strip().upper() == "EUR":
                            v = self._safe_float(rd[col_rate])
                            if v is not None and abs(v - 1.0) > 0.0001:
                                errors_rows.append((ri, "c0060", rd[col_rate]))
            elif biz_rule == "lei_name_consistency":
                col_lei  = self._find_column(df, "c0010")
                col_name = self._find_column(df, "c0020")
                if col_lei and col_name:
                    lei_map: dict = {}
                    for ri, rd in df.iterrows():
                        lei_val  = str(rd[col_lei]).strip()  if not self._is_missing(rd[col_lei])  else ""
                        name_val = str(rd[col_name]).strip() if not self._is_missing(rd[col_name]) else ""
                        if lei_val and name_val:
                            if lei_val in lei_map and lei_map[lei_val] != name_val:
                                errors_rows.append((ri, "c0020", name_val))
                            else:
                                lei_map[lei_val] = name_val
            for ri, field_c, val in errors_rows:
                self._add_error(
                    rule_id=rule.get("rule_id", ""), rule_level="DQ",
                    rule_type=rule.get("rule_type", ""), template=key,
                    row=int(ri) + 2, field_code=field_c,
                    field_label=rule.get("field_label", field_c),
                    severity=rule.get("severity", "WARNING"),
                    value=str(val),
                    message=rule.get("message", f"Business-Logik-Fehler: {biz_rule}"),
                    explanation=rule.get("explanation", ""),
                    dpm_reference=rule.get("dpm_reference", "")
                )

    def _dq_cross_ref(self, rule: dict) -> None:
        """Prüft referenzielle Integrität: Wert in field muss in ref_template.ref_field existieren."""
        tmpl      = rule.get("template", "")
        fld       = rule.get("field", "")
        ref_tmpl  = rule.get("ref_template", "")
        ref_fld   = rule.get("ref_field", "")
        ref_df    = self._get_template(ref_tmpl)
        if ref_df is None:
            return  # Referenz-Template nicht geladen
        ref_col = self._find_column(ref_df, ref_fld)
        if ref_col is None:
            return
        ref_values = set(
            str(v).strip() for v in ref_df[ref_col] if not self._is_missing(v)
        )
        for key in [k for k in self.templates if k == tmpl or k.startswith(tmpl)]:
            df  = self.templates[key]
            col = self._find_column(df, fld)
            if col is None:
                continue
            for row_idx, row_data in df.iterrows():
                val = row_data[col]
                if self._is_missing(val):
                    continue
                if str(val).strip() not in ref_values:
                    self._add_error(
                        rule_id=rule.get("rule_id", ""), rule_level="DQ",
                        rule_type=rule.get("rule_type", ""), template=key,
                        row=int(row_idx) + 2, field_code=fld,
                        field_label=rule.get("field_label", fld),
                        severity=rule.get("severity", "WARNING"),
                        value=str(val),
                        message=rule.get("message", f"Referenz fehlt: {val} nicht in {ref_tmpl}.{ref_fld}"),
                        explanation=rule.get("explanation", ""),
                        dpm_reference=rule.get("dpm_reference", "")
                    )

    def _dq_format_check(self, rule: dict) -> None:
        """Prüft Format-Anforderungen (ISIN, LEI, ISO3166 etc.)."""
        import re
        tmpl       = rule.get("template", "")
        fld        = rule.get("field", "")
        fmt_type   = rule.get("format_type", "")
        for key in [k for k in self.templates if k == tmpl or k.startswith(tmpl)]:
            df  = self.templates[key]
            col = self._find_column(df, fld)
            if col is None:
                continue
            for row_idx, row_data in df.iterrows():
                val = row_data[col]
                if self._is_missing(val):
                    continue
                s = str(val).strip()
                error = False
                if fmt_type == "ISIN":
                    error = not (len(s) == 12 and re.match(r"^[A-Z]{2}[A-Z0-9]{10}$", s))
                elif fmt_type == "LEI":
                    error = not (len(s) == 20 and re.match(r"^[A-Z0-9]{20}$", s))
                elif fmt_type == "ISO3166_ALPHA2":
                    error = not re.match(r"^[A-Z]{2}$", s)
                elif fmt_type == "BIC":
                    error = not re.match(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$", s)
                if error:
                    self._add_error(
                        rule_id=rule.get("rule_id", ""), rule_level="DQ",
                        rule_type=rule.get("rule_type", ""), template=key,
                        row=int(row_idx) + 2, field_code=fld,
                        field_label=rule.get("field_label", fld),
                        severity=rule.get("severity", "WARNING"),
                        value=s,
                        message=rule.get("message", f"Format ungültig ({fmt_type}): {s}"),
                        explanation=rule.get("explanation", ""),
                        dpm_reference=rule.get("dpm_reference", "")
                    )

    def _find_column(self, df: pd.DataFrame, field_code: str) -> Optional[str]:
        """
        Sucht eine Spalte im DataFrame — flexibles Matching (cXXXX ↔ XXXX ↔ int).
        """
        if df is None or not field_code:
            return None
        if field_code in df.columns:
            return field_code
        # Versuche cXXXX → XXXX
        alt = field_code[1:] if field_code.startswith("c") else f"c{field_code}"
        if alt in df.columns:
            return alt
        # Normalisiert
        normalized = f"c{field_code.lstrip('c').zfill(4)}"
        if normalized in df.columns:
            return normalized
        return None

    def _get_template(self, template_id: str) -> Optional[pd.DataFrame]:
        """Gibt ein Template zurück — sucht auch nach Varianten (TypeA, TypeB)."""
        if template_id in self.templates:
            return self.templates[template_id]
        for key in self.templates:
            if key.startswith(template_id):
                return self.templates[key]
        return None

    def _is_missing(self, val: Any) -> bool:
        """
        FIX BUG-05: Prüft ob ein Wert fehlt.
        Nutzt pd.isna() für robuste NaN/NA/NaT-Erkennung.
        """
        # pd.isna deckt float NaN, pd.NA, pd.NaT ab
        try:
            if pd.isna(val):
                return True
        except (TypeError, ValueError):
            pass
        if val is None:
            return True
        s = str(val).strip().lower()
        return s in _MISSING_STRINGS

    def _check_prerequisite(
        self, df: pd.DataFrame, row_idx: int,
        prerequisite: str, rule: dict
    ) -> bool:
        """
        FIX BUG-14: Echte Voraussetzungsprüfung.
        Parst Muster wie 'c0250 = Non-structured/Vanilla' oder
        'c0060 = Intragroup...'. Gibt True zurück wenn Regel angewendet werden soll.
        """
        if not prerequisite:
            return True

        prereq_lower = prerequisite.lower()

        # Muster: "wenn Feld X einen Wert Y hat → dann prüfen"
        # Nur wenn nicht angegeben → immer prüfen
        field_match = re.search(r"c(\d{4})\s*=\s*['\"]?([^'\"]+)['\"]?", prerequisite, re.IGNORECASE)
        if field_match:
            cond_col_code = f"c{field_match.group(1).zfill(4)}"
            cond_val      = field_match.group(2).strip()
            actual_col    = self._find_column(df, cond_col_code)
            if actual_col and row_idx < len(df):
                actual_val = str(df[actual_col].iloc[row_idx]).strip()
                # Bedingung muss erfüllt sein
                return cond_val.lower() in actual_val.lower()
            # Bedingungsfeld nicht vorhanden → Regel nicht anwenden
            return False

        # Schlüsselwortbasiert: "non-structured" → prüfe c0250
        if "non-structured" in prereq_lower:
            col = self._find_column(df, "c0250")
            if col and row_idx < len(df):
                return "non-structured" in str(df[col].iloc[row_idx]).lower()

        if "structured" in prereq_lower and "non-structured" not in prereq_lower:
            col = self._find_column(df, "c0250")
            if col and row_idx < len(df):
                v = str(df[col].iloc[row_idx]).lower()
                return "structured" in v and "non-structured" not in v

        # Default: Regel anwenden
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # STATISTIK / SUMMARY
    # ══════════════════════════════════════════════════════════════════════════

    def get_summary(self) -> dict:
        """Gibt eine strukturierte Zusammenfassung der Validierungsergebnisse zurück."""
        total    = len(self.errors)
        errors   = sum(1 for e in self.errors if e.get("severity") == "ERROR")
        warnings = sum(1 for e in self.errors if e.get("severity") == "WARNING")

        by_template:   dict[str, int] = defaultdict(int)
        by_type:       dict[str, int] = defaultdict(int)
        by_level:      dict[str, int] = defaultdict(int)
        for e in self.errors:
            by_template[e.get("template", "")]  += 1
            by_type[e.get("rule_type", "")]     += 1
            by_level[e.get("rule_level", "")]   += 1

        return {
            "total":               total,
            "errors":              errors,
            "warnings":            warnings,
            "by_template":         dict(by_template),
            "by_rule_type":        dict(by_type),
            "by_rule_level":       dict(by_level),
            # FIX BUG-10: sortierte, normalisierte Template-IDs
            "templates_validated": sorted(self.templates.keys()),
            "validation_time":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _add_error(
        self,
        rule_id: str, rule_level: str, rule_type: str,
        template: str, row: Optional[int], field_code: Optional[str],
        field_label: str, severity: str, value: Any,
        message: str, explanation: str, dpm_reference: str,
    ) -> None:
        """Fügt einen Befund (Fehler oder Warnung) zur Ergebnisliste hinzu."""
        self.errors.append({
            "rule_id":       rule_id,
            "rule_level":    rule_level,
            "rule_type":     rule_type,
            "template":      template,
            "row":           row,
            "field_code":    field_code or "",
            "field_label":   field_label,
            "severity":      severity,
            "value":         str(value)[:200] if value is not None else "",
            "message":       message,
            "explanation":   explanation,
            "dpm_reference": dpm_reference,
            "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
