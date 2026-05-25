"""Evaluator-Tests für die DSL (Phase 2)."""

import pandas as pd
import pytest

from app.rules_language import EvaluationContext, evaluate
from app.rules_language.diagnostics import DSLError, DiagnosticCode


@pytest.fixture
def df_simple():
    return pd.DataFrame(
        {
            "c0040": ["ISIN", "CUSIP", "ISIN", None],
            "c0250": ["Structured", "Non-Structured/Vanilla", None, "Other non-standard terms"],
            "c0070": [10, 0, 100, None],
            "c0240": ["A", "ZCB issued at discount", "B", "A"],
        }
    )


def test_evaluate_equality(df_simple):
    ctx = EvaluationContext(df=df_simple, row_index=0)
    assert evaluate('c0040 = "ISIN"', ctx) is True
    ctx.row_index = 1
    assert evaluate('c0040 = "ISIN"', ctx) is False


def test_evaluate_in(df_simple):
    ctx = EvaluationContext(df=df_simple, row_index=1)
    expr = 'c0250 in ("Non-Structured/Vanilla", "Other non-standard terms")'
    assert evaluate(expr, ctx) is True
    ctx.row_index = 0
    assert evaluate(expr, ctx) is False


def test_evaluate_not_in(df_simple):
    ctx = EvaluationContext(df=df_simple, row_index=0)
    expr = 'c0250 not in ("Non-Structured/Vanilla", "Other non-standard terms")'
    assert evaluate(expr, ctx) is True


def test_evaluate_truth_table_and():
    df = pd.DataFrame({"a": [1], "b": [0]})
    # Wir benutzen c-Felder nicht, sondern Literale, um Wahrheitstabelle direkt zu testen.
    ctx = EvaluationContext(df=df, row_index=0)
    assert evaluate('true and true', ctx) is True
    assert evaluate('true and false', ctx) is False
    assert evaluate('false and true', ctx) is False
    assert evaluate('false and false', ctx) is False


def test_evaluate_truth_table_or():
    ctx = EvaluationContext(df=pd.DataFrame({"x": [0]}), row_index=0)
    assert evaluate('true or true', ctx) is True
    assert evaluate('true or false', ctx) is True
    assert evaluate('false or true', ctx) is True
    assert evaluate('false or false', ctx) is False


def test_evaluate_not(df_simple):
    ctx = EvaluationContext(df=df_simple, row_index=0)
    assert evaluate('not (c0040 = "CUSIP")', ctx) is True


def test_evaluate_is_null(df_simple):
    ctx = EvaluationContext(df=df_simple, row_index=2)
    assert evaluate('is_null(c0250)', ctx) is True
    assert evaluate('is_not_null(c0250)', ctx) is False
    ctx.row_index = 0
    assert evaluate('is_null(c0250)', ctx) is False


def test_evaluate_null_in_comparison(df_simple):
    """Konsistente Null-Semantik (siehe docs/PHASE2_DSL_SPEC.md).

    ``null = "x"`` → False (null ist nicht "x").
    ``null != "x"`` → True (null ist ungleich "x"; Existenzprüfung).
    ``null = null`` → True, ``null != null`` → False.
    """
    ctx = EvaluationContext(df=df_simple, row_index=2)
    assert evaluate('c0250 = "anything"', ctx) is False
    assert evaluate('c0250 != "anything"', ctx) is True
    # Symmetrisch
    assert evaluate('"anything" = c0250', ctx) is False
    assert evaluate('"anything" != c0250', ctx) is True
    # null-Literale
    assert evaluate('null = null', ctx) is True
    assert evaluate('null != null', ctx) is False
    assert evaluate('c0250 = null', ctx) is True
    assert evaluate('c0250 != null', ctx) is False
    # Numerische Vergleiche bleiben SQL-nah: null < x → False
    ctx_null = EvaluationContext(df=df_simple, row_index=3)  # c0070 ist NaN
    assert evaluate('c0070 < 5', ctx_null) is False
    assert evaluate('c0070 > 5', ctx_null) is False


def test_evaluate_unknown_field_raises(df_simple):
    ctx = EvaluationContext(df=df_simple, row_index=0)
    with pytest.raises(DSLError) as exc:
        evaluate('c9999 = "x"', ctx)
    assert exc.value.diagnostic.code == DiagnosticCode.UNKNOWN_FIELD


def test_evaluate_unknown_function_raises(df_simple):
    ctx = EvaluationContext(df=df_simple, row_index=0)
    with pytest.raises(DSLError) as exc:
        evaluate('regexp_match(c0040, ".*")', ctx)
    assert exc.value.diagnostic.code == DiagnosticCode.UNSUPPORTED_FN


def test_evaluate_complex_prerequisite_pattern(df_simple):
    """Realistisches Muster aus rule_catalog.json (Zeile 411)."""
    expr = (
        'c0250 in ("Non-Structured/Vanilla", "Other non-standard terms") '
        'and c0240 != "ZCB issued at discount"'
    )
    ctx = EvaluationContext(df=df_simple, row_index=3)  # Other non-standard terms, c0240=A
    assert evaluate(expr, ctx) is True
    ctx.row_index = 1  # Non-Structured/Vanilla, c0240=ZCB issued at discount
    assert evaluate(expr, ctx) is False


def test_evaluate_numeric_comparison(df_simple):
    ctx = EvaluationContext(df=df_simple, row_index=0)
    assert bool(evaluate('c0070 > 5', ctx)) is True
    ctx.row_index = 1
    assert bool(evaluate('c0070 > 5', ctx)) is False
    assert bool(evaluate('c0070 >= 0', ctx)) is True


def test_evaluate_cross_template_ref():
    df_a = pd.DataFrame({"c0040": ["ISIN"], "c0050": ["123"]})
    df_b = pd.DataFrame({"c0040": ["ISIN"]})
    ctx = EvaluationContext(
        df=df_a,
        row_index=0,
        templates={"B02.00": df_b, "B01.00": df_a},
        current_template="B01.00",
    )
    assert evaluate('B02.00.c0040 = c0040', ctx) is True


def test_evaluate_short_circuit_and_skips_right(df_simple):
    """false and X darf X (mit unbekanntem Feld) nicht auswerten."""
    ctx = EvaluationContext(df=df_simple, row_index=0)
    # c0040 = "CUSIP" ist False; rechter Operand würde UnknownField werfen.
    assert evaluate('c0040 = "CUSIP" and c9999 = "x"', ctx) is False


def test_evaluate_short_circuit_or_skips_right(df_simple):
    ctx = EvaluationContext(df=df_simple, row_index=0)
    assert evaluate('c0040 = "ISIN" or c9999 = "x"', ctx) is True


def test_evaluate_functions_abs_min_max(df_simple):
    ctx = EvaluationContext(df=df_simple, row_index=0)
    assert evaluate('abs(-3)', ctx) == 3
    assert evaluate('min(1, 2, 3)', ctx) == 1
    assert evaluate('max(1, 2, 3)', ctx) == 3
    assert evaluate('len("abc")', ctx) == 3
    assert evaluate('lower("ABC")', ctx) == "abc"
    assert evaluate('upper("abc")', ctx) == "ABC"
