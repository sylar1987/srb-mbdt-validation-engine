# Phase 2 – Umsetzungsstand

Stand: 2026-05-24

## Was Phase 2 liefert

- **DSL-Spezifikation** in `docs/PHASE2_DSL_SPEC.md` mit Literalen, Feld-/
  Template-/Cross-Referenzen, Vergleichs-, Mengen-, Booleschen Operatoren,
  Operatorpräzedenz, Wahrheitstabelle für `null`, Nicht-Zielen sowie
  positiven und negativen Beispielen.
- **`RuleDefinitionV2`** (`app/models/rule_v2.py`) parallel zu
  `RuleDefinition`. Trennt `condition` (Anwendbarkeit) und `assertion`
  (Aussage), inkl. `scope`, `severity`, `source`, `metadata`. Mapper
  `map_legacy_rule` übersetzt sicher abbildbare Bestandsregeln; nicht
  übersetzbare Prerequisites liefern `None` und werden vom Aufrufer
  bewusst nicht migriert.
- **Eigene Regelsprache** in `app/rules_language/`:
  - `tokens.py`, `lexer.py` – handgeschriebener Lexer mit String-Escapes,
    Mehrzeichen-Operatoren (`==`, `!=`, `<>`, `<=`, `>=`, `not in`).
  - `parser.py` – Recursive-Descent-Parser mit explizit dokumentierter
    Operatorpräzedenz.
  - `ast_nodes.py`, `ast_builder.py` – frozen Dataclasses, Helfer für
    programmatischen Aufbau (Tests/Phase 3).
  - `grammar.py` – EBNF-Referenz (rein dokumentierend).
  - `evaluator.py` – AST-Auswertung mit kurzschlüssigem `and`/`or`,
    SQL-naher `null`-Semantik, Cross-Template-Lookup über
    `find_matching_keys`.
  - `functions.py` – Built-ins: `is_null`, `is_not_null`, `is_reported`,
    `abs`, `min`, `max`, `len`, `lower`, `upper`.
  - `operators.py` – sichere Typkoerzierung (Number/String/Bool) für
    Vergleiche.
  - `diagnostics.py` – `Diagnostic`, `DSLError` und konkrete
    Fehlerklassen mit stabilen Codes (`DSL_SYNTAX`,
    `DSL_UNSUPPORTED_FN`, `DSL_UNKNOWN_FIELD`, `DSL_UNKNOWN_TEMPLATE`,
    `DSL_TYPE_ERROR`).
  - `serializer.py` – AST → deterministisches Dict für Tests/Audit.
- **Prerequisite-Migration** (`app/validation/prerequisite_evaluator.py`):
  versucht erst DSL-Übersetzung über
  `translate_legacy_prerequisite`, fällt bei nicht-übersetzbaren oder
  bei DSL-Auswertungsfehlern auf die Phase-1-Heuristik zurück. Diagnosen
  pro Aufruf sind über `last_diagnostics()` einsehbar.
- **Expression-Validator** (`app/validation/expression_validator.py`):
  voll funktionsfähige Auswertung für `RuleDefinitionV2` (row, template,
  cross). In Phase 2 noch **nicht** an die `engine.py`-Dispatcher-Kette
  angebunden, um Bestands-Pipelines nicht zu brechen. Phase 3 hängt
  DPM-extrahierte Regeln hier ein.
- **Tests** (`tests/test_rules_language_lexer_parser.py`,
  `tests/test_rules_language_evaluator.py`,
  `tests/test_rule_definition_v2.py`,
  `tests/test_prerequisite_evaluator_dsl.py`,
  `tests/test_expression_validator.py`): 57 neue Tests, alle grün;
  Regression der Phase-1/1.5-Tests bestätigt (59 grün, gesamt 116/116).

## Bewusst Fallback / Legacy

- **`prerequisite_evaluator`**: DSL wird nur dort verwendet, wo
  `translate_legacy_prerequisite` ein DSL-Programm liefert. Frei-
  formulierte Texte aus `rule_catalog.json` bleiben in der
  Phase-1-Heuristik. Sie geben (wie zuvor) konservativ `True` zurück,
  aber unterstützen den Hinweis über `last_diagnostics()`.
- **`mandatory_validator`/`codelist_validator`/`datatype_validator`/
  `consistency_validator`/`dq_validator`/`cross_template_validator`**:
  Verwenden weiterhin den Phase-1/1.5-Code. Ihre Prerequisite-Auswertung
  läuft über den jetzt DSL-fähigen Evaluator, sodass komplexere
  Prerequisite-Muster (z. B. `c0250 = ("A" OR "B") AND c0240 != "X"`)
  nun korrekt strukturiert ausgewertet werden – mit gleichem Ergebnis
  für die heute schon richtig laufenden Muster.
- **`expression_validator.validate_v2`** wird in Phase 2 nicht in die
  Standard-Pipeline (`engine.run_validation`) eingehängt. Dies ist eine
  bewusste Entscheidung, um keine fachlichen Regressionen zu riskieren,
  bevor DPM-Regeln in Phase 3 als `RuleDefinitionV2` eintreffen.

## Nicht-Ziele in Phase 2

- Keine Metadata-/Export-Pipeline (Phase 3).
- Kein `eval`/`exec` und keine freie Python-Ausführung im DSL-Pfad.
- Keine Aggregationen über Zeilen (`SUM`, `COUNT`); Vorbereitung folgt
  zusammen mit `template`-Scope und DPM-Regeln.
- Keine Regex/Datumsfunktionen.

## Offene Punkte Richtung Phase 3

1. Anbindung des `expression_validator` an die Dispatcher-Kette, sobald
   DPM-extrahierte Regeln als `RuleDefinitionV2` ankommen.
2. Aggregationen (`SUM(B02.00.c0070)`) und Template-Existenzprüfungen
   als Built-ins.
3. Hash-/Versionierung des AST in `RuleDefinitionV2.metadata`, um
   Audit-Trails zu unterstützen.
4. Migration weiterer Validator-Familien (Consistency, Cross-Template)
   auf `RuleDefinitionV2`-Auswertung.

## Wie man die DSL benutzt

```python
from app.rules_language import parse, evaluate, EvaluationContext
import pandas as pd

df = pd.DataFrame({"c0040": ["ISIN"], "c0070": [123]})
ctx = EvaluationContext(df=df, row_index=0)
assert evaluate('c0040 = "ISIN" and is_not_null(c0070)', ctx) is True
```

Für strukturierte Regeln:

```python
from app.models import RuleDefinitionV2
from app.validation.expression_validator import validate_v2

rule = RuleDefinitionV2(
    rule_id="R_DEMO",
    scope="row",
    target_template="B02.00",
    condition='c0040 = "ISIN"',
    assertion='is_not_null(c0070)',
    severity="ERROR",
    message="c0070 erforderlich, wenn c0040 = ISIN",
)
issues = validate_v2(validation_context, rule)
```
