# DPM Value Aliases (CODE + Caption)

Eingabe-Werte in MBDT-Templates dürfen in zwei Varianten geliefert werden,
ohne dass Codelist- oder Prerequisite-Validierungen fehlschlagen:

**A) Technischer DPM-/Codelist-Wert allein**

```
SCT
True
Resolution Entity
```

**B) Technischer Wert plus Caption/Langtext**

Akzeptierte Separatoren:

| Separator | Beispiel |
|-----------|----------------------------------------------|
| ` - `     | `SCT - Secured collateralized liabilities`  |
| `:`       | `SCT: Secured collateralized liabilities`   |
| `(`       | `SCT (Secured collateralized liabilities)`  |
| `\|`      | `SCT \| Secured collateralized liabilities` |

## Auflösungsregeln

Implementiert in `app/normalization/value_resolver.py`.

1. **Technischer Code hat Vorrang.** Stimmt der Inputwert exakt mit einem
   zulässigen Codelist-Wert überein, wird er übernommen.
2. **`CODE + Caption` wird auf `CODE` reduziert**, wenn `CODE` in der
   erlaubten Werteliste enthalten ist.
3. **Caption-only** wird nur dann auf einen Code gemappt, wenn ein
   explizites Mapping `caption -> code` vorliegt und die Caption darin
   **eindeutig** ist.
4. **Mehrdeutige Caption** wird nicht still gemappt. Das Ergebnis trägt
   `ambiguous=True`; die Validierung meldet weiterhin einen Verstoß.

## Schutz vor falscher Reduktion

`canonicalize_for_compare` (für Prerequisite/DSL-Stringvergleich) reduziert
nur dann, wenn

- eine Codeliste übergeben wird **und** der linke Token darin enthalten ist,
  **oder**
- ohne Codeliste: der linke Token wie ein Code aussieht (kurz,
  alphanumerisch/Unterstrich, keine Whitespaces).

Damit bleiben **unverändert**:

- Numerische Werte (`1000.50`)
- ISO-Datumswerte (`2024-12-31` – Bindestrich ohne umliegende Spaces)
- LEI (20-stellig alphanumerisch)
- Beliebige Werte ohne erkannten Separator

## Integration

- `app/validation/codelist_validator.py` ruft `resolve_value` für jeden
  Inputwert auf, bevor ein Verstoß gemeldet wird.
- `app/validation/prerequisite_evaluator.py` ruft
  `canonicalize_for_compare` auf beiden Seiten der Gleichheitsprüfung auf
  (Regelwert ↔ Inputwert), sodass `CODE` und `CODE - Caption` als
  gleich gelten.

## Tests

Unter `tests/test_value_resolver.py`:

- Codelist akzeptiert `CODE`, `CODE - Caption`, `CODE: Caption`,
  `CODE (Caption)`, `CODE | Caption`
- Caption-only eindeutig wird akzeptiert
- Caption-only mehrdeutig liefert `ambiguous=True` und wird abgelehnt
- Prerequisite: `CODE - Caption` ist äquivalent zu `CODE` in beide
  Richtungen
- Numerische/Datum/LEI-Werte bleiben unverändert
