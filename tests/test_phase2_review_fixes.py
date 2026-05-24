"""Regressionstests für die Review-Findings aus PR #4 (Phase 2 DSL).

Deckung:
  1. End-to-End: ``mandatory_validator`` reicht ``templates`` und
     ``current_template`` an ``eval_prereq`` durch, sodass Cross-Template-
     Bedingungen (``Bxx.yy.cNNNN = "X"``) im Produktionspfad funktionieren.
  2. Cross-Template-Sicherheit im Legacy-Fallback: eine Cross-Ref-Bedingung
     wird NICHT per Substring-Heuristik als lokale Feldprüfung interpretiert.
  3. Konsistente Null-Semantik (``= null`` / ``!= null``).
  4. String-Literal-Escaping im Legacy-Translator (eingebettete ``"`` / ``\\``).
  5. Kurze Feldreferenzen (``c40``) werden als FieldRef geparst und über
     ``find_column`` auf den 4-stelligen Header aufgelöst.
"""

from __future__ import annotations

import pandas as pd

from app.config.catalog_loader import (
    load_catalog,
    load_field_structure,
    load_field_structure_model,
)
from app.models import InputBatch, RuleDefinition, TemplateData
from app.models.rule_v2 import (
    _normalize_string_literal,
    translate_legacy_prerequisite,
)
from app.rules_language import EvaluationContext, evaluate as dsl_eval
from app.rules_language.parser import parse
from app.rules_language.ast_nodes import FieldRef, TemplateRef
from app.validation import mandatory_validator
from app.validation.context import ValidationContext
from app.validation.prerequisite_evaluator import evaluate as eval_prereq
from app.validation.prerequisite_evaluator import last_diagnostics


def _ctx_with(df_map: dict, catalog=None) -> ValidationContext:
    catalog = catalog or load_catalog()
    batch = InputBatch(source_type="memory", source_path="memory")
    for k, df in df_map.items():
        batch.add(TemplateData(template_id=k.split("_", 1)[0], key=k, df=df))
    return ValidationContext(
        batch=batch,
        catalog=catalog,
        field_structure=load_field_structure(),
        field_structure_model=load_field_structure_model(),
        legacy_validator=None,
        use_native_validators=True,
    )


# ── 1. End-to-End: Cross-Template-Prerequisite im mandatory_validator ──────


def test_mandatory_validator_cross_template_prerequisite_dsl_path():
    """Pflichtfeld nur, wenn B02.00.c0040 = "ISIN".

    Die Bedingung referenziert ein Feld in einem ANDEREN Template, das nur
    funktionieren kann, wenn ``mandatory_validator`` ``templates`` und
    ``current_template`` an ``eval_prereq`` durchreicht.
    """
    ctx = _ctx_with(
        {
            # Ziel-Template: c0050 ist die Pflichtspalte, eine Zeile leer.
            "B01.00": pd.DataFrame({"c0010": ["1"], "c0050": [""]}),
            # Referenz-Template, das die Bedingung aktiviert.
            "B02.00": pd.DataFrame({"c0040": ["ISIN"]}),
        }
    )
    rule = RuleDefinition(
        rule_id="T_CROSS_PREREQ",
        rule_level="L1",
        rule_type="MANDATORY_FIELD",
        template="B01.00",
        field_code="c0050",
        field_label="X-Ref",
        prerequisite='Rule applicable only if B02.00.c0040 = "ISIN"',
    )
    issues = mandatory_validator.validate(ctx, rule)
    assert len(issues) == 1
    assert issues[0].rule_id == "T_CROSS_PREREQ"


def test_mandatory_validator_cross_template_prerequisite_skips_when_false():
    """Wenn der Cross-Ref-Wert nicht passt, darf KEIN Issue entstehen."""
    ctx = _ctx_with(
        {
            "B01.00": pd.DataFrame({"c0010": ["1"], "c0050": [""]}),
            "B02.00": pd.DataFrame({"c0040": ["CUSIP"]}),
        }
    )
    rule = RuleDefinition(
        rule_id="T_CROSS_PREREQ_OFF",
        rule_level="L1",
        rule_type="MANDATORY_FIELD",
        template="B01.00",
        field_code="c0050",
        field_label="X-Ref",
        prerequisite='Rule applicable only if B02.00.c0040 = "ISIN"',
    )
    issues = mandatory_validator.validate(ctx, rule)
    assert issues == []


# ── 2. Sicherer Fallback bei Cross-Refs ────────────────────────────────────


def test_legacy_fallback_refuses_substring_match_for_cross_ref():
    """Schlägt DSL fehl, darf die Legacy-Heuristik bei einem Cross-Ref nicht
    auf die LOKALE Spalte ``c0040`` zurückgreifen – das würde fälschlich
    True/False liefern, abhängig vom Inhalt der lokalen Zeile."""
    # Lokales c0040 enthält "ISIN", würde also bei einem Substring-Treffer
    # die Bedingung "True" liefern – obwohl die Bedingung B02.00.c0040
    # referenziert, das gar nicht im Batch ist.
    df = pd.DataFrame({"c0040": ["ISIN"]})
    # Cross-Ref-Form, die der Translator akzeptiert: DSL würde versuchen
    # B02.00 aufzulösen → UnknownTemplate → Fallback. Der Fallback darf
    # nicht ``ISIN in ISIN`` matchen, sondern muss diagnostizieren.
    prereq = 'Rule applicable only if B02.00.c0040 = "ISIN"'
    result = eval_prereq(df, 0, prereq, {}, templates={}, current_template="B01.00")
    # Konservativ True (kein Unterdrücken von Issues), aber Diagnose vorhanden.
    assert result is True
    diags = last_diagnostics()
    assert any("Cross-Template" in d.message or "DSL_UNKNOWN_TEMPLATE" in d.code.value
               for d in diags), diags


# ── 3. Null-Semantik konsistent ────────────────────────────────────────────


def test_null_semantics_consistent():
    """Siehe docs/PHASE2_DSL_SPEC.md: Wahrheitstabelle für null."""
    ctx = EvaluationContext(df=pd.DataFrame({"a": [1]}), row_index=0)
    assert dsl_eval('null = null', ctx) is True
    assert dsl_eval('null != null', ctx) is False
    assert dsl_eval('"x" != null', ctx) is True
    assert dsl_eval('"x" = null', ctx) is False
    assert dsl_eval('null != "x"', ctx) is True
    assert dsl_eval('null = "x"', ctx) is False


def test_null_semantics_field_reference():
    df = pd.DataFrame({"c0040": [None]})
    ctx = EvaluationContext(df=df, row_index=0)
    assert dsl_eval('c0040 = null', ctx) is True
    assert dsl_eval('c0040 != null', ctx) is False

    df2 = pd.DataFrame({"c0040": ["ISIN"]})
    ctx2 = EvaluationContext(df=df2, row_index=0)
    assert dsl_eval('c0040 != null', ctx2) is True
    assert dsl_eval('c0040 = null', ctx2) is False


# ── 4. String-Literal-Escaping im Legacy-Translator ────────────────────────


def test_normalize_string_literal_escapes_embedded_quotes():
    """Aus ``'foo "bar"'`` muss ein gültiges DSL-Literal werden, das vom
    Lexer fehlerfrei wieder eingelesen werden kann."""
    out = _normalize_string_literal("'foo \"bar\"'")
    # Lexer-Roundtrip: ergebnis muss parsbar sein und denselben Wert liefern.
    from app.rules_language.lexer import tokenize
    from app.rules_language.tokens import TokenType
    tokens = tokenize(out)
    string_tokens = [t for t in tokens if t.type == TokenType.STRING]
    assert len(string_tokens) == 1
    assert string_tokens[0].value == 'foo "bar"'


def test_normalize_string_literal_escapes_backslash():
    """Backslashes dürfen nicht vom Lexer als Escape-Marker missdeutet werden."""
    out = _normalize_string_literal(r"some\path\value")
    from app.rules_language.lexer import tokenize
    from app.rules_language.tokens import TokenType
    tokens = tokenize(out)
    string_tokens = [t for t in tokens if t.type == TokenType.STRING]
    assert len(string_tokens) == 1
    assert string_tokens[0].value == r"some\path\value"


def test_translate_legacy_prerequisite_with_quoted_value_with_quote():
    """Vollständiger Translator-Pfad inkl. eingebettetem ``"``."""
    text = "Rule applicable only if c0040 = 'foo\"bar'"
    dsl = translate_legacy_prerequisite(text)
    assert dsl is not None
    # Roundtrip via Parser+Evaluator
    df = pd.DataFrame({"c0040": ['foo"bar']})
    ctx = EvaluationContext(df=df, row_index=0)
    assert dsl_eval(dsl, ctx) is True


# ── 5. c40 / kurze Feldreferenzen ─────────────────────────────────────────


def test_parser_resolves_short_field_code_as_field_ref():
    node = parse('c40 = "ISIN"')
    # Erwartet: linker Operand ist FieldRef("c40", ""), nicht TemplateRef.
    assert isinstance(node.left, FieldRef)
    assert not isinstance(node.left, TemplateRef)
    assert node.left.field_code == "c40"


def test_short_field_code_resolves_via_find_column():
    """``c40`` muss über ``find_column`` auf den 4-stelligen Header ``c0040``
    auflösen, ohne UnknownFieldError."""
    df = pd.DataFrame({"c0040": ["ISIN"]})
    ctx = EvaluationContext(df=df, row_index=0)
    assert dsl_eval('c40 = "ISIN"', ctx) is True


def test_translate_legacy_prerequisite_accepts_short_field_code():
    dsl = translate_legacy_prerequisite('Rule applicable if c40 = "ISIN"')
    assert dsl == 'c40 = "ISIN"'


def test_translate_legacy_prerequisite_accepts_cross_template_ref():
    """Cross-Template-Refs müssen den DSL-Pfad nehmen, nicht None liefern."""
    dsl = translate_legacy_prerequisite(
        'Rule applicable only if B02.00.c0040 = "ISIN"'
    )
    assert dsl == 'B02.00.c0040 = "ISIN"'
