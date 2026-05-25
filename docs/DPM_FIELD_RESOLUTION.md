# DPM-Feldauflösung – Header-Varianten in der Validierungsengine

Die SRB MBDT-Validierungsengine arbeitet intern ausschließlich mit
**technischen DPM-Bezeichnungen** der Form `cNNNN` (z. B. `c0010`,
`c0040`, `c0051`). Eingabedaten (CSV/XLSX) liefern jedoch in der Praxis
unterschiedliche Spaltennamen. Dieses Dokument beschreibt, welche
Varianten unterstützt werden, wie die Auflösung funktioniert und welche
Diagnose-Möglichkeiten bestehen.

## Unterstützte Header-Varianten

| # | Variante | Beispiel | Auflösung |
|---|---|---|---|
| A | Nur technische Bezeichnung (mit `c`) | `c0040` | direkt |
| A' | Nur technische Bezeichnung (ohne `c`) | `0040`, `40` | per Auffüllen zu `c0040` |
| B | Technischer Code + Caption (Bindestrich) | `c0040 - Type of identifier` | Code wird extrahiert |
| B' | Technischer Code + Caption (En/Em Dash) | `c0040 – …`, `c0040 — …` | Code wird extrahiert |
| B'' | Technischer Code + Caption (Doppelpunkt) | `c0040: Type of identifier` | Code wird extrahiert |
| B''' | Technischer Code + Caption (Klammer) | `c0040 (Type of identifier)` | Code wird extrahiert |
| C | Nur Caption | `Type of the unique identifier (known to the counterparty)` | per FieldStructure-Mapping, sofern eindeutig |

Trenner für Variante B: `-`, `–` (U+2013), `—` (U+2014), `:`, `|`, `/`,
sowie umschließende Klammern `( … )`.

## Auflösungsreihenfolge

```
Header
  │
  ├─ Variante A/A'  → c-Code direkt
  ├─ Variante B/…   → c-Code per Regex extrahiert
  └─ Variante C     → FieldResolver(template, field_structure) per Label
                       └─ uneindeutig? → bleibt unverändert + Diagnose
```

Technische Codes haben immer Vorrang. Die Caption neben einem Code wird
nicht ausgewertet (sie ist nur informativ). Reine Caption-Header werden
**nur dann** auf einen `cNNNN`-Code gemappt, wenn die Caption in
`field_structure.json` für das jeweilige Template **eindeutig** einem
einzigen Code zugeordnet ist.

## Implementierung

* `app/normalization/field_resolver.py`
  * `extract_field_code_from_header(header)` – Regex-basierter Code-Extractor
    für Varianten A/B.
  * `FieldResolver(template_id, field_structure)` – baut ein
    Caption→Code-Mapping pro Template und erkennt uneindeutige Captions.
  * `resolve_dataframe_columns(df, template_id, field_structure)` –
    benennt DataFrame-Spalten um und liefert eine Diagnose-Liste
    (`{original, resolved, reason}` mit `reason ∈ {code, code+caption,
    caption, caption_ambiguous, unknown}`).
* `app/normalization/headers.py::normalize_col_names` nutzt
  `extract_field_code_from_header`, sodass bereits beim CSV-Einlesen
  Varianten A/B kanonisiert werden – auch ohne `field_structure`.
* `app/io/csv_loader.py` und `app/io/xlsx_loader.py` nehmen ein
  optionales `field_structure`-Argument entgegen und führen damit die
  Caption-Auflösung (Variante C) aus.
* `app/runner.py::Runner` reicht die geladene `FieldStructure` an alle
  Loader durch.

## Qualitäts-/Konformitätsprüfung

`app/quality/catalog_conformance.py::check_catalog` prüft den
Regelkatalog gegen die Feldstruktur und meldet:

* `MISSING_FIELD_CODE` – Regel ohne technischen Code,
* `NON_TECHNICAL_FIELD_CODE` – `field_code` ist keine `cNNNN`-Bezeichnung,
* `UNKNOWN_TEMPLATE` – Template fehlt in `field_structure.json`,
* `UNKNOWN_FIELD_CODE` – Code im FS-Template nicht vorhanden,
* `LABEL_MISMATCH` – Caption weicht vom FS-Label ab (weicher Hinweis).

Der Test `tests/test_field_resolver.py::test_catalog_conformance_clean_for_repo_catalog`
stellt sicher, dass alle 394 Regeln gegen die aktuelle
`field_structure.json` auflösbar sind.

## Aktueller Zustand des Repository-Katalogs

* `rules_checked = 394`
* `rules_resolved = 394`
* `MISSING_FIELD_CODE = 0`
* `NON_TECHNICAL_FIELD_CODE = 0`
* `UNKNOWN_TEMPLATE = 0`
* `UNKNOWN_FIELD_CODE = 0`
* `LABEL_MISMATCH = 76` (rein redaktionelle Abweichungen)

Die 76 `LABEL_MISMATCH`-Findings sind keine Validierungsfehler, sondern
Hinweise auf Caption-Divergenzen zwischen Regelkatalog und
Feldstruktur, z. B.:

* `c0030` Caption: *"Unique identification number (known to counterparty)"*
  vs. FS: *"Unique identification number (known to the counterparty)"*
* `c0060` Caption: *"Original amount issued in original currency"*
  vs. FS: *"Original amount issued in foreign currency"*

Sie betreffen ausschließlich die Anzeige und werden nicht für die
Header-Auflösung verwendet (technische Codes haben Vorrang). Eine
fachliche Harmonisierung der Captions wäre möglich, ist aber nicht
Voraussetzung für korrekte Validierung.

## Was passiert bei uneindeutigen Captions?

Wenn eine Caption innerhalb desselben Templates mehrfach vorkommt, wird
der entsprechende Header nicht stillschweigend gemappt. Stattdessen
bleibt der Header unverändert, `resolve_dataframe_columns` markiert ihn
mit `reason="caption_ambiguous"`, und die Spalte wird im
Validierungslauf wie eine unbekannte Spalte behandelt (= die jeweilige
Regel meldet einen Strukturfehler "Spalte fehlt", anstatt eine
potenziell falsche Spalte zu prüfen). So werden falsche stille
Mappings konsequent vermieden.

## Offene fachliche Lücken

Aktuell keine. Sollten in Zukunft Captions ergänzt/umbenannt werden,
schlägt der Test
`tests/test_field_resolver.py::test_catalog_conformance_clean_for_repo_catalog`
fehl, sobald ein `cNNNN`-Code im Regelkatalog nicht mehr auflösbar ist.
