# Golden-Master-Mini-Fixture (Phase 1.5)

Diese Fixture ist eine **kleine, synthetische** MBDT-Submission, die ein
reproduzierbares Set an `ValidationIssue`s erzeugt. Sie ersetzt keinen
echten Bestandsdatensatz – sie stellt sicher, dass die Engine für eine
bekannte, einfache Eingabe stabil das gleiche Ergebnis liefert.

## Inhalt

- `B99.00.csv` – minimal gültige Identifikation mit Reference Date.
- `B02.00.csv` – eine Zeile mit absichtlichen Fehlern:
  - `c0030` leer → Pflichtfeldfehler (L1).
  - `c0140 = "FantasyType"` → Codelistenfehler (CL).
- `expected_issue_keys.json` – Liste der erwarteten Issue-Schlüssel
  (`rule_id, template, row, field_code, severity`).

## Einschränkung

Es liegen **keine realen SRB-Submissions** im Repository. Diese Fixture
deckt deshalb nur Pflichtfeld-, Codelisten- und Datentypprüfungen für
zwei Templates ab. Eine breitere Golden-Master-Suite gegen reale
Submissions ist Folgeaufgabe, sobald repräsentative Testdaten freigegeben
werden können.
