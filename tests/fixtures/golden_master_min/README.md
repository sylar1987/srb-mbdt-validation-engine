# Golden-Master-Mini-Fixture (Phase 1.5)

Diese Fixture ist eine **kleine, synthetische** MBDT-Submission, die ein
reproduzierbares Set an `ValidationIssue`s erzeugt. Sie ersetzt keinen
echten Bestandsdatensatz – sie stellt sicher, dass die Engine für eine
bekannte, einfache Eingabe stabil das gleiche Ergebnis liefert.

## Inhalt

- `B99.00.csv` – minimal gültige Identifikation mit Reference Date,
  inklusive **gültiger LEI-Werte** (`529900XXXX0000000001`,
  `529900XXXX0000000002`) in `c0020` und `c0051`. Diese dürfen *nicht*
  als LEI-Format-Fehler gemeldet werden (Regression-Schutz: LEI darf
  nicht über das Substring `numeric` im `test_type` auf den
  Numeric-Check misrouted werden).
- `B02.00.csv` – eine Zeile mit absichtlichen Fehlern:
  - `c0030` leer → Pflichtfeldfehler (L1).
  - `c0140 = "FantasyType"` → Codelistenfehler (CL).
- `expected_issue_keys.json` – **handkuratierte** Liste der erwarteten
  Issue-Schlüssel (`rule_id, template, row, field_code, severity`).
  Bei Anpassungen an Rule-Engine oder Catalog ist der erwartete Soll-
  Stand bewusst zu pflegen; ein blindes „Self-Snapshot“ vom aktuellen
  Lauf ist nicht zulässig.

## Einschränkung

Es liegen **keine realen SRB-Submissions** im Repository. Diese Fixture
deckt deshalb nur Pflichtfeld-, Codelisten- und Datentypprüfungen für
zwei Templates ab. Eine breitere Golden-Master-Suite gegen reale
Submissions ist Folgeaufgabe, sobald repräsentative Testdaten freigegeben
werden können.
