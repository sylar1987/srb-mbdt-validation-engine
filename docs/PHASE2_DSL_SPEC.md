# Phase 2 – DSL-Spezifikation für die Regelengine

Stand: 2026-05-24 · Geltungsbereich: Paket `app/rules_language/`

Dieses Dokument definiert die in Phase 2 unterstützte Domain-Specific Language
(DSL) für Validierungsregeln. Die DSL wird vom Parser in einen Abstract Syntax
Tree (AST) überführt und vom `Evaluator` gegen einen Validierungs-Kontext
ausgewertet. Sie ersetzt schrittweise die Heuristiken aus
`app/validation/prerequisite_evaluator.py` (Phase 1).

## Designprinzipien

1. **Bewusst beschränkt.** Es ist keine universelle Programmiersprache. Es gibt
   keine Schleifen, keine Zuweisungen, keine Seiteneffekte, keine I/O.
2. **Sicher.** Es wird kein `eval`/`exec` verwendet. Ein eigener Lexer und
   rekursiver Descent-Parser erzeugen den AST; ein eigener Evaluator wertet
   ihn aus.
3. **Erklärbar.** Jeder Ausdruck wird zu einem deterministischen AST, der
   serialisierbar ist (`serializer.py`) und somit auditierbar und testbar.
4. **Migrationsfreundlich.** Bestehende `prerequisite`-Strings aus
   `rule_catalog.json` (z. B. `c0250 = "Structured"`) lassen sich entweder
   direkt oder über einen Translator in DSL-Form bringen.
5. **Robust bei fehlenden Daten.** Fehlende Spalten, fehlende Templates und
   Typabweichungen führen zu strukturierten Diagnosen, nicht zu Crashes.

## Lexikalische Elemente

### Literale

| Typ      | Beispiele                                | Bemerkung                                    |
|----------|------------------------------------------|----------------------------------------------|
| String   | `"Structured"`, `'Cash account'`         | Doppelte oder einfache Anführungszeichen     |
| Integer  | `0`, `42`, `-1`                          | Vorzeichen wird als unärer Operator gelesen  |
| Decimal  | `1.5`, `0.0`, `100.25`                   | Punkt als Dezimaltrenner                     |
| Boolean  | `true`, `false`                          | Klein geschrieben                            |
| Null     | `null`                                   | Steht für „nicht vorhanden“                  |

### Bezeichner (Feld-/Template-Referenzen)

| Form                  | Bedeutung                                                    |
|-----------------------|--------------------------------------------------------------|
| `c0040`               | Feld der aktuellen Zeile im aktuellen Template               |
| `cNNNN`               | Allgemeine Spaltenreferenz, vierstellig (`c0000`–`c9999`)    |
| `B02.00.c0040`        | Cross-Template-Referenz – Lookup im Ziel-Template            |
| `B02.00`              | Reine Template-Referenz (Existenz, Zeilenanzahl)             |

Feldreferenzen werden über `find_column` aufgelöst, sodass auch Header wie
`c0040` oder `c40` aus den Eingabe-CSV/XLSX gefunden werden.

### Operatoren

| Kategorie     | Operatoren                                            |
|---------------|-------------------------------------------------------|
| Vergleich     | `=`, `==`, `!=`, `<>`, `<`, `<=`, `>`, `>=`           |
| Mengen        | `in`, `not in`                                        |
| Logik         | `and`, `or`, `not`                                    |
| Arithmetik    | `+`, `-`, `*`, `/`                                    |
| Gruppierung   | `(`, `)`, Listen `(a, b, c)` bzw. `[a, b, c]`         |

`=` und `==` sind synonym, ebenso `!=` und `<>`. Dies erlaubt es,
EBA-/SRB-Regeltexte ohne Umformatierung als DSL zu verwenden.

### Funktionen (Built-ins)

| Funktion             | Bedeutung                                              |
|----------------------|--------------------------------------------------------|
| `is_null(x)`         | true, wenn `x` `null`/leer/`NaN`                       |
| `is_not_null(x)`     | true, wenn `x` nicht `null`/leer                       |
| `is_reported(x)`     | Alias von `is_not_null` mit zusätzlicher Trimm-Logik   |
| `abs(x)`             | Betrag einer Zahl                                      |
| `min(a, b, ...)`     | Minimum                                                |
| `max(a, b, ...)`     | Maximum                                                |
| `len(x)`             | Länge eines Strings                                    |
| `lower(x)`           | Kleinschreibung eines Strings                          |
| `upper(x)`           | Großschreibung eines Strings                           |

Funktionsargumente werden eager ausgewertet. Unbekannte Funktionen liefern
eine `UnsupportedFunctionError`-Diagnose, kein Python-Fehler.

### Operatorpräzedenz

Höchste Bindung zuerst:

1. Klammerung `(...)`
2. Funktionsaufruf, Member-Access (`B02.00.c0040`)
3. Unäres `-` und `+`
4. Multiplikativ `*`, `/`
5. Additiv `+`, `-`
6. Vergleich `=`, `==`, `!=`, `<>`, `<`, `<=`, `>`, `>=`
7. Mengen `in`, `not in`
8. Unäres `not` (bindet schwächer als Vergleiche, wie in SQL/Python)
9. Logisches `and`
10. Logisches `or`

`and`/`or` sind **kurzschlüssig**. `null` in Vergleichen ist „unbekannt“ und
führt nach SQL-naher Konvention zu `false` (siehe Wahrheitstabelle unten).

## Scope-Modell

| Scope          | Auswertungseinheit                              | Cross-Template? |
|----------------|-------------------------------------------------|-----------------|
| `row`          | Eine Zeile eines Templates                      | nein            |
| `template`     | Ein gesamtes Template                           | nein            |
| `cross`        | Mehrere Templates                                | ja              |

Der Scope wird in `RuleDefinitionV2.scope` gespeichert. Der Parser ist
scope-agnostisch; der Evaluator nutzt den Scope, um zu entscheiden, in
welchem Kontext die Referenzen aufgelöst werden.

## Nicht-Ziele (Phase 2)

- Keine freie Python-/SQL-Sprache, keine `eval`/`exec`.
- Keine Schleifen, keine Aggregationen über Zeilen (`SUM`, `COUNT`) in Phase 2.
  Vorbereitung folgt in Phase 3.
- Keine Datums-/Regex-Funktionen in der Erstauslieferung. (`like`/`matches`
  bleiben optional.)
- Keine Definition oder Auswertung von Variablen oder Funktionen durch den
  Anwender. Built-ins sind die einzige Erweiterung.
- Keine Seiteneffekte. Der Evaluator schreibt keine Daten.
- Keine implizite Typkoerzierung von String zu Zahl außerhalb klar
  definierter Funktionen.

## Wahrheitstabelle für `null`

| Ausdruck           | Ergebnis      |
|--------------------|---------------|
| `null = null`      | `false` (!)   |
| `is_null(null)`    | `true`        |
| `null = "x"`       | `false`       |
| `"x" != null`      | `true`        |
| `null and true`    | `false`       |
| `null or true`     | `true`        |
| `not null`         | `true`        |

Begründung: SRB-/EBA-Regeln gehen davon aus, dass nicht-berichtete Felder
zu einer „nicht erfüllten“ Bedingung führen, nicht zu einer Fehlauswertung.
Für explizite Null-Checks gibt es `is_null` / `is_not_null`.

## Positive Beispiele

```text
# Reines Feld-Equality (Standardform aus rule_catalog.json)
c0040 = "ISIN"

# Mengenmitgliedschaft (Mehrwertige Bedingungen aus den B-Templates)
c0250 in ("Structured", "Only structured coupon")

# Konjunktion und Negation
c0250 in ("Non-Structured/Vanilla", "Other non-standard terms")
  and c0240 != "ZCB issued at discount"

# Cross-Template-Referenz
B02.00.c0040 = c0040

# Funktionen
is_not_null(c0070) and c0070 > 0

# Klammerung
(c0040 = "ISIN" or c0040 = "CUSIP") and is_not_null(c0050)
```

## Negative Beispiele

```text
# Syntaxfehler – unbekannter Operator
c0040 ?? "ISIN"
# → SyntaxError: Unexpected token '?'

# Unbekannte Funktion
regexp_match(c0040, ".*")
# → UnsupportedFunctionError: regexp_match

# Unausgeglichene Klammer
(c0040 = "ISIN"
# → SyntaxError: Missing ')'
```

## Diagnostik

Diagnosen aus dem `diagnostics.py`-Modul tragen einen `code`:

| Code                     | Bedeutung                                          |
|--------------------------|----------------------------------------------------|
| `DSL_SYNTAX`             | Lexer/Parser-Fehler                                |
| `DSL_UNSUPPORTED_FN`     | Unbekannte oder noch nicht implementierte Funktion |
| `DSL_UNKNOWN_FIELD`      | Spalte fehlt im aktuellen Template                 |
| `DSL_UNKNOWN_TEMPLATE`   | Referenziertes Template fehlt im Batch             |
| `DSL_TYPE_ERROR`         | Operator auf inkompatiblen Typen                   |

Diagnosen werden vom Aufrufer (Evaluator, Prerequisite-Evaluator,
Expression-Validator) in `ValidationIssue`-Objekte transformiert.

## Migration aus rule_catalog.json

Bestehende `prerequisite`-Strings haben das Muster
`Rule applicable [only] if <expr>` mit `<expr>` bestehend aus:

- Gleichheit `cNNNN = "literal"`
- Ungleichheit `cNNNN != "literal"`
- Mengenliteral `cNNNN = ("a" OR "b")` → DSL: `cNNNN in ("a", "b")`
- Konjunktion `AND`

Ein eigener Translator (siehe `app/validation/prerequisite_evaluator.py` ab
Phase 2) normalisiert diese Form auf DSL-Syntax, bevor der Parser sie
verarbeitet. Komplexere Regeltexte werden in Phase 2 explizit als „nicht
unterstützt“ markiert und fallen auf die Phase-1-Heuristik zurück, statt
stillschweigend zu scheitern.
