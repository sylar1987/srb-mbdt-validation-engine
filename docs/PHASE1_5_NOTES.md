# Phase 1.5 – Native Engine Stabilisierung

Dieser Stand setzt **Phase 1.5** aus `phase_roadmap_1_5_2_3_konzept.md` um.
Ziel war: die in PR #1 geschaffene modulare Architektur produktiv nutzbar
machen, Legacy-Abhängigkeiten reduzieren und die Basis für Phase 2 (DSL)
und Phase 3 (Metadata/Export) legen – ohne bestehendes Verhalten zu
brechen.

## Was wurde umgesetzt

### 1. Native Validatoren mit Legacy-Fallback

`mandatory_validator`, `codelist_validator` und `datatype_validator`
liefern jetzt produktiv `ValidationIssue` aus eigener Python-Logik. Die
Auswertung folgt 1:1 dem Verhalten des Legacy-`MBDTValidator`
(getestet über `test_native_and_legacy_produce_same_issue_set` und den
Golden-Master).

* Pflichtfelder: Prerequisite-Auswertung über
  `app.validation.prerequisite_evaluator.evaluate`; fehlende Spalten
  werden als eigenes Issue gemeldet.
* Codelisten: `Catalog.codelists` + `field_codelist_map`,
  Sonderwerte `Not available` / `Not applicable` / `N/A` / `NA`
  toleriert (Legacy-Parität).
* Datentypen/Formate: `utils.regex_patterns` und `utils.iso_lists`
  decken numeric / date / ISO 3166 / ISO 4217 / LEI ab. Unbekannte
  `test_type`-Werte fallen auf den Legacy-Adapter zurück.

Der Modus ist über `EngineSettings.extra["use_native_validators"]`
schaltbar (Default: `True`). Mit `False` läuft die alte Adapter-Variante
weiter – nützlich für Migrationsvergleiche.

### 2. `field_structure.json` produktiv konsumiert

Neues typisiertes Modell `app.models.FieldStructure` mit
`TemplateStructure` und `FieldDefinition`. Das Modell akzeptiert beide
im Repository vorhandenen Schemavarianten (`field_code/column/mandatory`
und `code/col_number`). Geladen wird über
`app.config.catalog_loader.load_field_structure_model`.

Konsumiert wird das Modell vom neuen `structure_validator`
(`app.validation.structure_validator`). Er meldet:

* `STRUCT_001` – Template nicht in `field_structure.json`.
* `STRUCT_002` – Feld im DataFrame nicht in der Struktur beschrieben.
* `STRUCT_003` – Pflichtspalte fehlt im geladenen Template.

Strukturprüfung läuft als Teil von `ValidationEngine.run` *vor* dem
regelbasierten Dispatcher.

### 3. Run-Manifest-Skelett

`app.reporting.manifest.RunManifest` enthält:

* deterministische `run_id` (UUIDv5 über Input-Pfad + `started_at`)
* `started_at` / `finished_at` (UTC, ISO 8601)
* `input.path`, `input.source_type`, `input.hash` (SHA-256)
* `catalog.version`, `catalog.rule_count`, `catalog.de_annex`
* `templates_loaded` (sortiert)
* `issues.count`, `issues.by_severity`

Das Manifest wird im Runner automatisch nach `validate()` gebaut und
ist mit `Runner.write_manifest(path)` als deterministisches JSON
schreibbar. Tests in `tests/test_manifest.py` belegen, dass dieselben
Eingaben byte-identische JSONs erzeugen.

### 4. Reporting weiter entkoppelt

Neuer Standardpfad `app.reporting.write_issue_excel` schreibt einen
schlanken Report (Sheets `Issues`, `Summary`, `Manifest`) **ohne**
Legacy-Validator-Abhängigkeit, nur aus `ValidationIssue`,
`ValidationSummary` und `RunManifest`. Erreichbar über
`Runner.write_issue_report(path)`.

Der vorhandene `write_excel_report` (Legacy-Vollreport) bleibt für die
bestehende ausführliche Excel-Formatierung als Opt-in.

### 5. Golden-Master-Mini-Fixture

`tests/fixtures/golden_master_min/` enthält eine kleine synthetische
Submission und die erwartete Issue-Schlüsselliste
(`expected_issue_keys.json`). Der Regressionstest läuft sowohl im
nativen als auch im Legacy-Modus und verlangt vollständige Parität.

**Einschränkung:** Es liegen keine realen SRB-Submissions im
Repository. Die Fixture ist eine Mindestabdeckung für Pflichtfeld-,
Codelisten- und Datentypprüfungen, kein Vollersatz für echte
Bestandsdaten. Sobald freigegebene Realdaten verfügbar sind, sollte die
Suite erweitert werden.

## Was bleibt Legacy / Fallback

| Bereich | Stand |
|---|---|
| L2-Konsistenzregeln (`consistency_validator`) | weiterhin Legacy-Adapter |
| CROSS-Template-Regeln (`cross_template_validator`) | weiterhin Legacy-Adapter (BUG-17-Fix gehört dazu) |
| DQ-Regeln (`dq_validator`) | weiterhin Legacy-Adapter |
| Datentyp-`test_type`s außerhalb numeric/date/iso-3166/iso-4217/lei | Fallback auf Legacy-Adapter |
| `MBDTValidator.generate_error_report` (Legacy-Vollreport) | beibehalten als opt-in |
| `mbdt_validator.py` (≈2.297 Zeilen) | weiterhin als Fassade vorhanden |
| `prerequisite_evaluator` | deckt nur Phase-1-Muster ab; vollständige DSL kommt in Phase 2 |

## BUG-17-Regressionsschutz

Der Bugfix für `v_CROSS_0010` (Submission A/B Deduplication) bleibt
unverändert in `MBDTValidator._validate_cross_template_rule`. Die vier
Regressionstests in `tests/test_legacy_bugfix_v_cross_0010.py` laufen
weiterhin grün. Zusätzlich prüft
`tests/test_golden_master.py::test_golden_master_bug17_cross_rule_safe`,
dass die CROSS-Auswertung im neuen Runner-Pfad nicht crasht.

## Nächste Schritte (Phase 2 vorbereitet)

* `RuleDefinitionV2` mit `condition`/`assertion`/`scope` einführen
  (Mapping-Tabelle in der Roadmap).
* DSL/AST-Engine in `app/rules_language/` – der heutige
  `prerequisite_evaluator` ist der dokumentierte Einstiegspunkt.
* Native Migration der verbleibenden Validatoren (consistency, cross,
  dq) sollte erst nach der DSL erfolgen, damit doppelte Implementierung
  vermieden wird.

## Offene fachliche Entscheidungen

1. **Schemavereinheitlichung `field_structure.json`** – B02/B03/B04/B90
   nutzen ein anderes Key-Schema (`code`/`col_number`) als B99/B01/B05/B06.
   Empfehlung: vereinheitlichen auf `field_code`/`column`/`mandatory`,
   ggf. mit klar definierten `data_type`-Werten. (Aktueller Loader
   akzeptiert beide Varianten.)
2. **`mandatory`-Marker für B02/B03/B04/B90** – aktuell sind dort alle
   Felder ohne `mandatory`-Flag. `STRUCT_003` greift damit nur für
   B99/B01/B05/B06. Empfehlung: Markierung nachziehen, sobald die
   fachliche Pflichtfeldliste je Template bestätigt ist.

## Tests

```bash
python -m pytest tests/
# 54 passed
```

Suite-Übersicht:

| Datei | Schwerpunkt |
|---|---|
| `test_config_loader.py` | Katalog-Loader |
| `test_csv_loader.py` | CSV-Import |
| `test_field_structure.py` | Typisiertes Feldstruktur-Modell |
| `test_golden_master.py` | Golden-Master-Mini-Fixture (native + legacy) |
| `test_issue_excel_writer.py` | Standalone-Excel-Report |
| `test_legacy_bugfix_v_cross_0010.py` | BUG-17-Regression |
| `test_manifest.py` | Run-Manifest determinism |
| `test_models.py` | Dataclasses |
| `test_native_validators.py` | Native L1/CL/DPM + Struktur |
| `test_normalization.py` | Header/Wert-Normalisierung |
| `test_smoke_imports.py` | Package-Importe |
| `test_utils.py` | Utility-Funktionen |
| `test_validation_end_to_end.py` | Runner-E2E |
