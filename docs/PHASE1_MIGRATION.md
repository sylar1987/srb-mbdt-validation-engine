# Phase 1 – Migration & Mapping

Dieser Stand setzt **Phase 1** des Soll-Aufbaus
(`phase1_soll_aufbau_gap_analyse_v2.md`) um. Die bestehende monolithische
Klasse `MBDTValidator` (≈2.290 Zeilen) ist als Legacy-Fassade erhalten;
die neue Architektur unter `app/` kapselt Input, Konfiguration,
Normalisierung, Datenmodelle, Validierungs-Orchestrierung, Reporting und
Services. Fachliche Logik wurde *nicht* neu geschrieben — alle 394
Regeln werden weiterhin von `MBDTValidator` ausgewertet, allerdings
*aufgerufen vom Dispatcher* und *konsumiert als `ValidationIssue`*.

## Ziel-Architektur (umgesetzt)

```
app/
├── main.py                 # Modulare CLI (python -m app.main)
├── runner.py               # Runner orchestriert Lauf
├── settings.py             # EngineSettings + Pfade
├── io/
│   ├── csv_loader.py       # CSV-Verzeichnis + Einzeldatei → InputBatch
│   ├── xlsx_loader.py      # XLSX → InputBatch
│   └── template_registry.py
├── config/
│   └── catalog_loader.py   # rule_catalog.json + field_structure.json
├── models/
│   ├── batch.py            # InputBatch
│   ├── template_data.py    # TemplateData
│   ├── rule.py             # RuleDefinition
│   ├── issue.py            # ValidationIssue
│   └── summary.py          # ValidationSummary
├── normalization/
│   ├── headers.py          # Header/Spaltenname-Logik
│   ├── missing.py          # Blank/NA-Handling
│   └── values.py           # String-Normalisierung
├── validation/
│   ├── context.py          # ValidationContext (expliziter Laufzeitstate)
│   ├── dispatcher.py       # Dispatcher + Validator-Registry
│   ├── engine.py           # ValidationEngine (orchestriert Lauf)
│   ├── mandatory_validator.py
│   ├── codelist_validator.py
│   ├── datatype_validator.py
│   ├── consistency_validator.py
│   ├── cross_template_validator.py
│   ├── dq_validator.py
│   ├── prerequisite_evaluator.py
│   └── _legacy_adapter.py  # Phase-1-Adapter zur MBDTValidator-Logik
├── services/
│   ├── reference_date_service.py
│   └── template_lookup_service.py
├── reporting/
│   ├── excel_report_writer.py
│   └── summary_builder.py
└── utils/
    ├── regex_patterns.py
    ├── iso_lists.py
    ├── numeric.py
    └── dates.py
```

## Mapping-Matrix Altlogik → neues Modul

| Alt (`mbdt_validator.py`) | Neu |
|---|---|
| `MBDTValidator.__init__` (JSON-Laden, DE-Annex-Overrides) | `app.config.catalog_loader.load_catalog` + `Catalog.apply_de_annex` |
| `load_xlsx` | `app.io.xlsx_loader.load_xlsx` |
| `load_csv_dir` | `app.io.csv_loader.load_csv_dir` |
| `load_single_csv` | `app.io.csv_loader.load_single_csv` |
| `TEMPLATE_SHEET_MAP` | `app.io.template_registry` |
| `_find_header_row`, `_extract_headers` | `app.normalization.headers.find_header_row`, `extract_headers` |
| `_normalize_col_names` | `app.normalization.headers.normalize_col_names` |
| Missing/Blank-Handling (`replace("", pd.NA)`) | `app.normalization.missing.replace_blank_with_na` |
| `astype(str).replace("None"/"nan", pd.NA)` | `app.normalization.values.normalize_dataframe_strings` |
| ISO-Codelisten, `_MISSING_STRINGS` | `app.utils.iso_lists` |
| Regex (`DATE_RE`, `ISIN_RE`, `LEI_RE`, `ISO_3166_2_RE`, …) | `app.utils.regex_patterns` |
| `_safe_float`, `_is_missing` | `app.utils.numeric` |
| `_parse_date` | `app.utils.dates` |
| `_find_column`, `_get_template` | `app.normalization.headers.find_column`, `app.services.template_lookup_service` |
| Reference-Date-Extraktion aus B99.00 c0070 | `app.services.reference_date_service.extract_reference_date` |
| `validate()` Orchestrierung | `app.validation.engine.ValidationEngine.run` |
| Routing nach `rule_level` | `app.validation.dispatcher.Dispatcher` |
| `_validate_single_template_rule` (L1) | `app.validation.mandatory_validator` (delegiert) |
| `_validate_single_template_rule` (CL) | `app.validation.codelist_validator` (delegiert) |
| `_validate_single_template_rule` (DPM) | `app.validation.datatype_validator` (delegiert) |
| `_apply_consistency_rule`, `_apply_cross_field_formula` (L2) | `app.validation.consistency_validator` (delegiert) |
| `_validate_cross_template_rule` (CROSS) | `app.validation.cross_template_validator` (delegiert) |
| `_validate_dq_rule` + Subhandler | `app.validation.dq_validator` (delegiert) |
| `_check_prerequisite` | `app.validation.prerequisite_evaluator.evaluate` |
| Fehler-Dicts via `_add_error` | `app.models.ValidationIssue` (mit `from_dict`/`to_dict`-Roundtrip) |
| `get_summary` | `app.models.ValidationSummary.from_issues` + `app.reporting.summary_builder` |
| `generate_error_report` (Excel) | `app.reporting.excel_report_writer.write_excel_report` (Consumer von ValidationIssue) |

## Phase-1-Datenklassen

* **`InputBatch`** – Aggregat aller geladenen Templates einer Submission
  (Source-Type, Path, Entity, Reference Date, Map `key → DataFrame`,
  parallele Map `key → TemplateData`).
* **`TemplateData`** – Pro Template Variant/Sourcename/Rohwerte + Debug-Dict.
* **`RuleDefinition`** – Typisierte Sicht auf JSON-Regeln,
  `to_legacy_dict()` liefert Roh-JSON für die Legacy-Auswertung.
* **`ValidationIssue`** – Einheitliches Fehler-/Befundobjekt
  (`from_dict`/`to_dict` 1:1 kompatibel zum bisherigen Dict-Format).
* **`ValidationSummary`** – Aggregiert Issues je Template, Level und Type
  (`from_issues`); ersetzt das Dict-Result von `get_summary`.

## Programmfluss

1. `Runner` lädt Konfiguration (`load_catalog`, optional Field-Structure).
2. `Runner.load_xlsx/csv_dir/single_csv` → `InputBatch`.
3. `Runner.validate` baut `ValidationContext` und ruft `ValidationEngine.run`.
4. Engine prüft System-Checks (SYS_001/SYS_002), zieht Reference Date.
5. `Dispatcher` iteriert `RuleDefinition`s und ruft den passenden Validator.
6. Jeder Validator liefert `list[ValidationIssue]`.
7. `summary_builder.build_summary` aggregiert → `ValidationSummary`.
8. `excel_report_writer.write_excel_report` rekonstruiert den Excel-Report
   *aus den `ValidationIssue`-Objekten*.

## Bewusste Nicht-Ziele in Phase 1

* **Keine** vollständige DSL/AST-Regelengine (Phase 2).
* **Keine** XML-/xBRL-Writer (Phase 3).
* **Keine** automatische Metadata-Extraktion aus EBA-/SRB-Paketen (Phase 3).
* **Keine** Umverdrahtung der konkreten Regelauswertung – die 394 Regeln
  bleiben in `MBDTValidator` und werden über `_legacy_adapter` aufgerufen.
* Der `prerequisite_evaluator` deckt bewusst nur die heute genutzten
  Muster ab (siehe Modul-Docstring); komplexere Boolesche Logik kommt
  in Phase 2.

## Behobener Legacy-Bug (BUG-17)

`mbdt_validator.py:1190` (`v_CROSS_0010`, Submission A/B Deduplication)
nutzte

```python
df02_a = self.templates.get("B02.00_TypeA") or self.templates.get("B02.00")
```

`pandas.DataFrame.__bool__` wirft jedoch ``ValueError: The truth value of
a DataFrame is ambiguous``, sobald der erste ``get`` einen DataFrame
zurückliefert. Damit crashte die Regel im SRB-Normalfall (TypeA
geladen). Der Fix ist eine separate ``is None``-Prüfung; die Semantik
bleibt unverändert: TypeA bevorzugen, sonst auf generisches ``B02.00``
fallen. Abdeckung: vier Tests in
``tests/test_legacy_bugfix_v_cross_0010.py``.

## Offene Punkte / Architektur-Entscheidungen für den Owner

1. **Legacy-Fassade `MBDTValidator` behalten oder ablösen?**
   Aktuell Phase-1-Adapter → Legacy. Optionen:
   * (a) **Behalten** (empfohlen für Phase 1): keine Regressionsrisiken.
   * (b) **Inline migrieren**: einzelne Validatoren bekommen eigene
     Implementierungen, der Adapter entfällt. Größerer Aufwand, aber DQ
     Kategorie 3 („Explizite Zuständigkeiten") wäre stärker erfüllt.
2. **`field_structure.json` wird geladen, aber bislang nicht in den
   Validatoren konsumiert.** Empfehlung: in einem Folgeschritt für
   Pflichtfeld- und Typprüfungen nutzen.
3. **Reporting-Adapter** nutzt `MBDTValidator.generate_error_report`
   für das vollständige Excel-Layout. Eine eigenständige Excel-Schicht
   (ohne Legacy-Abhängigkeit) wäre eine sinnvolle Phase-1.5-Erweiterung.

## DQ-Kategorien-Abdeckung (Selbstbewertung)

| DQ-Kategorie | Status | Anmerkung |
|---|---|---|
| 1 Fachliche Gleichwertigkeit | ✓ | Legacy-Auswertung unverändert, alle 394 Regeln laufen. |
| 2 Vollständigkeit Regelabdeckung | ✓ | L1/L2/CL/DPM/CROSS/DQ alle dispatcht. |
| 3 Explizite Zuständigkeiten | ◑ | Module zugeordnet; konkrete Auswertung noch im Legacy-Validator. |
| 4 Einheitliches Fehlermodell | ✓ | Alles fließt durch `ValidationIssue`. |
| 5 Testbarkeit | ✓ | 26 Unit/E2E-Tests, Module isoliert importierbar. |
| 6 Transparenz | ✓ | Klarer Program Flow, Mapping-Matrix dokumentiert. |
| 7 Migrationsfähigkeit | ✓ | `prerequisite_evaluator.py` ist der AST-Einstiegspunkt. |
| 8 Betriebsstabilität | ✓ | Legacy-CLI `run_validation.py` unverändert. |

## CLI-Nutzung

Beide Einstiegspunkte funktionieren parallel:

```bash
# Legacy (unverändert)
python run_validation.py --input MeinTemplate.xlsx --entity "Bank AG"

# Neu, modular
python -m app.main --input MeinTemplate.xlsx --entity "Bank AG"
```

## Tests

```bash
python -m pytest tests/ -v
# 26 passed
```
