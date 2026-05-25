# Phase 3 – Metadata-getriebene RegTech-Pipeline (MVP)

Status: **MVP umgesetzt**, aufbauend auf Phase 1 (Architektur) und
Phase 2 (DSL/AST-Regelengine).

## Scope dieser Phase

Phase 3 ergänzt die Validierungsengine um drei neue Layer:

1. `app/metadata/` – Einlesen regulatorischer Pakete (DPM/Codelists/
   Regeln/Taxonomie) in ein internes, versionsfähiges Metadatenmodell.
2. `app/transformation/` – Überführung validierter DataFrames in das
   exportfähige Faktenmodell `CanonicalFact`.
3. `app/export/` – Erzeugung technischer Zielartefakte (XML und
   xBRL-CSV-Paket) inklusive Manifest, Export-Validierung und Audit.

Das interne Domänenmodell wird in `app/models/metadata_objects.py`
zentralisiert und ist über `app.models.__init__` exportiert.

## Was der MVP konkret leistet

- **Domänenmodell**: `MetadataPackage`, `DataPointDefinition`,
  `TemplateDefinition`, `CodelistDefinition`, `Dimension`, `Unit`,
  `Context`, `CanonicalFact`, `ExportArtifact`, `ExportPackage` plus
  Reuse von `RuleDefinitionV2` aus Phase 2. Alle Modelle besitzen
  `to_dict()`, das `MetadataPackage` zusätzlich `content_hash()` für
  versionierte Adressierung.
- **Package Locator / Reader**: erkennt Pakete an einer
  `manifest.json` im Wurzelverzeichnis, liest CSV (`;`-Trennzeichen,
  UTF-8 mit optionalem BOM) und JSON. `discover()` scannt rekursiv.
- **Extractoren**:
  - `DpmExtractor` → `DataPointDefinition`
  - `TaxonomyExtractor` → `TemplateDefinition` + `Dimension`
  - `CodelistExtractor` → `CodelistDefinition`
  - `ValidationRuleExtractor` → `RuleDefinitionV2`. Untranslatable
    Rules werden mit `metadata.translatable=False` markiert statt
    verworfen; DSL-Strings werden über den Phase-2-Parser
    syntaktisch geprüft.
  - `GlossaryExtractor` → Glossar als Dict.
- **MetadataMapper**: orchestriert alle Extractoren, baut `MetadataPackage`
  und leitet via `derive_config()` interne Konfiguration ab
  (Regel-Liste, Codelist-Map, Templates, Liste nicht übersetzbarer
  Regel-IDs).
- **Repository / Versionierung**: `MetadataRepository` ist immutable
  (`register()` wirft auf Re-Insert mit gleichem Hash);
  `MetadataVersioning.diff()` liefert ein `PackageDelta` mit
  Added/Removed/Changed für Datenpunkte, Templates, Codelists (inkl.
  Wert-Diff) und Regeln.
- **DQ-Diagnose**: `MetadataQualityChecker` erzeugt einen
  `QualityReport` mit Findings für fehlende `framework_version`,
  fehlende Datenpunkte, unbekannte Codelist-Referenzen, dangling
  Template-Datapoint-Referenzen, doppelte Regel-IDs, nicht
  übersetzbare Regeln und Reader-Diagnostics.
- **Transformation**: `CanonicalModelBuilder` baut `CanonicalFact` je
  Zeile/Datenpunkt mit Kontext, Einheit und Dimensionen.
  `DimensionMapper` mappt `ENTITY → c0010`, `PERIOD → c0020`,
  `UNIT → c0030` (MVP-Heuristik, anpassbar). `UnitBuilder` löst
  Einheiten aus dem Datenpunkt oder dem Currency-Feld auf.
  `ExportPreparer` sortiert stabil und filtert ungültige Facts.
- **Export-Writer**:
  - `XmlWriter` erzeugt ein UTF-8-XML mit Namespace
    `https://srb.example/mbdt/phase3`, je Fakt Tags für Kontext,
    Dimensionen, Wert und Audit-Herkunft (`source_row`,
    `source_file`).
  - `XbrlCsvWriter` schreibt ein Verzeichnis mit `facts.csv`,
    `metadata.json` und `parameters.csv`. Header enthält alle in
    den Facts vorkommenden Dimensions-Spalten.
  - `PackageManifestWriter` schreibt `manifest.json` mit
    Artefaktliste, Run-ID, Hashes, Status.
  - `AuditWriter` schreibt `audit.json` mit Run-ID, Zeitstempel,
    Input-Hash (SHA-256 über `to_dict()`-Liste), Metadata- und
    Rule-Version, Rule-Count, Artefakten und Status.
- **ExportValidator** prüft: technische Identifier vorhanden,
  Pflichtdimensionen, Reference-Period, Einheit bei MONETARY,
  Metadata-Versionskonsistenz und Dubletten (Template+Field+Entity+
  Datum+Dimensionen).

## Unterstützte Fixture-Formate (MVP)

Ein Package ist ein Verzeichnis mit:

```
manifest.json          # Pflicht; verlinkt alle Bestandteile
datapoints.csv         # CSV ;-getrennt
templates.csv
codelists.csv
dimensions.csv
validation_rules.json  # {"rules": [...]}
glossary.json          # optional
```

Beispiele liegen unter `tests/fixtures/phase3/package_v1` und `_v2`.

## DQ-Kriterien (Erfüllungsgrad MVP)

| Kriterium | Status |
|---|---|
| Metadatenvollständigkeit | erfüllt für Pilot-Template B02.00, Pflichtfelder vorhanden |
| Metadatentreue | 1:1-Mapping CSV/JSON → Domänenobjekt; Hash-basierte Versionierung |
| Versionskonsistenz | `ExportValidator` Code `EX040` blockt Mix; Hash auf `MetadataPackage` |
| Regelkonvergenz | DSL-translatierbare Regeln werden geprüft; Rest explizit markiert |
| Exportvollständigkeit | Pflichtdimensionen + Kontext + Einheit (bei MONETARY) verpflichtend |
| Exportkorrektheit | XML wird mit `ElementTree.fromstring()` re-parsed (Smoketest); CSV mit stabilem Header |
| Auditierbarkeit | `audit.json` enthält Input-Hash, Metadata-Version, Rule-Count, Run-ID, Zeitstempel, Artefakte |
| Änderungsbeherrschung | `PackageDelta` für Add/Remove/Change inkl. Codelist-Value-Diff |
| Betriebsstabilität | Fehlerhafte Packages liefern `diagnostics`/`QualityReport`, nicht Exceptions |
| Wiederverwendbarkeit | Pipeline pro Paket parameterisiert; weitere Templates über reine Metadaten ergänzbar |

## Bewusst nicht im MVP

- Kein vollständiger DPM-2.0-/XBRL-Taxonomy-Parser (kein XSD/Linkbase-
  Reader, kein XBRL-Discovery).
- Kein vollständiges xBRL-CSV-Format laut OIM-Spezifikation; das
  gelieferte CSV ist eine vereinfachte, anschlussfähige Annäherung.
- Kein automatischer Pull/Download von EBA-Paketen, keine
  Hotfix-Erkennung über externe Quellen.
- Kein UI für Metadatenpflege.
- Keine vollständige Übersetzung beliebiger natürlich-sprachlicher
  Regeltexte in DSL – `translatable=False` markiert echte Lücken.
- Keine ECB-/AnaCredit-spezifischen Sonderfälle.

## Offene Punkte / Risiken

- `DimensionMapper` ist heuristisch (Mapping ENTITY/PERIOD/UNIT auf
  feste Feldcodes). Für weitere Templates muss das Mapping je
  Template parametrisiert werden (Mapping-Tabelle aus Metadaten).
- `XbrlCsvWriter` produziert kein offizielles xBRL-CSV-Paket im
  OIM-Sinn (z. B. fehlt `report.json` mit Taxonomie-Referenz).
  Das ist bewusst auf Folgephase verschoben.
- Audit-Trail enthält noch keine Fehler-/Resubmission-Historie über
  mehrere Läufe – nur den aktuellen Run.
- Hash-basierte Versionierung verwendet SHA-256 über
  `to_dict()`-JSON. Bei Refactoring der Domänenmodelle ändert sich
  der Hash – das ist gewollt, muss aber im Operations-Handling
  beachtet werden.

## Roadmap-Status (Stand 2026-05-25)

- Phase 1 / 1.5 / 2: abgeschlossen, Tests grün.
- Phase 3 MVP: dieser Branch (`phase3-metadata-export-pipeline`).
- Nächste Schritte (Phase 3 Ausbau): echtes xBRL-CSV-Paketformat
  (OIM), DPM-2.0-Reader, dimensionale Mapping-Tabellen je Template,
  produktive Run-Governance über mehrere Läufe.
